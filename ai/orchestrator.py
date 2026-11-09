"""The central AI Orchestrator (GDD 14). Every game event runs the same executable workflow:

    1. receive the game event            6. validate the agents' results
    2. retrieve the player profile       7. apply PERMITTED learning-profile updates
    3. identify the educational goal     8. return a structured decision to the game engine
    4. decide which agents are needed    9. record the decision (ai_decisions table)
    5. invoke the agents / tools

Agent 6, the AI Planner (ai/planner_agent.py), is the LLM agent: when a live provider is set up,
Claude plans the learner's next step by calling the other agents as tools. An accepted plan steers
the topic (and, within one band of the rules, the difficulty) of the next few questions.

Each decision carries a ``trace`` - one line per step - which the profile screen shows as the
"AI log", so the agent workflow is visible and demonstrable rather than described.

The orchestrator may write ONLY learning data (question history, mastery, recommendations,
its own decision log). It never touches HP, damage, EXP, inventory, captures or quest state.
"""
import random

from ai.difficulty_manager import DifficultyManager
from ai.game_master import GameMaster
from ai.learning_analyst import LearningAnalyst
from ai.offline_provider import OfflineProvider
from ai.planner_agent import PlannerAgent
from ai.question_agent import QuestionGeneratorAgent
from ai.schemas import (OrchestratorDecision, SchemaError, TutorResponse, validate_question,
                        validate_recommendation, validate_tutor)
from ai.tutor_agent import TutorAgent
from combat import battle_rules
from mathematics import curriculum
from mathematics.answer_validator import AnswerValidator
from mathematics.question_generator import QuestionGenerator
from monsters.monster_data import quests


