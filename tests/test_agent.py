"""Offline tests: the model is mocked, so no API calls are made.

Run with: .venv/bin/python -m unittest discover tests
"""
import json
import os
import sys
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.environ.setdefault("BASETEN_API_KEY", "test-not-a-real-key")
os.environ.setdefault("META_API_KEY", "test-not-a-real-key")

import agent  # noqa: E402
import household as home  # noqa: E402
from llm import extract_json  # noqa: E402

DAY = home.load_day()

MORNING = {  # what the model returns for the default morning routine
    "devices": [{"id": "lights", "name": "Lights", "type": "light", "kw": 0.1},
                {"id": "curtains", "name": "Curtains", "type": "curtains", "kw": 0},
                {"id": "toilet", "name": "Toilet seat heater", "type": "heater", "kw": 0.4},
                {"id": "washer", "name": "Washing machine", "type": "washing_machine", "kw": 0.6}],
    "commands": [{"device": "lights", "at": "07:00", "state": "on", "quote": "lights on exactly at 7 am"},
                 {"device": "curtains", "at": "07:00", "state": "open", "quote": "curtains must open"},
                 {"device": "toilet", "at": "07:05", "state": "on", "quote": "heat up at 7:05 am"},
                 {"device": "lights", "at": "21:30", "state": "on", "quote": "After 9:30pm"}],
    "keep": [{"device": "lights", "from": "07:30", "until": "21:00", "state": "closed", "quote": "keep the lights closed"}],
    "tasks": [{"device": "washer", "minutes": 60, "start": "07:30", "quote": "I wash the clothes at 7:30 am"}],
    "max_household_kw": None, "summary": "Morning routine",
}
LAUNDRY = {  # a flexible task: the brain chooses the time
    "devices": [{"id": "dryer", "name": "Tumble dryer", "type": "dryer", "kw": 2.0}],
    "commands": [], "keep": [{"device": "dryer", "from": "21:00", "until": "22:30", "state": "off"}],
    "tasks": [{"device": "dryer", "minutes": 60, "earliest": "20:00", "finish_by": "24:00"}],
    "max_household_kw": 4.0, "summary": "Dryer tonight",
}


def plan_of(raw):
    plan, warnings = home.validate_plan(raw)
    return plan


def reply(events, runs, held=(), reason="test"):
    return ("thinking...\n" + json.dumps({"events": events, "runs": runs, "held": list(held), "reason": reason}),
            "reasoning text")


def good_morning():
    events, runs, _ = home.literal_day(plan_of(MORNING), DAY)
    return events, runs


class PlanValidationTests(unittest.TestCase):
    def test_closed_lights_mean_off_and_all_items_kept(self):
        plan, warnings = home.validate_plan(MORNING)
        self.assertEqual(warnings, [])
        self.assertEqual(plan["keep"][0]["state"], "off")
        self.assertEqual(home.instruction_count(plan), 6)

    def test_bad_items_dropped_with_warnings(self):
        raw = dict(MORNING, commands=[{"device": "lights", "at": "7am", "state": "on"},
                                      {"device": "ghost", "at": "07:00", "state": "on"},
                                      {"device": "lights", "at": "07:00", "state": "purple"}],
                   max_household_kw=500)
        plan, warnings = home.validate_plan(raw)
        self.assertEqual(plan["commands"], [])
        self.assertIsNone(plan["max_household_kw"])
        self.assertEqual(len(warnings), 4)

    def test_keep_window_clashing_with_command_is_dropped(self):
        raw = dict(MORNING, keep=[{"device": "lights", "from": "06:00", "until": "21:00", "state": "off"}])
        plan, warnings = home.validate_plan(raw)
        self.assertEqual(plan["keep"], [])
        self.assertIn("clashes", warnings[0])

    def test_extract_plan_reads_model_reply(self):
        with mock.patch("preferences.ask_spark_open", return_value=("ok\n" + json.dumps(MORNING), "r")):
            from preferences import extract_plan
            plan, _, warnings = extract_plan("x")
        self.assertEqual((len(plan["commands"]), warnings), (4, []))


