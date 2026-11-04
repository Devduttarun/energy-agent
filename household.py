"""Simulated home: the household's devices, one day of prices and background load, and the plan checks.

The home brain (agent.py) plans a day of device actions. This module plays that plan
minute by minute and checks it against what the household asked for:
- commands: a device set to a state at an exact time ("lights on at 07:00"),
- keep windows: a device held in a state between two times ("lights off until 21:00",
  "no dryer between midnight and 6am"),
- tasks: an appliance cycle, either at a fixed start ("wash at 7:30") or anywhere in a
  window ("dry by midnight"), where the brain picks the cheapest time,
- a whole-home power limit.

Prices and the load of the rest of the home come from the first day of data.csv.
Every problem is written in plain language, because it is shown to the household and
sent back to the model as feedback.
"""
import copy
import csv
import re
from pathlib import Path

DATA_PATH = Path(__file__).parent / "data.csv"
MINUTES = 24 * 60
STEP = 5  # flexible tasks start on 5-minute boundaries
DRYER_IN_DATA = (41, 43, 2.0)  # data.csv day 1 includes a 2 kW dryer at 20:30-21:30; managed devices replace it

# type: (default name, icon, kW while on, (on-state, off-state), typical cycle minutes or None)
DEVICE_TYPES = {
    "light": ("Lights", "💡", 0.1, ("on", "off"), None),
    "curtains": ("Curtains", "🪟", 0.0, ("open", "closed"), None),
    "heater": ("Heater", "🔥", 0.8, ("on", "off"), None),
    "water_heater": ("Water heater", "🚿", 3.0, ("on", "off"), 30),
    "washing_machine": ("Washing machine", "🧺", 0.6, ("on", "off"), 60),
    "dryer": ("Tumble dryer", "🌀", 2.0, ("on", "off"), 60),
    "dishwasher": ("Dishwasher", "🍽️", 1.2, ("on", "off"), 90),
    "air_conditioner": ("Air conditioner", "❄️", 1.2, ("on", "off"), None),
    "fan": ("Fan", "🌬️", 0.05, ("on", "off"), None),
    "ev_charger": ("EV charger", "🚗", 7.0, ("on", "off"), 120),
    "kitchen": ("Kitchen appliance", "☕", 1.5, ("on", "off"), 15),
    "tv": ("TV", "📺", 0.12, ("on", "off"), None),
    "vacuum": ("Robot vacuum", "🤖", 0.04, ("on", "off"), 60),
    "other": ("Appliance", "🔌", 0.5, ("on", "off"), None),
}
ON_WORDS = {"on", "open", "opened", "start", "started", "run", "running", "heat", "heating"}
OFF_WORDS = {"off", "closed", "close", "shut", "stop", "stopped"}
HHMM = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")
LONG_ON_MIN = 4 * 60  # a device left on this long with no instruction to switch it off gets a question
AUTO_OFF_MIN = {"heater": 30, "light": 60, "tv": 120, "air_conditioner": 480}  # suggested on-time before switching off


def to_min(t):
    return 1440 if t == "24:00" else int(t[:2]) * 60 + int(t[3:5])


def hhmm(minute):
    return f"{minute // 60:02d}:{minute % 60:02d}"


def time_ok(t, end=False):
    """HH:MM within the day; "24:00" (end of the day) only where `end` allows it."""
    return isinstance(t, str) and (bool(HHMM.match(t)) or (end and t == "24:00"))


def slug(text):
    return re.sub(r"[^a-z0-9]+", "_", str(text).lower()).strip("_")[:40] or "device"


def state_on(word):
    """True for on/open/start, False for off/closed/stop, None if not a state."""
    word = str(word).strip().lower()
    return True if word in ON_WORDS else False if word in OFF_WORDS else None


def state_word(device, on):
    return DEVICE_TYPES[device["type"]][3][0 if on else 1]


def in_window(m, start, end):
    """Minute m inside [start, end), with windows allowed to wrap past midnight."""
    s, e = to_min(start), to_min(end)
    return s <= m < e if s < e else (m >= s or m < e)


def window_minutes(start, end):
    return [m for m in range(MINUTES) if in_window(m, start, end)]


def load_day(path=DATA_PATH):
    """Half-hourly price and background load (the rest of the home) for the first day of data.csv."""
    rows = list(csv.DictReader(path.open(newline="")))[:48]
    background = [float(r["household_load_kw"]) for r in rows]
    first, last, kw = DRYER_IN_DATA
    for i in range(first, last):
        background[i] = max(0.15, background[i] - kw)
    return {"date": rows[0]["timestamp"][:10], "price": [float(r["grid_price_per_kwh"]) for r in rows],
            "background": background}