class AgentOrchestrator:
    def __init__(self, repository, question_generator=None, rng=None, llm=None, region="number_forest"):
        self.repository = repository
        self.rng = rng or random.Random()
        self.region = region
        self.llm = llm or OfflineProvider()
        self.difficulty_manager = DifficultyManager()
        self.questions = QuestionGeneratorAgent(question_generator or QuestionGenerator(self.rng),
                                                self.difficulty_manager, self.rng)
        self.analyst = LearningAnalyst(repository)
        self.tutor = TutorAgent()
        self.game_master = GameMaster()
        self.game_master_agent = self.game_master
        self.quest_manager = None   # set by the game once a save is loaded (read-only use)
        self.level_provider = None  # set by the game: callable -> the team's level (difficulty floor)
        self.last_decision = None
        self.planner = PlannerAgent(self, self.llm)
        self.plans = {}             # player_id -> {"plan": Plan, "remaining": questions left to steer}

    # ======================================================================== workflow
    def handle(self, event):
        handlers = {"question_request": self._question_request, "wrong_attempt": self._wrong_attempt,
                    "hint_request": self._hint_request, "worked_example": self._worked_example,
                    "answer_resolved": self._answer_resolved, "recommend": self._recommend,
                    "battle_end": self._battle_end}
        kind = event.get("type")
        if kind not in handlers:
            raise ValueError(f"unknown event type {kind!r}")
        decision = OrchestratorDecision(kind, "")
        decision.step(f"1. Received event '{kind}'" + (f" ({event.get('context')})" if event.get("context") else ""))
        handlers[kind](event, decision)
        if kind in ("question_request", "answer_resolved", "recommend", "battle_end"):
            decision.decision_id = self.repository.log_decision(
                event["player_id"], kind, decision.objective, decision.agents, decision.summary(),
                decision.message[:200])
            decision.step(f"9. Recorded decision #{decision.decision_id}")
        self.last_decision = decision
        return decision

    def _use(self, decision, agent):
        if agent.name not in decision.agents:
            decision.agents.append(agent.name)

    # ------------------------------------------------------------------ question request
    def _question_request(self, event, decision):
        player_id = event["player_id"]
        affinity = event.get("topic")
        decision.step("2. Retrieved the learning profile and recent history")
        self._use(decision, self.analyst)
        if affinity:
            analysis = self.analyst.analyse(player_id, affinity)
        else:
            topics = event.get("topics") or curriculum.REGION_TOPICS.get(self.region, curriculum.MASTERY_TOPICS)
            plan = self._active_plan(player_id, topics)
            if plan:
                analysis = self.analyst.analyse(player_id, plan.focus_topic)
                decision.step(f"2b. Following the AI Planner's plan: focus on {plan.focus_topic}")
                self._use(decision, self.planner)
            else:
                analysis = self.analyst.weakest(player_id, topics)
        topic = self.questions.choose_topic([analysis], affinity)
        decision.analysis = analysis
        goals = {"weakness": "remediate", "insufficient_evidence": "gather evidence", "developing": "consolidate",
                 "strong": "stretch", "mastered": "challenge"}
        decision.objective = f"{goals[analysis.status]} {curriculum.label(topic).lower()}"
        decision.step(f"3. Objective: {decision.objective} ({analysis.summary})")
        decision.step("4. Agents needed: Learning Analyst -> Difficulty Manager -> Question Generator"
                      + (" -> Tutor (struggling)" if analysis.status == "weakness" else ""))
        self._use(decision, self.difficulty_manager)
        history = self.repository.question_history(player_id, topic, limit=12)
        previous = history[0]["difficulty"] if history else ""
        difficulty = self.difficulty_manager.recommend(analysis, previous, self.player_level())
        plan = None if affinity else self._active_plan(player_id, [topic])
        if plan and plan.difficulty != difficulty.level:
            gap = abs(curriculum.DIFFICULTIES.index(plan.difficulty) - curriculum.DIFFICULTIES.index(difficulty.level))
            if gap <= 1:   # the planner may only nudge the rules by one band
                difficulty = type(difficulty)(plan.difficulty, difficulty.reason + " AI Planner adjusted it by one band.",
                                              previous)
        if plan:
            self.plans[player_id]["remaining"] -= 1
        if event.get("min_difficulty"):
            floor = curriculum.DIFFICULTIES.index(curriculum.normalise_difficulty(event["min_difficulty"]))
            if curriculum.DIFFICULTIES.index(difficulty.level) < floor:
                difficulty = type(difficulty)(curriculum.DIFFICULTIES[floor],
                                              difficulty.reason + " Raised to this area's minimum.", previous)
        decision.difficulty = difficulty
        decision.step(f"5. Difficulty Manager: {difficulty.level} - {difficulty.reason}")
        self._use(decision, self.questions)
        recent = [row["prompt"] for row in history]
        question = None
        for _ in range(3):
            candidate = self.questions.generate(topic, difficulty.level, event.get("subtopic"),
                                                event.get("affinity", ""), recent)
            try:
                question = validate_question(candidate)
                break
            except SchemaError as error:
                decision.step(f"6. Rejected a question: {error}")
        if question is None:   # never reached in practice; the templates always verify
            question = self.questions.generate("addition", "foundation")
        decision.question = question
        decision.step(f"6. Question {question.question_id} validated independently (answer type {question.answer_type})")
        if analysis.status == "weakness":
            self._use(decision, self.tutor)
            decision.tutor = self.tutor.hint(question, 0, analysis)
            decision.step("7. Tutor prepared a proactive first hint")
        decision.message = f"{curriculum.label(topic)} {difficulty.level} question"
        decision.step(f"8. Returned a {difficulty.level} {curriculum.label(topic).lower()} question to the game")

    # ------------------------------------------------------------------ tutor during a question
    def _analysis(self, event):
        try:
            return self.analyst.analyse(event["player_id"], event["question"].topic)
        except Exception:
            return None

    def _wrong_attempt(self, event, decision):
        question = event["question"]
        analysis = self._analysis(event)
        self._use(decision, self.tutor)
        decision.objective = "explain the mistake without giving the answer"
        decision.tutor = self.tutor.feedback(question, event.get("submitted", ""), analysis)
        decision.message = decision.tutor.text

    def _hint_request(self, event, decision):
        question = event["question"]
        self._use(decision, self.tutor)
        decision.objective = "progressive hint"
        decision.tutor = self.tutor.hint(question, int(event.get("level", 0)), self._analysis(event))
        decision.message = decision.tutor.text

    def _worked_example(self, event, decision):
        question = event["question"]
        self._use(decision, self.questions)
        self._use(decision, self.tutor)
        decision.objective = "worked example on different numbers"
        decision.tutor = self.tutor.worked_example(self.questions.worked_example(question))
        decision.message = decision.tutor.text

    # ------------------------------------------------------------------ after the question
    def _answer_resolved(self, event, decision):
        player_id, question = event["player_id"], event["question"]
        outcome = event["outcome"]
        worked = bool(event.get("worked_example"))
        score = battle_rules.learning_score(outcome, worked)
        decision.step("2. Retrieved the learning profile")
        decision.objective = f"update {curriculum.label(curriculum.mastery_topic(question.topic)).lower()} mastery"
        decision.step(f"3. Objective: {decision.objective}")
        decision.step("4. Agents needed: Learning Analyst, Tutor, Game Master")
        wrong_answers = [a for a in event.get("attempts", []) if not question.check(a).correct]
        misconception = ""
        for answer in wrong_answers:
            misconception = self.tutor.misconception_for(question, str(answer).strip()) or misconception
        before = self.analyst.analyse(player_id, question.topic)
        # 7. The only write the AI layer is allowed: the learning record (GDD 13).
        updated = self.repository.record_assessment(
            player_id, question, outcome != battle_rules.FAILED, event.get("used_hint", False),
            event.get("attempts_used", 1), score, (event.get("attempts") or [""])[-1], misconception, worked,
            event.get("context", ""))
        self._use(decision, self.analyst)
        analysis = self.analyst.analyse(player_id, question.topic)
        decision.analysis = analysis
        decision.step(f"5. Learning Analyst: score {score:.2f} recorded; mastery {before.mastery_score} -> "
                      f"{updated['mastery']} ({analysis.status})")
        self._use(decision, self.tutor)
        decision.tutor = self.tutor.explain(question, outcome, analysis)
        decision.step("6. Tutor explanation validated")
        decision.step(f"7. Learning profile updated ({updated['evidence']} assessed {analysis.topic} questions)")
        improved = before.status == "weakness" and analysis.status != "weakness"
        if analysis.status == "weakness" or improved or analysis.identified_weakness:
            self._use(decision, self.game_master)
            recommendation = self._quest_recommendation(player_id)
            decision.recommendation = recommendation
            text = self.game_master.recommendation_text(self._ordered_analyses(player_id), recommendation)
            if improved:
                text = f"{curriculum.label(analysis.topic)} is improving! " + text
            self.repository.add_recommendation(player_id, text)
            decision.message = text
            decision.step(f"8. Game Master recommended: {text}")
        else:
            decision.message = decision.tutor.text
            decision.step("8. Returned the explanation to the game")

    def _ordered_analyses(self, player_id, topics=None):
        topics = topics or curriculum.MASTERY_TOPICS
        analyses = [self.analyst.analyse(player_id, topic) for topic in topics]
        order = {"weakness": 0, "insufficient_evidence": 2, "developing": 1, "strong": 3, "mastered": 4}
        evidence = [a for a in analyses if a.evidence_count > 0]
        untested = [a for a in analyses if a.evidence_count == 0]
        return sorted(evidence, key=lambda a: (order[a.status], a.mastery_score)) + untested

    def _quest_recommendation(self, player_id):
        manager = self.quest_manager
        available = manager.available() if manager else list(quests())
        active = manager.active() if manager else []
        recommendation = self.game_master.recommend_quest(self._ordered_analyses(player_id), available, active)
        try:
            return validate_recommendation(recommendation, quests())
        except SchemaError:
            return None

    # ------------------------------------------------------------------ recommendations
    def _recommend(self, event, decision):
        player_id = event["player_id"]
        decision.step("2. Retrieved the learning profile, party level and quest progress")
        analyses = self._ordered_analyses(player_id)
        self._use(decision, self.analyst)
        self._use(decision, self.game_master)
        decision.objective = "plan the next learning step"
        decision.step(f"3. Objective: {decision.objective}")
        decision.step("4-5. Learning Analyst ranked the topics; Game Master matched quests")
        recommendation = self._quest_recommendation(player_id)
        decision.recommendation = recommendation
        decision.analysis = analyses[0] if analyses else None
        ready, advice = self.game_master.boss_readiness(analyses[:5], event.get("party_level", 1),
                                                        event.get("seals_done", False))
        text = self.game_master.recommendation_text(analyses, recommendation)
        decision.message = text
        decision.extra = {"objectives": self.game_master.objectives(analyses), "boss_ready": ready,
                          "boss_advice": advice}
        decision.step(f"6-8. Recommendation validated and returned: {text}")
        self.repository.add_recommendation(player_id, text)

    def _battle_end(self, event, decision):
        """GDD 7.7: the AI may analyse how the player handled an encounter (it changes nothing)."""
        player_id = event["player_id"]
        answered = event.get("answers", [])
        right = sum(1 for outcome in answered if outcome != battle_rules.FAILED)
        decision.objective = "review the encounter"
        decision.step(f"2-5. Encounter vs {event.get('enemy', '?')}: {right}/{len(answered)} questions answered, "
                      f"outcome {event.get('outcome')}")
        self._use(decision, self.analyst)
        decision.message = f"{right}/{len(answered)} correct vs {event.get('enemy', '?')} ({event.get('outcome')})"
        decision.step("8. Summary stored for future recommendations")

    # ======================================================================== AI Planner (LLM agent)
    def player_level(self):
        try:
            return int(self.level_provider()) if self.level_provider else None
        except Exception:
            return None

    def _active_plan(self, player_id, topics):
        entry = self.plans.get(player_id)
        if not entry or entry["remaining"] <= 0 or entry["plan"].focus_topic not in topics:
            return None
        return entry["plan"]

    def start_planning(self, player_id, party_level=1, seals_done=False):
        """Ask the AI Planner for a plan in the background. A Future resolving to a Plan or None."""
        return self.planner.plan_async(player_id, party_level, seals_done)

    def apply_plan(self, player_id, plan, steer_questions=3):
        """Adopt a validated plan: log it with Claude's tool calls, store the advice, steer questions."""
        decision = OrchestratorDecision("agent_plan", f"plan: focus on {curriculum.label(plan.focus_topic).lower()}")
        decision.agents = [self.planner.name] + sorted({self._agent_for(name) for name in plan.tool_calls} - {""})
        decision.step(f"1. AI Planner (Claude) given the goal: plan the next learning step")
        for line in plan.trace:
            decision.step(line)
        if plan.reasoning:
            decision.step(f"Reasoning: {plan.reasoning}")
        decision.step(f"Plan validated against the rules; steering the next {steer_questions} questions")
        decision.message = plan.message
        decision.extra = {"objectives": plan.objectives, "quest_id": plan.quest_id}
        self.plans[player_id] = {"plan": plan, "remaining": steer_questions}
        self.repository.add_recommendation(player_id, plan.message)
        decision.decision_id = self.repository.log_decision(player_id, "agent_plan", decision.objective,
                                                            decision.agents, decision.summary(), plan.message[:200])
        self.last_decision = decision
        return decision

    @staticmethod
    def _agent_for(tool_name):
        return {"get_learning_overview": "learning_analyst", "analyse_topic": "learning_analyst",
                "recommend_difficulty": "difficulty_manager", "list_quests": "game_master",
                "check_boss_readiness": "game_master", "get_training_spot": "game_master"}.get(tool_name, "")

    # ======================================================================== conveniences
    def request_question(self, player_id, topic=None, context="battle", subtopic=None, affinity="",
                         min_difficulty=None, topics=None):
        decision = self.handle({"type": "question_request", "player_id": player_id, "topic": topic,
                                "context": context, "subtopic": subtopic, "affinity": affinity,
                                "min_difficulty": min_difficulty, "topics": topics})
        return decision

    def recommendations(self, player_id, party_level=1, seals_done=False):
        return self.handle({"type": "recommend", "player_id": player_id, "party_level": party_level,
                            "seals_done": seals_done})

    # ======================================================================== pre-GDD API (Arena)
    def next_question(self, player_id, topic=None, fallback="easy"):
        profile = self.repository.get_learning_profile(player_id)
        return self.questions.act(profile, topic, fallback)

    def submit_answer(self, player_id, question, submitted):
        correct = AnswerValidator.check(submitted, question.answer)
        self.repository.record_attempt(player_id, question, submitted, correct)
        feedback = self.tutor.legacy_feedback(question, correct)
        reward = 0 if not correct else {"easy": 4, "intermediate": 7, "advanced": 10}.get(question.difficulty, 4)
        return _LegacyAnswer(correct, feedback, "", question.difficulty, reward, "")

    def profile(self, player_id, level=1):
        return {"topics": self.repository.learning_profile(player_id),
                "summary": self.repository.history_summary(player_id),
                "mistakes": [a for a in self.repository.recent_attempts(player_id, 25) if not a["correct"]][:4],
                "recommendations": self.repository.recommendations(player_id),
                "next_step": self.game_master.recommendation({}, level)}


class _LegacyAnswer:
    def __init__(self, correct, feedback, weakness, next_difficulty, exp_reward, recommendation):
        self.correct, self.feedback, self.weakness = correct, feedback, weakness
        self.next_difficulty, self.exp_reward, self.recommendation = next_difficulty, exp_reward, recommendation