class CheckTests(unittest.TestCase):
    def test_literal_day_passes(self):
        for raw in (MORNING, LAUNDRY):
            plan = plan_of(raw)
            events, runs, held = home.literal_day(plan, DAY)
            self.assertEqual(home.check(plan, DAY, events, runs, held), [])

    def test_command_five_minutes_off_is_caught(self):
        plan, (events, runs) = plan_of(MORNING), good_morning()
        events = [dict(e, at="07:00") if e["device"] == "toilet" else e for e in events]
        problems = home.check(plan, DAY, events, runs, [])
        self.assertIn("You asked for Toilet seat heater on at 07:05. The plan does it at 07:00.", problems)

    def test_unrequested_action_is_caught(self):
        plan, (events, runs) = plan_of(MORNING), good_morning()
        problems = home.check(plan, DAY, events + [{"at": "12:00", "device": "curtains", "state": "closed"}], runs, [])
        self.assertTrue(any("didn't ask for" in p for p in problems))

    def test_keep_window_broken_when_lights_never_switch_off(self):
        plan, (events, runs) = plan_of(MORNING), good_morning()
        events = [e for e in events if not (e["device"] == "lights" and e["state"] == "off")]
        problems = home.check(plan, DAY, events, runs, [])
        self.assertTrue(any("keep the Lights off from 07:30 to 21:00" in p for p in problems))

    def test_fixed_task_at_wrong_time(self):
        plan, (events, _) = plan_of(MORNING), good_morning()
        problems = home.check(plan, DAY, events, [{"device": "washer", "start": "02:30"}], [])
        self.assertTrue(any("start the Washing machine at 07:30" in p for p in problems))

    def test_flexible_task_window_keep_limit_and_cost(self):
        plan = plan_of(LAUNDRY)
        check = lambda start: home.check(plan, DAY, [], [{"device": "dryer", "start": start}], [])  # noqa: E731
        self.assertTrue(any("must run between" in p for p in check("23:30")))
        self.assertTrue(any("keep the Tumble dryer off" in p for p in check("21:00")))
        self.assertTrue(any("above your 4 kW limit" in p for p in check("20:00")))
        self.assertEqual(check("23:00"), [])
        free = plan_of(dict(LAUNDRY, keep=[], max_household_kw=None))  # default time 20:00
        self.assertTrue(any("more than at 20:00" in p
                            for p in home.check(free, DAY, [], [{"device": "dryer", "start": "22:00"}], [])))

    def test_hold_only_when_nothing_works(self):
        plan = plan_of(LAUNDRY)
        self.assertTrue(any("could run at" in p for p in home.check(plan, DAY, [], [], ["dryer"])))
        tight = plan_of(dict(LAUNDRY, max_household_kw=2.0))
        self.assertEqual(home.check(tight, DAY, [], [], ["dryer"]), [])

    def test_wrapping_keep_on_window_needs_midnight_event(self):
        raw = {"devices": [{"id": "ac", "name": "AC", "type": "air_conditioner"}], "commands": [], "tasks": [],
               "keep": [{"device": "ac", "from": "22:00", "until": "06:00", "state": "on"}], "summary": "s"}
        plan = plan_of(raw)
        events, runs, held = home.literal_day(plan, DAY)
        self.assertEqual(home.check(plan, DAY, events, runs, held), [])
        self.assertTrue(any("would be off at 00:00" in p
                            for p in home.check(plan, DAY, [{"at": "22:00", "device": "ac", "state": "on"}], [], [])))

    def test_tips_and_questions(self):
        plan, (events, runs) = plan_of(MORNING), good_morning()
        tips, questions = home.tips_and_questions(plan, DAY, events, runs)
        self.assertIn("You asked for 07:30, so it stays", tips[0])
        self.assertTrue(questions and "Toilet seat heater stays on from 07:05" in questions[0])


class SavingsTests(unittest.TestCase):
    def test_options_offer_heater_off_and_cheaper_wash(self):
        plan, (events, runs) = plan_of(MORNING), good_morning()
        options = home.savings_options(plan, DAY, events, runs)
        kinds = {(o["kind"], o["device"]) for o in options}
        self.assertEqual(kinds, {("off", "toilet"), ("move", "washer")})
        self.assertTrue(all(o["saving_sgd"] > 0 for o in options))

    def test_approved_option_saves_against_plan_as_said(self):
        plan = plan_of(MORNING)
        heater = next(o for o in home.savings_options(plan, DAY, *good_morning()) if o["device"] == "toilet")
        better = home.apply_option(plan, heater)
        self.assertEqual(len(plan["commands"]) + 1, len(better["commands"]))  # original untouched
        events, runs, held = home.literal_day(better, DAY)
        self.assertEqual(home.check(better, DAY, events, runs, held), [])
        with mock.patch.object(agent, "ask_spark_open", return_value=reply(events, runs)):
            record = agent.run(better, log_path=None, as_said=plan)
        self.assertAlmostEqual(record["metrics"]["saved_sgd"], heater["saving_sgd"], places=2)
        self.assertNotIn("toilet", {o["device"] for o in record["options"]})


