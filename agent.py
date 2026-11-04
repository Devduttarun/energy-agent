"""The home brain: understand -> plan -> verify -> act -> explain.

- understand (preferences.py): Muse Spark Open turns the household's own words into a plan of
  devices, exact-time commands, keep windows, appliance tasks and a power limit.
- plan: Muse Spark Open turns that into the day's timeline, choosing the cheapest valid time
  for every flexible task from the price forecast.
- verify: plain code (household.check) replays the timeline minute by minute and checks every
  instruction, keep window, task window, the power limit and cost. If anything fails, the
  problems go back to the model for another attempt (up to MAX_ATTEMPTS); if no attempt
  passes, the brain falls back to the literal plan code can build alone.
- act: carries out the verified timeline in the simulated home.
- explain: says what happened and why, with money-saving tips and questions for the household.

The run is saved to runs/latest.json for the dashboard (app.py).
"""
import json
import sys
from pathlib import Path

import household as home
import llm
from llm import ask_spark_open, extract_json

RUNS_DIR = Path(__file__).parent / "runs"
MAX_ATTEMPTS = 3

SYSTEM_PROMPT = """You are the planning brain of a smart home in Singapore. You get the household's
instructions (already structured), the electricity price for every half hour of the day, and the load
the rest of the home already draws. Every device starts the day off (curtains closed).

Plan the day:
- events: every device state change. Include every command exactly as given: same device, same time,
  same state. Where a keep window needs a device in a state it would not otherwise be in, add one event
  at the start of the window (or at 00:00 for a window that wraps past midnight). Add nothing else.
- runs: one start time (HH:MM, a multiple of 5 minutes) for each task. A task with a fixed start must
  start exactly then. A flexible task must start and finish inside its window; choose the cheapest start
  (cost = kW x hours x price), while respecting the device's keep windows and the power limit
  (background load + every device that is on).
- held: tasks for which no start time meets every rule. Only then.

You may think first. Then end your reply with exactly one JSON object on its own line, and nothing after it:
{"events": [{"at": "HH:MM", "device": "<device id>", "state": "<state>"}], "runs": [{"device": "<device id>", "start": "HH:MM"}], "held": ["<device id>"], "reason": "<one short sentence>"}"""


def decide(plan, day, feedback=None):
    """Ask Muse Spark Open for the day's timeline; return the parsed action dict."""
    devices = {d: {"name": v["name"], "kw": v["kw"], "states": list(home.DEVICE_TYPES[v["type"]][3])}
               for d, v in plan["devices"].items()}
    instructions = {k: plan[k] for k in ("commands", "keep", "tasks", "max_household_kw")}
    forecast = "\n".join(f"{home.hhmm(i * 30)}  price {p:.4f} SGD/kWh  background load {b:.2f} kW"
                         for i, (p, b) in enumerate(zip(day["price"], day["background"])))
    user_msg = (f"Devices: {json.dumps(devices)}\n\nInstructions: {json.dumps(instructions)}\n\n"
                f"Each half hour of the day:\n{forecast}")
    if feedback:
        user_msg += ("\n\nYour previous plan failed these checks:\n- " + "\n- ".join(feedback)
                     + "\nPlan again so that every check passes.")
    try:
        answer, reasoning = ask_spark_open(SYSTEM_PROMPT, user_msg)
    except Exception as e:
        return _failed(f"the model call failed ({type(e).__name__})")
    action = parse_action(answer)
    action.update(reasoning=reasoning, model=llm.last_model)
    return action


def parse_action(text):
    """Pull the final plan JSON out of the model's reply."""
    obj = extract_json(text, lambda o: isinstance(o.get("events"), list) and isinstance(o.get("runs"), list))
    if obj is None:
        return _failed("could not read a plan from the model reply")
    held = obj.get("held") if isinstance(obj.get("held"), list) else []
    return {"events": obj["events"], "runs": obj["runs"], "held": [str(h) for h in held],
            "reason": str(obj.get("reason", "")), "source": "model"}


def _failed(reason):
    return {"events": [], "runs": [], "held": [], "reason": reason, "source": "fallback", "failed": True}


def verify(plan, day, action):
    """Check the timeline against every instruction; return it with a list of `problems` (empty = passed).

    These checks are plain code, not the model, so a wrong plan can't slip through.
    """
    if action.get("failed"):
        return {**action, "problems": [action["reason"]]}
    return {**action, "problems": home.check(plan, day, action["events"], action["runs"], action["held"])}


