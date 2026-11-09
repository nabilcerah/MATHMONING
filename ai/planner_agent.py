"""Agent 6 - the AI Planner: an LLM agent (Claude) that plans the learner's next step.

This is the "agentic" part of the AI layer. Instead of a fixed workflow, Claude is given a goal
("plan this learner's next step") and a set of TOOLS - the other five agents - and decides by
itself which tools to call, in what order, and when it knows enough:

    goal -> Claude reasons -> calls tools (analyse topics, check quests, difficulty...) -> reads the
    results -> calls more tools if needed -> submits a plan with ``submit_plan``

Guard rails (GDD 17) - the model plans, the rules stay in charge:
  * Every tool is READ-ONLY. The planner cannot change HP, EXP, items, quests or answers.
  * ``submit_plan`` is validated: a real topic, a difficulty within one band of what the
    Difficulty Manager allows, an existing quest, safe and short text, and the plan must be based
    on at least one data tool call. A rejected plan goes back to Claude with the reason, so it can
    correct itself (up to MAX_TURNS model calls in total).
  * Questions and answers still come only from the verified templates - Claude never writes them.
  * Only learning statistics are sent (no player name or other personal data).
  * No API key, offline mode, the web build, a timeout or any error -> no plan, and the
    rule-based orchestrator carries on exactly as before.
"""
import json
from concurrent.futures import Future
from dataclasses import dataclass, field

from ai.agent_base import Agent
from ai.game_master import TRAINING
from ai.schemas import safe_text
from mathematics import curriculum
from monsters.monster_data import quests

MAX_TURNS = 6           # model calls per plan (tool calls in one turn count once)
MAX_TOKENS = 1024

SYSTEM_PROMPT = """You are the AI Planner inside MATHMON, a maths-learning monster RPG for learners aged 12-17.
Your goal: decide the learner's next learning step - which topic to focus on, at what difficulty, which existing \
quest (if any) fits, up to three short objectives, and one encouraging message for the learner.

Work like an agent: use the tools to gather evidence before deciding. Usually start with get_learning_overview, then \
look deeper at the topics that matter (analyse_topic, recommend_difficulty), and check list_quests and \
check_boss_readiness when they are relevant. Do not guess numbers - base the plan on tool results.

When you are confident, call submit_plan exactly once. If it is rejected, read the reason, fix the plan and submit again.
Rules: the focus topic must be one of the curriculum topics; keep the difficulty within one band of the Difficulty \
Manager's recommendation; only use quest ids returned by list_quests; the message must be warm, encouraging, \
under 220 characters and never shaming. Topics with too little evidence need practice to measure them, not remediation."""

DATA_TOOLS = ("get_learning_overview", "analyse_topic", "recommend_difficulty", "list_quests",
              "check_boss_readiness", "get_training_spot")


def _topic_schema(description="A curriculum topic id."):
    return {"type": "string", "enum": list(curriculum.MASTERY_TOPICS), "description": description}


TOOLS = [
    {"name": "get_learning_overview",
     "description": "Learning Analyst: every curriculum topic with its status (weakness, developing, strong, mastered "
                    "or insufficient_evidence), mastery 0-100, number of assessed questions, recent accuracy and hint "
                    "rate. Ordered from most to least in need.",
     "input_schema": {"type": "object", "properties": {}}},
    {"name": "analyse_topic",
     "description": "Learning Analyst: a detailed look at one topic, including any repeated misconception and the "
                    "learner's recent wrong answers in that topic.",
     "input_schema": {"type": "object", "properties": {"topic": _topic_schema()}, "required": ["topic"]}},
    {"name": "recommend_difficulty",
     "description": "Difficulty Manager (rule-based): the difficulty the rules allow next for a topic, with the reason. "
                    "Your plan's difficulty must stay within one band of this.",
     "input_schema": {"type": "object", "properties": {"topic": _topic_schema()}, "required": ["topic"]}},
    {"name": "list_quests",
     "description": "Quest log: the quests that are active or available to start, with the topics each one practises.",
     "input_schema": {"type": "object", "properties": {}}},
    {"name": "check_boss_readiness",
     "description": "Game Master: whether the learner's team and skills look ready for the region boss, with advice.",
     "input_schema": {"type": "object", "properties": {}}},
    {"name": "get_training_spot",
     "description": "Game Master: where in the world a topic is practised best, and which monster lives there.",
     "input_schema": {"type": "object", "properties": {"topic": _topic_schema()}, "required": ["topic"]}},
    {"name": "submit_plan",
     "description": "Submit the final plan. It is validated against the game rules; if it is rejected you get the "
                    "reason and may submit a corrected plan.",
     "input_schema": {
         "type": "object",
         "properties": {
             "focus_topic": _topic_schema("The topic the next questions should practise."),
             "difficulty": {"type": "string", "enum": list(curriculum.DIFFICULTIES)},
             "quest_id": {"type": "string", "description": "An id from list_quests, or an empty string for none."},
             "objectives": {"type": "array", "items": {"type": "string"}, "maxItems": 3,
                            "description": "Up to three short, measurable learning objectives."},
             "message": {"type": "string", "description": "One warm message to the learner (under 220 characters)."},
             "reasoning": {"type": "string", "description": "One sentence: why this plan (shown in the AI log)."},
         },
         "required": ["focus_topic", "difficulty", "quest_id", "objectives", "message", "reasoning"],
     }},
]