# Plan validation ----------------------------------------------------------------------
def validate_plan(raw):
    """Keep only well-formed plan items; return (plan, warnings). Nothing the model gets wrong is trusted."""
    warnings, devices = [], {}
    for d in raw.get("devices") or []:
        if not isinstance(d, dict) or not str(d.get("name") or "").strip():
            warnings.append(f"ignored a device without a name: {d!r}")
            continue
        kind = d.get("type") if d.get("type") in DEVICE_TYPES else "other"
        kw = d.get("kw")
        kw = float(kw) if isinstance(kw, (int, float)) and 0 <= kw <= 22 else DEVICE_TYPES[kind][2]
        devices[slug(d.get("id") or d["name"])] = {"name": str(d["name"])[:40], "type": kind, "kw": kw}

    def device_of(item):
        dev = slug(item.get("device", "")) if isinstance(item, dict) else None
        return dev if dev in devices else None

    def quote(item):
        q = item.get("quote")
        return str(q)[:160] if isinstance(q, str) and q.strip() else None

    commands = []
    for c in raw.get("commands") or []:
        dev = device_of(c)
        on = state_on(c.get("state")) if dev else None
        if on is None or not time_ok(c.get("at")):
            warnings.append(f"ignored a command I couldn't read: {c!r}")
            continue
        commands.append({"device": dev, "at": c["at"], "state": state_word(devices[dev], on), "quote": quote(c)})

    keep = []
    for k in raw.get("keep") or []:
        dev = device_of(k)
        on = state_on(k.get("state")) if dev else None
        if on is None or not time_ok(k.get("from")) or not time_ok(k.get("until"), end=True) \
                or to_min(k["from"]) == to_min(k["until"]) % MINUTES:
            warnings.append(f"ignored a keep rule I couldn't read: {k!r}")
            continue
        keep.append({"device": dev, "from": k["from"], "until": k["until"],
                     "state": state_word(devices[dev], on), "quote": quote(k)})

    tasks = []
    for t in raw.get("tasks") or []:
        dev = device_of(t)
        if dev is None or any(x["device"] == dev for x in tasks):
            warnings.append(f"ignored a task I couldn't read (or a second task for one device): {t!r}")
            continue
        minutes = t.get("minutes")
        minutes = int(minutes) if isinstance(minutes, (int, float)) and 5 <= minutes <= 720 \
            else DEVICE_TYPES[devices[dev]["type"]][4] or 60
        start = t.get("start") if time_ok(t.get("start")) else None
        earliest = t.get("earliest") if time_ok(t.get("earliest")) else "00:00"
        finish_by = t.get("finish_by") if time_ok(t.get("finish_by"), end=True) else "24:00"
        if start and to_min(start) + minutes > MINUTES:
            warnings.append(f"ignored {devices[dev]['name']}: starting at {start} it would run past midnight")
            continue
        if not start and to_min(earliest) + minutes > to_min(finish_by):
            warnings.append(f"ignored {devices[dev]['name']}: {minutes} min doesn't fit between {earliest} and {finish_by}")
            continue
        tasks.append({"device": dev, "minutes": minutes, "start": start, "quote": quote(t),
                      "earliest": None if start else earliest, "finish_by": None if start else finish_by})

    # A command inside a keep window that sets the opposite state is a clash the household must resolve.
    for k in list(keep):
        clash = next((c for c in commands if c["device"] == k["device"] and c["state"] != k["state"]
                      and in_window(to_min(c["at"]), k["from"], k["until"])), None)
        if clash:
            keep.remove(k)
            name = devices[k["device"]]["name"]
            warnings.append(f"“keep {name} {k['state']} {k['from']}–{k['until']}” clashes with "
                            f"“{name} {clash['state']} at {clash['at']}”, so the exact-time instruction wins")

    limit = raw.get("max_household_kw")
    if limit is not None and not (isinstance(limit, (int, float)) and 1 <= limit <= 30):
        warnings.append(f"ignored power limit {limit!r}")
        limit = None
    used = {x["device"] for x in commands + keep + tasks}
    plan = {"devices": {d: v for d, v in devices.items() if d in used}, "commands": commands, "keep": keep,
            "tasks": tasks, "max_household_kw": float(limit) if limit else None,
            "limit_quote": quote({"quote": raw.get("limit_quote")}) if limit else None,
            "summary": str(raw.get("summary") or "")[:300]}
    if not used:
        warnings.append("I couldn't find anything to schedule in what you said")
    return plan, warnings