def plan_and_verify(plan, day, inject=None, on_event=None):
    """decide() then verify(); on failure, retry with the problems as feedback. Returns (action, attempts).

    `inject` replaces the model's first answer (the safety drill), so the retry loop can be shown on
    demand. `on_event(kind, data)` reports progress to a live view.
    """
    emit = on_event or (lambda kind, data: None)
    attempts, feedback = [], None
    while True:
        if inject is not None and not attempts:
            action = dict(inject)
        else:
            emit("planning", {"attempt": len(attempts) + 1})
            action = decide(plan, day, feedback=feedback)
        action = verify(plan, day, action)
        attempts.append(action)
        emit("attempt", action)
        if not action["problems"] or action.get("failed") or len(attempts) >= MAX_ATTEMPTS:
            break
        feedback = action["problems"]
    if action["problems"]:
        # Never act on a plan that failed verification: do exactly what was asked, and hold
        # any task that cannot run without breaking a rule.
        events, runs, held = home.literal_day(plan, day)
        action = verify(plan, day, {"events": events, "runs": runs, "held": held, "source": "fallback",
                                    "reason": f"no plan passed verification after {len(attempts)} attempts; "
                                              "doing exactly what you asked"})
    return action, attempts


def drill_action(plan, day):
    """A deliberately wrong plan for the safety drill: a correct one with a single instruction broken.

    Moves an exact-time command 5 minutes early if there is one; otherwise starts a task at the
    wrong time. Returns None when there is nothing to break.
    """
    events, runs, held = home.literal_day(plan, day)
    wrong = None
    command = next((c for c in plan["commands"] if home.to_min(c["at"]) >= 5), None)
    if command:
        wrong = home.hhmm(home.to_min(command["at"]) - 5)
        for e in events:
            if (e["device"], e["at"], e["state"]) == (command["device"], command["at"], command["state"]):
                e["at"] = wrong
                break
        what = f"{plan['devices'][command['device']]['name']} at {wrong} instead of {command['at']}"
    elif runs:
        r = runs[0]
        task = next(t for t in plan["tasks"] if t["device"] == r["device"])
        start = home.to_min(task["start"] or task["earliest"])
        r["start"] = wrong = home.hhmm(start + 30 if start + 30 + task["minutes"] <= home.MINUTES else start - 30)
        what = f"{plan['devices'][r['device']]['name']} starting at {wrong}"
    if wrong is None:
        return None
    return {"events": events, "runs": runs, "held": held, "source": "drill",
            "reason": f"Safety drill: a deliberately wrong plan ({what}) injected to test verify()"}