class LoopTests(unittest.TestCase):
    def test_retry_with_feedback_then_pass(self):
        plan, (events, runs) = plan_of(MORNING), good_morning()
        wrong = [dict(e, at="07:00") if e["device"] == "toilet" else e for e in events]
        with mock.patch.object(agent, "ask_spark_open", side_effect=[reply(wrong, runs), reply(events, runs)]) as ask:
            action, attempts = agent.plan_and_verify(plan, DAY)
        self.assertEqual(len(attempts), 2)
        self.assertIn("07:05", ask.call_args_list[1].args[1])  # the rejection reached the model
        self.assertEqual((action["problems"], action["source"]), ([], "model"))

    def test_falls_back_to_literal_plan_after_max_attempts(self):
        plan = plan_of(MORNING)
        with mock.patch.object(agent, "ask_spark_open", return_value=reply([], [])):
            action, attempts = agent.plan_and_verify(plan, DAY)
        self.assertEqual(len(attempts), agent.MAX_ATTEMPTS)
        self.assertEqual((action["source"], action["problems"]), ("fallback", []))

    def test_api_error_falls_back(self):
        plan = plan_of(LAUNDRY)
        with mock.patch.object(agent, "ask_spark_open", side_effect=TimeoutError):
            action, attempts = agent.plan_and_verify(plan, DAY)
        self.assertEqual((len(attempts), action["source"], action["runs"]), (1, "fallback", [{"device": "dryer", "start": "22:30"}]))

    def test_drill_rejected_then_model_corrects(self):
        plan, (events, runs) = plan_of(MORNING), good_morning()
        inject = agent.drill_action(plan, DAY)
        seen = []
        with mock.patch.object(agent, "ask_spark_open", return_value=reply(events, runs)) as ask:
            action, attempts = agent.plan_and_verify(plan, DAY, inject=inject, on_event=lambda k, d: seen.append(k))
        self.assertEqual(attempts[0]["source"], "drill")
        self.assertIn("The plan does it at 06:55", attempts[0]["problems"][0])
        self.assertIn("06:55", ask.call_args.args[1])
        self.assertEqual((len(attempts), action["problems"], seen), (2, [], ["attempt", "planning", "attempt"]))

    def test_drill_breaks_a_flexible_task_when_no_commands(self):
        plan = plan_of(LAUNDRY)
        inject = agent.verify(plan, DAY, agent.drill_action(plan, DAY))
        self.assertTrue(inject["problems"])

    def test_run_records_timeline_and_savings(self):
        plan = plan_of(LAUNDRY)
        with mock.patch.object(agent, "ask_spark_open",
                               return_value=reply([], [{"device": "dryer", "start": "23:00"}])):
            record = agent.run(plan, log_path=None)
        m = record["metrics"]
        self.assertLess(m["cost_sgd"], m["baseline_cost_sgd"])
        self.assertEqual([e["text"] for e in record["timeline"]], ["Tumble dryer started · 60 min"])
        self.assertIn("saves", record["timeline"][0]["why"])
        self.assertEqual(m["over_limit_min"], 0)


class ParsingTests(unittest.TestCase):
    def test_ignores_answers_inside_think_block(self):
        text = '<think>{"action": "shift_load"}</think>\n{"action": "no_action", "reason": "x"}'
        self.assertEqual(extract_json(text, lambda o: "action" in o)["action"], "no_action")

    def test_unparseable_reply_is_safe(self):
        action = agent.verify(plan_of(MORNING), DAY, agent.parse_action("no json here"))
        self.assertEqual((action["source"], len(action["problems"])), ("fallback", 1))


if __name__ == "__main__":
    unittest.main()