def instruction_count(plan):
    return len(plan["commands"]) + len(plan["keep"]) + len(plan["tasks"]) + (1 if plan["max_household_kw"] else 0)


# Simulation ---------------------------------------------------------------------------
def simulate(plan, day, events, runs):
    """Per-minute on/off state of every device and the whole home's load. Devices start the day off."""
    changes = {d: {} for d in plan["devices"]}
    for e in events:
        changes[e["device"]][to_min(e["at"])] = state_on(e["state"])
    tasks = {t["device"]: t for t in plan["tasks"]}
    for r in runs:
        start = to_min(r["start"])
        changes[r["device"]][start] = True
        if start + tasks[r["device"]]["minutes"] < MINUTES:
            changes[r["device"]][start + tasks[r["device"]]["minutes"]] = False
    on = {}
    for d, ch in changes.items():
        cur, series = False, []
        for m in range(MINUTES):
            cur = ch.get(m, cur)
            series.append(cur)
        on[d] = series
    load = [day["background"][m // 30] + sum(plan["devices"][d]["kw"] for d in on if on[d][m])
            for m in range(MINUTES)]
    return {"on": on, "load": load}


def cost(load, day):
    return sum(kw / 60 * day["price"][m // 30] for m, kw in enumerate(load))


def run_cost(plan, day, device, start):
    kw, minutes = plan["devices"][device]["kw"], next(t["minutes"] for t in plan["tasks"] if t["device"] == device)
    return sum(kw / 60 * day["price"][m // 30] for m in range(start, min(start + minutes, MINUTES)))


def valid_starts(plan, day, device, base_load, anywhere=False):
    """Every start (minute) at which a task breaks no keep window or the power limit, given the other load.

    `anywhere` ignores the task's own time and window (used for money-saving tips).
    """
    task = next(t for t in plan["tasks"] if t["device"] == device)
    kw, n, limit = plan["devices"][device]["kw"], task["minutes"], plan["max_household_kw"]
    if anywhere:
        starts = range(0, MINUTES - n + 1, STEP)
    elif task["start"]:
        starts = [to_min(task["start"])]
    else:
        starts = range(to_min(task["earliest"]), to_min(task["finish_by"]) - n + 1, STEP)
    blocked = [k for k in plan["keep"] if k["device"] == device and not state_on(k["state"])]
    return [s for s in starts
            if not any(in_window(m, k["from"], k["until"]) for k in blocked for m in range(s, s + n))
            and not (limit and any(base_load[m] + kw > limit + 1e-9 for m in range(s, s + n)))]


def load_without(plan, day, events, runs, device):
    return simulate(plan, day, events, [r for r in runs if r["device"] != device])["load"]


# Checks -------------------------------------------------------------------------------
def check(plan, day, events, runs, held):
    """Every way a proposed day breaks the household's instructions, in plain language (empty = passed)."""
    devs, problems = plan["devices"], []
    name = lambda d: devs[d]["name"]  # noqa: E731
    good_events = []
    for e in events:
        if not isinstance(e, dict) or e.get("device") not in devs or state_on(e.get("state")) is None \
                or not time_ok(e.get("at")):
            problems.append(f"The plan contains an action that can't be carried out: {e!r}")
        else:
            good_events.append(e)

    for c in plan["commands"]:
        want = state_on(c["state"])
        if not any(e["device"] == c["device"] and e["at"] == c["at"] and state_on(e["state"]) == want
                   for e in good_events):
            near = [e["at"] for e in good_events if e["device"] == c["device"] and state_on(e["state"]) == want]
            problems.append(f"You asked for {name(c['device'])} {c['state']} at {c['at']}. "
                            + (f"The plan does it at {near[0]}." if near else "The plan never does it."))
    for e in good_events:
        on = state_on(e["state"])
        asked = any(c["device"] == e["device"] and c["at"] == e["at"] and state_on(c["state"]) == on
                    for c in plan["commands"])
        needed = any(k["device"] == e["device"] and state_on(k["state"]) == on
                     and in_window(to_min(e["at"]), k["from"], k["until"]) for k in plan["keep"])
        if not (asked or needed):
            problems.append(f"The plan sets {name(e['device'])} {state_word(devs[e['device']], on)} "
                            f"at {e['at']}, which you didn't ask for.")

    tasks, good_runs = {t["device"]: t for t in plan["tasks"]}, []
    for r in runs:
        t = tasks.get(r.get("device")) if isinstance(r, dict) else None
        if t is None or not time_ok(r.get("start")):
            problems.append(f"The plan runs something that isn't one of your tasks: {r!r}")
            continue
        if any(g["device"] == t["device"] for g in good_runs):
            problems.append(f"The plan runs the {name(t['device'])} more than once.")
            continue
        start = to_min(r["start"])
        if t["start"] and r["start"] != t["start"]:
            problems.append(f"You asked to start the {name(t['device'])} at {t['start']}. "
                            f"The plan starts it at {r['start']}.")
        elif not t["start"] and (start < to_min(t["earliest"]) or start + t["minutes"] > to_min(t["finish_by"])):
            problems.append(f"The {name(t['device'])} must run between {t['earliest']} and {t['finish_by']}, "
                            f"but the plan runs it {r['start']}–{hhmm(start + t['minutes'])}.")
        good_runs.append(r)
    ran = {r["device"] for r in good_runs}
    for d in tasks:
        if d not in ran and d not in held:
            problems.append(f"The plan never runs the {name(d)}.")

    sim = simulate(plan, day, good_events, good_runs)
    for k in plan["keep"]:
        want = state_on(k["state"])
        bad = [m for m in window_minutes(k["from"], k["until"]) if sim["on"][k["device"]][m] != want]
        if bad:
            problems.append(f"You asked to keep the {name(k['device'])} {k['state']} from {k['from']} to "
                            f"{k['until']}, but it would be {state_word(devs[k['device']], not want)} "
                            f"at {hhmm(bad[0])}.")
    limit = plan["max_household_kw"]
    if limit:
        # Only minutes where a managed device adds to the load: the rest of the home is outside the brain's control.
        over = [m for m, kw in enumerate(sim["load"]) if kw > limit + 1e-9
                and any(sim["on"][d][m] and devs[d]["kw"] > 0 for d in devs)]
        if over:
            peak = max(over, key=lambda m: sim["load"][m])
            problems.append(f"The home would draw {sim['load'][peak]:.2f} kW at {hhmm(peak)}, "
                            f"above your {limit:g} kW limit.")

    for d in held:
        if d not in tasks:
            problems.append(f"The plan skips {d!r}, which isn't one of your tasks.")
        elif d in ran:
            problems.append(f"The plan both runs and skips the {name(d)}.")
        else:
            ok = valid_starts(plan, day, d, load_without(plan, day, good_events, good_runs, d))
            if ok:
                problems.append(f"The plan skips the {name(d)}, but it could run at {hhmm(ok[0])} "
                                "without breaking any of your rules.")
    for r in good_runs:
        t = tasks[r["device"]]
        if t["start"]:
            continue
        ok = valid_starts(plan, day, r["device"], load_without(plan, day, good_events, good_runs, r["device"]))
        if ok and run_cost(plan, day, r["device"], to_min(r["start"])) > run_cost(plan, day, r["device"], ok[0]) + 1e-9:
            problems.append(f"Starting the {name(r['device'])} at {r['start']} costs "
                            f"{run_cost(plan, day, r['device'], to_min(r['start'])):.3f} SGD, more than at "
                            f"{hhmm(ok[0])} ({run_cost(plan, day, r['device'], ok[0]):.3f} SGD).")
    return problems


def literal_day(plan, day):
    """The safe plan code can build alone: commands as given, keep windows enforced from their start,
    fixed tasks at their time, flexible tasks at their earliest valid time; anything impossible is held."""
    events = [{"at": c["at"], "device": c["device"], "state": c["state"]} for c in plan["commands"]]
    task_devices = {t["device"] for t in plan["tasks"]}
    for k in plan["keep"]:
        if k["device"] in task_devices:
            continue  # tasks are placed around keep windows instead
        events.append({"at": k["from"], "device": k["device"], "state": k["state"]})
        if state_on(k["state"]) and to_min(k["from"]) > to_min(k["until"]):
            # Devices start the day off, so a window that wraps past midnight also needs switching on at 00:00.
            events.append({"at": "00:00", "device": k["device"], "state": k["state"]})
    runs, held = [], []
    for t in plan["tasks"]:
        ok = valid_starts(plan, day, t["device"], simulate(plan, day, events, runs)["load"])
        if ok:
            runs.append({"device": t["device"], "start": hhmm(ok[0])})
        else:
            held.append(t["device"])
    return events, runs, held


# After the day ------------------------------------------------------------------------
def naive_runs(plan):
    """What the household would do without the brain: every task switched on at its start, or at the
    start of its window, ignoring keep windows and the power limit. Used as the comparison baseline."""
    return [{"device": t["device"], "start": t["start"] or t["earliest"]} for t in plan["tasks"]]


def tips_and_questions(plan, day, events, runs):
    """Money-saving tips for fixed-time tasks, and questions about devices left on with no end time."""
    tips, questions = [], []
    for r in runs:
        t = next(x for x in plan["tasks"] if x["device"] == r["device"])
        if not t["start"]:
            continue
        ok = valid_starts(plan, day, r["device"], load_without(plan, day, events, runs, r["device"]), anywhere=True)
        if not ok:
            continue
        best = min(ok, key=lambda s: run_cost(plan, day, r["device"], s))
        saving = run_cost(plan, day, r["device"], to_min(r["start"])) - run_cost(plan, day, r["device"], best)
        if saving >= 0.01:
            tips.append(f"Starting the {plan['devices'][r['device']]['name']} at {hhmm(best)} instead of "
                        f"{r['start']} would save {saving:.2f} SGD a day. You asked for {r['start']}, so it stays.")
    sim = simulate(plan, day, events, runs)
    kept_on = {k["device"] for k in plan["keep"] if state_on(k["state"])}
    for d, series in sim["on"].items():
        if d in kept_on or plan["devices"][d]["type"] == "curtains" or d in {t["device"] for t in plan["tasks"]}:
            continue
        if series[-1]:
            start = MINUTES - next(i for i, v in enumerate(reversed(series)) if not v) \
                if not all(series) else 0
            if MINUTES - start >= LONG_ON_MIN:
                questions.append(f"The {plan['devices'][d]['name']} stays on from {hhmm(start)} until midnight. "
                                 "You didn't say when to switch it off. Should it go off at some point?")
    return tips, questions


def savings_options(plan, day, events, runs):
    """Changes the household could approve to save money, each priced against today's plan.

    Each option is {"kind", "device", "title", "detail", "saving_sgd", "at"}: "move" starts a
    fixed-time task at its cheapest valid time; "off" switches off a device left on until midnight.
    """
    options = []
    for r in runs:
        t = next(x for x in plan["tasks"] if x["device"] == r["device"])
        if not t["start"]:
            continue
        ok = valid_starts(plan, day, r["device"], load_without(plan, day, events, runs, r["device"]), anywhere=True)
        if not ok:
            continue
        best = min(ok, key=lambda s: run_cost(plan, day, r["device"], s))
        saving = run_cost(plan, day, r["device"], to_min(r["start"])) - run_cost(plan, day, r["device"], best)
        if saving >= 0.01:
            name = plan["devices"][r["device"]]["name"]
            options.append({"kind": "move", "device": r["device"], "at": hhmm(best), "saving_sgd": round(saving, 3),
                            "title": f"Run the {name} at {hhmm(best)} instead of {r['start']}",
                            "detail": "Same cycle, off-peak price. Only if the time suits you."})
    sim = simulate(plan, day, events, runs)
    kept_on = {k["device"] for k in plan["keep"] if state_on(k["state"])}
    skip = kept_on | {t["device"] for t in plan["tasks"]}
    for d, series in sim["on"].items():
        dev = plan["devices"][d]
        if d in skip or dev["type"] == "curtains" or not dev["kw"] or not series[-1] or all(series):
            continue
        start = MINUTES - next(i for i, v in enumerate(reversed(series)) if not v)
        off = start + AUTO_OFF_MIN.get(dev["type"], 60)
        if MINUTES - start < LONG_ON_MIN or off >= MINUTES:
            continue
        saving = sum(dev["kw"] / 60 * day["price"][m // 30] for m in range(off, MINUTES))
        if saving >= 0.01:
            options.append({"kind": "off", "device": d, "at": hhmm(off), "saving_sgd": round(saving, 3),
                            "title": f"Switch the {dev['name']} off at {hhmm(off)}",
                            "detail": f"Otherwise it stays on from {hhmm(start)} until midnight, "
                                      f"{(MINUTES - start) / 60:.0f} hours you never asked for (at {dev['kw']:g} kW)."})
    return sorted(options, key=lambda o: -o["saving_sgd"])


def apply_option(plan, option):
    """A copy of the plan with one approved savings option added as an instruction."""
    plan = copy.deepcopy(plan)
    note = "Brain's money-saving suggestion, approved by you"
    if option["kind"] == "move":
        task = next(t for t in plan["tasks"] if t["device"] == option["device"])
        task.update(start=option["at"], quote=note)
    else:
        dev = plan["devices"][option["device"]]
        plan["commands"].append({"device": option["device"], "at": option["at"],
                                 "state": state_word(dev, False), "quote": note})
    return plan