@dataclass
class Plan:
    focus_topic: str
    difficulty: str
    quest_id: str
    objectives: list
    message: str
    reasoning: str
    trace: list = field(default_factory=list)      # one line per model turn / tool call
    tool_calls: list = field(default_factory=list)  # names, in order


class PlanRejected(ValueError):
    pass


def _done(value):
    future = Future()
    future.set_result(value)
    return future


class PlannerAgent(Agent):
    name = "ai_planner"

    def __init__(self, orchestrator, llm):
        self.orchestrator, self.llm = orchestrator, llm

    @property
    def available(self):
        return bool(getattr(self.llm, "available", False))

    # ------------------------------------------------------------------ entry points
    def plan_async(self, player_id, party_level=1, seals_done=False):
        """Plan on the provider's worker thread (never on the game loop). Resolves to a Plan or None."""
        if not self.available:
            return _done(None)
        return self.llm.executor.submit(self.plan, player_id, party_level, seals_done)

    def plan(self, player_id, party_level=1, seals_done=False, client=None):
        """Run the agent loop. Returns a validated Plan, or None if anything goes wrong."""
        try:
            return self._run(player_id, party_level, seals_done, client or self.llm._client())
        except Exception:
            return None

    # ------------------------------------------------------------------ the agent loop
    def _run(self, player_id, party_level, seals_done, client):
        tools = _Toolbox(self.orchestrator, player_id, party_level, seals_done)
        messages = [{"role": "user", "content": (
            f"Plan the next learning step for this learner. Their team is level {party_level}; "
            f"the Numera Seals are {'restored' if seals_done else 'not restored yet'}. Use the tools.")}]
        trace, calls = [], []
        for turn in range(1, MAX_TURNS + 1):
            response = client.messages.create(model=self.llm.model, max_tokens=MAX_TOKENS, system=SYSTEM_PROMPT,
                                              tools=TOOLS, messages=messages)
            messages.append({"role": "assistant", "content": response.content})
            uses = [block for block in response.content if getattr(block, "type", "") == "tool_use"]
            if not uses:
                if getattr(response, "stop_reason", "") in ("max_tokens", "refusal"):
                    return None
                # Finished talking without a plan: one nudge, then give up.
                trace.append(f"Turn {turn}: Claude answered without a plan - asked it to call submit_plan")
                messages.append({"role": "user", "content": "Please call submit_plan with your plan now."})
                continue
            results, plan = [], None
            for use in uses:
                calls.append(use.name)
                args = use.input if isinstance(use.input, dict) else {}
                if use.name == "submit_plan":
                    try:
                        plan = self._validate(args, tools, calls)
                        trace.append(f"Turn {turn}: submit_plan -> ACCEPTED ({plan.focus_topic}, {plan.difficulty})")
                        results.append(_result(use.id, "Plan accepted."))
                    except PlanRejected as error:
                        trace.append(f"Turn {turn}: submit_plan -> REJECTED: {error}")
                        results.append(_result(use.id, f"Plan rejected: {error}", error=True))
                    continue
                try:
                    output = tools.call(use.name, args)
                    trace.append(f"Turn {turn}: {use.name}({_short(args)}) -> {output.get('summary', 'ok')}")
                    results.append(_result(use.id, json.dumps(output)))
                except Exception as error:   # bad arguments: tell Claude, let it retry
                    trace.append(f"Turn {turn}: {use.name}({_short(args)}) -> error: {error}")
                    results.append(_result(use.id, f"Tool error: {error}", error=True))
            messages.append({"role": "user", "content": results})
            if plan is not None:
                plan.trace, plan.tool_calls = trace, calls
                return plan
        return None

    # ------------------------------------------------------------------ validation (the rules win)
    def _validate(self, args, tools, calls):
        if not any(name in DATA_TOOLS for name in calls):
            raise PlanRejected("look at the learner's data with the tools before planning")
        topic = str(args.get("focus_topic", ""))
        if topic not in curriculum.MASTERY_TOPICS:
            raise PlanRejected(f"unknown topic {topic!r}")
        difficulty = str(args.get("difficulty", ""))
        if difficulty not in curriculum.DIFFICULTIES:
            raise PlanRejected(f"unknown difficulty {difficulty!r}")
        allowed = tools.rule_difficulty(topic)
        gap = abs(curriculum.DIFFICULTIES.index(difficulty) - curriculum.DIFFICULTIES.index(allowed))
        if gap > 1:
            raise PlanRejected(f"{difficulty} is too far from the Difficulty Manager's {allowed} for {topic}")
        quest_id = str(args.get("quest_id", "") or "")
        if quest_id and quest_id not in tools.quest_ids():
            raise PlanRejected(f"quest {quest_id!r} is not active or available")
        message = " ".join(str(args.get("message", "")).split())
        if not safe_text(message) or len(message) > 220:
            raise PlanRejected("the message must be kind, non-empty and under 220 characters")
        objectives = args.get("objectives") or []
        if not isinstance(objectives, list) or len(objectives) > 3:
            raise PlanRejected("give at most three objectives")
        objectives = [" ".join(str(goal).split())[:90] for goal in objectives]
        if not all(safe_text(goal) for goal in objectives):
            raise PlanRejected("every objective must be short, kind text")
        reasoning = " ".join(str(args.get("reasoning", "")).split())[:200]
        return Plan(topic, difficulty, quest_id, objectives, message, reasoning if safe_text(reasoning) else "")


