"""Agent 6, the AI Planner (LLM agent): the tool-use loop, self-correction after a rejected plan,
the rule guard rails, steering the next questions, and safe fallbacks. Claude is replaced by a
scripted fake client, so these tests need no API key or network."""
import random
import tempfile
import unittest
from types import SimpleNamespace

from ai.orchestrator import AgentOrchestrator
from ai.planner_agent import TOOLS, PlannerAgent
from database.database import Database
from database.player_repository import PlayerRepository
from world.quest_manager import QuestManager


def tool_use(name, args, call_id):
    return SimpleNamespace(type="tool_use", name=name, input=args, id=call_id)


def reply(*blocks, stop="tool_use"):
    return SimpleNamespace(content=list(blocks), stop_reason=stop)


class FakeClaude:
    """Plays back scripted responses and records every request the agent sends."""

    def __init__(self, responses):
        self.responses, self.requests = list(responses), []
        self.messages = self

    def create(self, **request):
        self.requests.append(dict(request, messages=list(request["messages"])))
        return self.responses.pop(0)


class FakeProvider:
    available, model = True, "test-model"

    def __init__(self, client=None):
        self.client = client

    def _client(self):
        return self.client

    @property
    def executor(self):
        return SimpleNamespace(submit=lambda fn, *args: _ran(fn, *args))


def _ran(fn, *args):
    from concurrent.futures import Future
    future = Future()
    future.set_result(fn(*args))
    return future


GOOD_PLAN = {"focus_topic": "fractions", "difficulty": "foundation", "quest_id": "",
             "objectives": ["Answer 5 fraction questions."], "message": "Let's build your fraction skills together!",
             "reasoning": "Fractions has the least evidence."}


class PlannerTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.repository = PlayerRepository(Database(self.folder.name + "/p.sqlite3"))
        self.player_id = self.repository.create_player("Ada", "CHRONOX")
        self.orchestrator = AgentOrchestrator(self.repository, rng=random.Random(1))
        self.orchestrator.quest_manager = QuestManager(self.repository, self.player_id)

    def tearDown(self):
        self.folder.cleanup()

    def planner(self, responses):
        client = FakeClaude(responses)
        provider = FakeProvider(client)
        self.orchestrator.llm = provider
        self.orchestrator.planner = PlannerAgent(self.orchestrator, provider)
        return self.orchestrator.planner, client

    def test_claude_chooses_tools_and_corrects_a_rejected_plan(self):
        planner, client = self.planner([
            reply(tool_use("get_learning_overview", {}, "a")),
            reply(tool_use("analyse_topic", {"topic": "fractions"}, "b"),
                  tool_use("recommend_difficulty", {"topic": "fractions"}, "c")),
            reply(tool_use("submit_plan", dict(GOOD_PLAN, difficulty="mastery"), "d")),   # too hard -> rejected
            reply(tool_use("submit_plan", GOOD_PLAN, "e")),
        ])
        plan = planner.plan(self.player_id, 3, False)
        self.assertIsNotNone(plan)
        self.assertEqual(plan.focus_topic, "fractions")
        self.assertEqual(plan.tool_calls, ["get_learning_overview", "analyse_topic", "recommend_difficulty",
                                           "submit_plan", "submit_plan"])
        self.assertTrue(any("REJECTED" in line for line in plan.trace))
        # Claude really received the tool results (and the rejection reason) between turns.
        last = client.requests[-1]["messages"]
        rejection = last[-1]["content"][0]
        self.assertTrue(rejection["is_error"])
        self.assertIn("too far", rejection["content"])
        self.assertEqual({tool["name"] for tool in client.requests[0]["tools"]}, {t["name"] for t in TOOLS})

    def test_plan_without_looking_at_data_unknown_quest_and_unsafe_text_are_rejected(self):
        planner, client = self.planner([
            reply(tool_use("submit_plan", GOOD_PLAN, "a")),                                     # no evidence yet
            reply(tool_use("list_quests", {}, "b")),
            reply(tool_use("submit_plan", dict(GOOD_PLAN, quest_id="not_a_quest"), "c")),
            reply(tool_use("submit_plan", dict(GOOD_PLAN, message="Don't be lazy."), "d")),
            reply(tool_use("submit_plan", GOOD_PLAN, "e")),
        ])
        plan = planner.plan(self.player_id)
        self.assertIsNotNone(plan)
        self.assertEqual(sum("REJECTED" in line for line in plan.trace), 3)

    def test_accepted_plan_is_logged_and_steers_the_next_questions(self):
        planner, _ = self.planner([
            reply(tool_use("get_learning_overview", {}, "a")),
            reply(tool_use("submit_plan", GOOD_PLAN, "b")),
        ])
        future = self.orchestrator.start_planning(self.player_id, 2, False)
        decision = self.orchestrator.apply_plan(self.player_id, future.result(), steer_questions=2)
        self.assertIn("ai_planner", decision.agents)
        self.assertIn("learning_analyst", decision.agents)
        logged = self.repository.recent_decisions(self.player_id, 5, "agent_plan")
        self.assertEqual(len(logged), 1)
        topics = [self.orchestrator.request_question(self.player_id, topics=("addition", "fractions")).question.topic
                  for _ in range(3)]
        self.assertEqual(topics[:2], ["fractions", "fractions"])
        # A monster's own topic (affinity) always wins over the plan.
        self.assertEqual(self.orchestrator.request_question(self.player_id, "addition").question.topic, "addition")

    def test_failures_fall_back_to_the_rules(self):
        planner, _ = self.planner([reply(SimpleNamespace(type="text", text="Hmm."), stop="end_turn")] * 6)
        self.assertIsNone(planner.plan(self.player_id))           # never submitted a plan
        broken = FakeClaude([])                                   # raises IndexError on the first call
        self.assertIsNone(PlannerAgent(self.orchestrator, FakeProvider(broken)).plan(self.player_id))
        offline = AgentOrchestrator(self.repository, rng=random.Random(1))
        self.assertIsNone(offline.start_planning(self.player_id).result())   # no API key -> no plan

    def test_bad_tool_arguments_are_reported_back_not_crashed(self):
        planner, client = self.planner([
            reply(tool_use("analyse_topic", {"topic": "astrology"}, "a")),
            reply(tool_use("get_learning_overview", {}, "b")),
            reply(tool_use("submit_plan", GOOD_PLAN, "c")),
        ])
        plan = planner.plan(self.player_id)
        self.assertIsNotNone(plan)
        self.assertTrue(client.requests[1]["messages"][-1]["content"][0]["is_error"])


if __name__ == "__main__":
    unittest.main()