def act(plan, day, action, baseline):
    """Carry out the verified timeline in the simulated home; return the timeline, series and metrics."""
    sim = home.simulate(plan, day, action["events"], action["runs"])
    base = home.simulate(plan, day, baseline["events"], baseline["runs"])
    devs, tasks = plan["devices"], {t["device"]: t for t in plan["tasks"]}
    timeline = []
    for e in action["events"]:
        on = home.state_on(e["state"])
        c = next((c for c in plan["commands"] if c["device"] == e["device"] and c["at"] == e["at"]
                  and home.state_on(c["state"]) == on), None)
        k = next((k for k in plan["keep"] if k["device"] == e["device"]
                  and home.in_window(home.to_min(e["at"]), k["from"], k["until"])), None)
        why = (f"“{c['quote']}”" if c and c["quote"] else "Exactly when you asked" if c else
               f"Kept {k['state']} until {k['until']}, as you asked" + (f": “{k['quote']}”" if k["quote"] else ""))
        timeline.append(_event(e["at"], e["device"], on, f"{devs[e['device']]['name']} {home.state_word(devs[e['device']], on)}", why))
    for r in action["runs"]:
        t, start = tasks[r["device"]], home.to_min(r["start"])
        if t["start"]:
            why = f"“{t['quote']}”" if t["quote"] else "Exactly when you asked"
        else:
            default = next((x for x in baseline["runs"] if x["device"] == r["device"]), None)
            saved = (home.run_cost(plan, day, r["device"], home.to_min(default["start"]))
                     - home.run_cost(plan, day, r["device"], start)) if default else 0
            why = (f"Cheapest time between {t['earliest']} and {t['finish_by']} that keeps every rule"
                   + (f": saves {saved:.2f} SGD vs switching on at {default['start']}" if saved >= 0.005 else ""))
        name = devs[r["device"]]["name"]
        timeline.append(_event(r["start"], r["device"], True, f"{name} started · {t['minutes']} min", why))
        if start + t["minutes"] < home.MINUTES:
            timeline.append(_event(home.hhmm(start + t["minutes"]), r["device"], False, f"{name} finished",
                                   "Cycle complete"))
    timeline.sort(key=lambda x: x["t"])
    limit = plan["max_household_kw"]
    series = [{"t": m, "at": home.hhmm(m), "load": round(sim["load"][m], 3), "baseline": round(base["load"][m], 3),
               "price": day["price"][m // 30]} for m in range(0, home.MINUTES, home.STEP)]
    over = lambda load: sum(1 for kw in load if limit and kw > limit + 1e-9)  # noqa: E731
    metrics = {
        "cost_sgd": round(home.cost(sim["load"], day), 3), "baseline_cost_sgd": round(home.cost(base["load"], day), 3),
        "device_kwh": round(sum(devs[d]["kw"] / 60 for d, s in sim["on"].items() for v in s if v), 2),
        "peak_kw": round(max(sim["load"]), 2), "baseline_peak_kw": round(max(base["load"]), 2),
        "over_limit_min": over(sim["load"]), "baseline_over_limit_min": over(base["load"]),
        "instructions": home.instruction_count(plan), "held": len(action["held"]),
    }
    metrics["saved_sgd"] = round(max(metrics["baseline_cost_sgd"] - metrics["cost_sgd"], 0), 3)
    intervals = {d: _intervals(s) for d, s in sim["on"].items()}
    return timeline, series, metrics, intervals


def _intervals(series):
    """[start, end) minute ranges in which a device is on."""
    out, start = [], None
    for m, on in enumerate(series + [False]):
        if on and start is None:
            start = m
        elif not on and start is not None:
            out.append([start, m])
            start = None
    return out


def _event(at, device, on, text, why):
    return {"t": home.to_min(at), "at": at, "device": device, "on": on, "text": text, "why": why}


def explain(plan, action, metrics, tips, questions):
    """A plain-language account of the day."""
    kept = metrics["instructions"] - metrics["held"]
    lines = [f"Followed {kept} of your {metrics['instructions']} instructions exactly."]
    saved = metrics["baseline_cost_sgd"] - metrics["cost_sgd"]
    if saved >= 0.005:
        lines.append(f"Saves {saved:.2f} SGD today, about {saved * 365:.0f} SGD a year.")
    for d in action["held"]:
        lines.append(f"Held the {plan['devices'][d]['name']}: no time meets all your rules, so it's your call.")
    if action["source"] == "fallback":
        lines.append("The model's plans didn't pass the checks, so the brain did exactly what you said instead.")
    return " ".join(lines + tips + questions)


def run(plan, drill=False, on_event=None, log_path=RUNS_DIR / "latest.json", as_said=None):
    """Plan, verify, act and explain one day for the household; return (and save) a record of it.

    `as_said` is the plan as the household first said it, before any approved savings options;
    savings are measured against doing that by hand (tasks switched on at once).
    """
    emit = on_event or (lambda kind, data: None)
    day = home.load_day()
    inject = drill_action(plan, day) if drill else None
    action, attempts = plan_and_verify(plan, day, inject=inject, on_event=on_event)
    emit("acting", action)
    said = as_said or plan
    baseline = {"events": home.literal_day(said, day)[0] if as_said else action["events"], "runs": home.naive_runs(said)}
    timeline, series, metrics, intervals = act(plan, day, action, baseline)
    tips, questions = home.tips_and_questions(plan, day, action["events"], action["runs"])
    options = home.savings_options(plan, day, action["events"], action["runs"])
    record = {"plan": plan, "date": day["date"], "drill": inject is not None, "attempts": attempts, "final": action,
              "timeline": timeline, "intervals": intervals, "series": series, "metrics": metrics, "tips": tips, "questions": questions,
              "options": options, "explanation": explain(plan, action, metrics, tips, questions)}
    emit("done", record)
    if log_path:
        log_path.parent.mkdir(exist_ok=True)
        log_path.write_text(json.dumps(record, indent=2))
    return record


def main():
    from preferences import DEFAULT_PREFERENCES, extract_plan

    args = [a for a in sys.argv[1:] if a != "--drill"]
    text = args[0] if args else DEFAULT_PREFERENCES
    print(f"You said: {text}\n")
    plan, _, warnings = extract_plan(text)
    for w in warnings:
        print(f"  note: {w}")
    if not plan:
        return
    print(f"Understood: {plan['summary']}\n")

    def show(kind, data):
        if kind == "attempt":
            print(f"  {data['source']} plan: {'passed' if not data['problems'] else 'REJECTED'}")
            for p in data["problems"]:
                print(f"    - {p}")

    record = run(plan, drill="--drill" in sys.argv, on_event=show)
    print()
    for e in record["timeline"]:
        print(f"  {e['at']}  {e['text']:<36} {e['why']}")
    m = record["metrics"]
    print(f"\nCost today {m['cost_sgd']:.2f} SGD (without the brain {m['baseline_cost_sgd']:.2f}), "
          f"peak {m['peak_kw']} kW\n{record['explanation']}")


if __name__ == "__main__":
    main()