def _result(tool_use_id, content, error=False):
    result = {"type": "tool_result", "tool_use_id": tool_use_id, "content": content}
    if error:
        result["is_error"] = True
    return result


def _short(args):
    return ", ".join(f"{value}" for value in args.values())[:30]


class _Toolbox:
    """The planner's tools: thin, READ-ONLY wrappers around the rule-based agents."""

    def __init__(self, orchestrator, player_id, party_level, seals_done):
        self.o, self.player_id = orchestrator, player_id
        self.party_level, self.seals_done = party_level, seals_done

    def call(self, name, args):
        if name not in DATA_TOOLS:
            raise ValueError(f"unknown tool {name!r}")
        return getattr(self, name)(**args)

    @staticmethod
    def _topic(topic):
        if topic not in curriculum.MASTERY_TOPICS:
            raise ValueError(f"unknown topic {topic!r}; use one of {', '.join(curriculum.MASTERY_TOPICS)}")
        return topic

    def get_learning_overview(self):
        analyses = self.o._ordered_analyses(self.player_id)
        rows = [{"topic": a.topic, "status": a.status, "mastery": a.mastery_score, "evidence": a.evidence_count,
                 "recent_accuracy": round(a.recent_accuracy, 2), "hint_rate": round(a.hint_rate, 2)} for a in analyses]
        need = [r["topic"] for r in rows if r["status"] in ("weakness", "developing")][:3]
        return {"topics": rows, "summary": f"{len(rows)} topics; most in need: {', '.join(need) or 'none'}"}

    def analyse_topic(self, topic):
        analysis = self.o.analyst.analyse(self.player_id, self._topic(topic))
        wrong = [{"question": row["prompt"][:80], "answer_given": row.get("submitted", ""),
                  "misconception": row.get("misconception", "")}
                 for row in self.o.repository.question_history(self.player_id, topic, limit=12)
                 if not row["correct"]][:4]
        data = analysis.to_dict()
        data.update(recent_wrong_answers=wrong,
                    summary=f"{analysis.status}, mastery {analysis.mastery_score}, {analysis.evidence_count} questions")
        return data

    def rule_difficulty(self, topic):
        analysis = self.o.analyst.analyse(self.player_id, topic)
        history = self.o.repository.question_history(self.player_id, topic, limit=1)
        return self.o.difficulty_manager.recommend(analysis, history[0]["difficulty"] if history else "",
                                                   self.o.player_level()).level

    def recommend_difficulty(self, topic):
        analysis = self.o.analyst.analyse(self.player_id, self._topic(topic))
        history = self.o.repository.question_history(self.player_id, topic, limit=1)
        decision = self.o.difficulty_manager.recommend(analysis, history[0]["difficulty"] if history else "",
                                                       self.o.player_level())
        return {"topic": topic, "difficulty": decision.level, "reason": decision.reason,
                "summary": decision.level}

    def quest_ids(self):
        manager = self.o.quest_manager
        if manager is None:
            return list(quests())
        return manager.active() + manager.available()

    def list_quests(self):
        manager, catalogue = self.o.quest_manager, quests()
        active = manager.active() if manager else []
        rows = [{"quest_id": qid, "title": catalogue[qid]["title"], "status": "active" if qid in active else "available",
                 "topics": list(catalogue[qid].get("topics", ()))} for qid in self.quest_ids()]
        return {"quests": rows, "summary": f"{len(rows)} quests"}

    def check_boss_readiness(self):
        analyses = self.o._ordered_analyses(self.player_id)
        ready, advice = self.o.game_master.boss_readiness(analyses[:5], self.party_level, self.seals_done)
        return {"ready": ready, "advice": advice, "summary": "ready" if ready else "not ready"}

    def get_training_spot(self, topic):
        place, monster = TRAINING.get(self._topic(topic), ("Green Meadow", ""))
        return {"topic": topic, "place": place, "monster": monster, "summary": place}
