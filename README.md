# energy-agent: a verifiable brain for your home

An AI agent that runs a home's electrical devices from the household's own words, cutting electricity cost without ever breaking what they asked for. It's built for the Meta Global AI Developer Hackathon, **"Push the Frontier"** track (energy / controlling a physical system).

The household describes their day in plain language, typed or spoken, covering any device:

> *"I wake up at 7 am - I need the lights on exactly at 7 am. The automatic curtains must open for me at 7am, and the bathroom toilet must heat up at 7:05 am. I wash the clothes at 7:30 am, and for the rest of the day until 9pm, keep the lights closed. After 9:30pm, turn on the lights."*

```
listen → understand (Muse Spark Open) → plan (Muse Spark Open) → verify (plain code) → act → explain
                                              ↑                          │
                                              └── problems fed back ─────┘  (up to 3 attempts, then the literal plan)
```

- **Understand** turns the words into devices, exact-time commands ("lights on at 07:00"), keep windows ("lights off 07:30–21:00"), appliance tasks (fixed, like "wash at 7:30", or flexible, like "dry any time before midnight") and a power limit. Each item quotes the household's words.
- **Plan** writes the day's timeline and picks the cheapest valid time for every flexible task from the price forecast.
- **Verify** is plain code, not the model. It replays the day minute by minute and checks every exact time, keep window, task window, the power limit and cost. A plan that breaks anything is never carried out: the exact problems go back to the model. If no plan passes, the brain does exactly what was asked and holds any task that can't run without breaking a rule.
- **Explain** says why every action happened, in the household's own words. It adds money-saving tips (e.g. "starting the washing machine at 02:30 would save 0.07 SGD; you asked for 07:30, so it stays") and questions where something was left open (e.g. "the toilet heater stays on until midnight; should it go off?").

## Meta models used

| Model | How it's served | What it does here | Code |
|---|---|---|---|
| **Muse Spark Open** (`meta-models/muse-spark-open-1026`), open weights | Baseten (inference partner) | 1. Turns the household's words into a plan of devices, commands, keep windows and tasks. 2. Plans the day's timeline, and re-plans when verification fails. | `llm.py`, `preferences.py`, `agent.py` |
| **Muse Voice Transcribe** (`muse-voice-transcribe-1.0`) | Meta Model API | Turns spoken instructions into text | `llm.py`, `preferences.py` |
| **Muse Spark** (`muse-spark-1.3`) | Meta Model API | Automatic backup for Muse Spark Open: used only if Baseten is unreachable or rejects the key. The dashboard shows which model answered each call. | `llm.py` |

Muse Spark Open's reasoning arrives separately from its answer (`reasoning_content` on Baseten). The agent parses only the final JSON answer. The reasoning is saved and shown in the dashboard (*Under the hood*) for every plan.

## What was built during the hackathon

Everything in this repository was built during the hackathon building period (from 27 Oct 2026):

| File | Purpose |
|---|---|
| `agent.py` | The understand → plan → verify → act → explain loop, retry-on-feedback, safety drill, run log |
| `household.py` | Simulated home: device types, plan validation, minute-by-minute simulation, the checks verify() runs, tips and questions |
| `preferences.py` | The household's words → a validated plan; audio conversion for transcription |
| `llm.py` | Clients for Muse Spark Open (Baseten), Muse Spark and Muse Voice Transcribe (Meta Model API); JSON extraction from reasoning-model output |
| `app.py`, `ui_style.py`, `live_view.py` | Streamlit dashboard: process flow, live home replay, results, Integrations (simulated pairing) |
| `tests/test_agent.py` | 21 offline tests with the model mocked |
| `data.csv` | Synthetic household data (see below) |
| `samples/preferences.wav` | Sample voice note (generated with macOS text-to-speech) |

Development tooling: written with the help of an AI coding assistant (Claude Code).

## Data: synthetic, not real meter readings

`data.csv` is **representative synthetic data**, not real meter readings: a typical Singapore household in 30-minute slots. The brain uses its first day for the price forecast and for the load of the rest of the home (devices the brain doesn't manage). Prices follow an illustrative time-of-use plan (about 0.245 SGD/kWh off-peak 23:00–07:00, about 0.318 peak). See `notes.md` for the full description.

## Results

Live runs with real calls to Muse Spark Open, with the safety drill on:

- **Morning routine** (the quote above): understood as 6 instructions across 4 devices (lights, curtains, toilet heater, washing machine), each quoting the household. The drill's wrong plan (lights at 06:55 instead of 07:00) was rejected by verify(). Muse Spark Open's corrected plan passed, and all 6 instructions were followed exactly. It also added the lights-off switch at 07:30 that the keep window needs. It gave a tip (washing at 02:30 would be 0.07 SGD cheaper, but 07:30 was asked for, so it stays) and asked a question (the toilet heater was never told to switch off).
- **Laundry night** ("dryer any time after 8pm, done by midnight, not 9–10:30pm, under 4 kW"): the drill's wrong plan (dryer at 20:30, running into the quiet window) was rejected. The model chose 23:00, the first off-peak slot, which keeps every rule. Switching on at 20:00 instead would have cost 0.22 SGD more and broken the 4 kW limit for 60 minutes.

## Run it

```bash
python -m venv .venv
.venv/bin/pip install -r requirements.txt
```

Create `.env` (it's git-ignored, never commit it) with:
```
BASETEN_API_KEY=...
META_API_KEY=...
```

Then:
```bash
.venv/bin/streamlit run app.py                    # dashboard
.venv/bin/python agent.py --drill                 # command line: the morning routine, with the safety drill
.venv/bin/python agent.py "Fan on at 10pm, off at 6am"   # command line, your own words
.venv/bin/python -m unittest discover tests       # offline tests, no API calls
```

## Using the dashboard

The steps are also shown at the top of the page.

1. **Tell it about your day.** Type, record a voice note and press *Transcribe*, or pick an example (*Morning routine*, *Laundry night*, *Whole home*). Press *Understand my day*. Each instruction appears as a card with the words it came from; *Edit the plan by hand* lets you change it.
2. **Watch it run your home.** Press *Run my day*. A process flow (Listen → Understand → Plan → Verify → Act → Explain) lights up as the brain works, with a plain-language log underneath. Then the day plays: the clock speeds through quiet hours and slows down for each action, devices switch on and off, and the feed says why.
   - **Safety drill** (on by default) slips one deliberately wrong plan in first. You see verify() catch it, the problem go back to Muse Spark Open, and the corrected plan pass.
   - **Demo / Fast** sets the pace.
3. **What the brain did.** Instructions followed, mistakes caught, cost and peak load (each against doing it without the brain), tips and questions. *Your day* shows every device on a timeline; *Under the hood* shows each plan, the checks it failed, and the raw model reasoning.

The **Integrations** tab shows how devices would be paired (Matter, Zigbee, Wi-Fi plug, Home Assistant). In this build pairing is **simulated**: no real hardware is contacted, and the page says so.

## Limitations

- The data is synthetic and the home is simulated: `act()` drives a simulated home, and Integrations pairing is a mock-up. No real device is switched.
- The plan covers one day; windows can wrap past midnight, but tasks must fit within the day.
- Singapore's grid carbon intensity is nearly flat (gas-fired), so shifting saves money but very little CO2. The brain doesn't claim emissions savings.
