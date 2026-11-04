# energy-agent notes

## data.csv

**This is representative synthetic data, not real meter readings.**

It shows a typical Singapore household over 3 days (Tue 20 – Thu 22 Oct 2026), with one row every 30 minutes: 144 rows plus a header. A fixed random seed was used, so the same file can be regenerated exactly.

| Column | Unit | What it represents |
|---|---|---|
| `timestamp` | ISO 8601, Singapore time (+08:00) | Start of each 30-minute interval |
| `household_load_kw` | kW | Average household power draw in that interval |
| `grid_price_per_kwh` | SGD/kWh | Illustrative time-of-use retail price |
| `grid_carbon_intensity` | gCO2e/kWh | Emissions per kWh drawn from the grid |

### Load shape (each day)

| Time | Load (kW) | What's running |
|---|---|---|
| 00:00–06:00 | 0.36–0.57 | **Low overnight:** bedroom AC on a low setting, plus fridge, router and standby |
| 06:30–08:00 | 0.74–1.14 | **Morning peak:** water heater, kettle, toaster |
| 09:00–18:00 | 0.17–0.43 | Mostly out: fridge and standby only (the daily minimum, ~0.17), with a small lunchtime bump |
| 19:00–20:00 | 1.09–1.36 | **Evening peak starts:** cooking, lights, TV |
| 20:00–23:00 | 1.60–4.31 | **Big evening spike:** living-room and bedroom AC (~1.5 kW) plus a ~2 kW tumble dryer for one hour |

The dryer runs at a different time each evening, so the daily peak moves:

| Day | Daily use | Peak |
|---|---|---|
| 20 Oct | 17.4 kWh | 4.31 kW at 20:30 |
| 21 Oct | 17.7 kWh | 4.17 kW at 21:00 |
| 22 Oct | 17.4 kWh | 3.77 kW at 21:30 |

About 17.5 kWh a day works out to roughly 525 kWh a month. That's on the high side for an HDB flat, which fits a home that runs AC every evening and uses a dryer daily.

Every value has ±8% random variation, so no two days are identical.

### Price

The price follows a made-up two-rate plan: about **0.245 SGD/kWh off-peak** (23:00–07:00) and about **0.318 SGD/kWh peak** (07:00–23:00), with ±0.004 random variation. The overall range is 0.2410–0.3217. The evening spike falls almost entirely in the peak window.

### Carbon intensity

Carbon intensity stays between 401 and 421 gCO2e/kWh, close to the average for Singapore's mostly gas-fired grid (about 0.41 kg/kWh). There's a small dip around 13:00, when rooftop solar contributes. It's nearly flat, so for this household shifting load in time changes the cost much more than the emissions.

These figures are plausible approximations, not official tariffs or emission factors.

## agent.py

The agent is a closed loop. Muse Spark Open makes the decisions, plain code verifies every one, and a simulated household carries them out and measures the savings. The rest of this file describes how each part works.

Files:

| File | Role |
|---|---|
| `agent.py` | The loop: monitor → decide → verify → act → explain, with retry-on-feedback. Saves a run log to `runs/latest.json` |
| `household.py` | Simulated household: replays data.csv, moves dryer runs, checks constraints, computes cost and CO2 |
| `preferences.py` | Plain-language preferences → validated constraints; converts audio for transcription |
| `llm.py` | Clients for Muse Spark Open (Baseten) and Muse Voice Transcribe (Meta Model API); parses JSON out of the model's output |
| `app.py` | Streamlit dashboard (`.venv/bin/streamlit run app.py`) |
| `tests/test_agent.py` | 18 offline tests; the model is mocked, so no API calls |

### The loop, step by step

| Step | What it does |
|---|---|
| `monitor()` | Advances the simulated household one 30-minute slot. If the dryer is about to start, the state also includes its power, duration and deadline, plus a forecast of every slot it could still start in (price, carbon, planned load) |
| `decide(state)` | When nothing flexible is due, returns `no_action` **without calling the model**. When the dryer is due, asks Muse Spark Open to run it now or pick a later start. The prompt includes the household's constraints and, on a retry, the problems with the previous answer |
| `verify(action)` | Deterministic checks, with no model involved: the appliance is the one due, the start time is a later slot from the list, the run finishes by the deadline, it doesn't run during quiet hours, the household stays under its power limit, and it costs no more than running now. Running now is also checked, so `no_action` is rejected when running now itself breaks a rule. `hold` is accepted only if the code independently confirms that no start time works |
| `act(action)` | Moves the run in the simulated load profile and records the cost and CO2 saved on that run |
| `explain(action)` | One plain-language sentence: what happened, the computed saving, and the model's reason |

**Three possible actions.** `no_action` (run as scheduled), `shift_load` (move to a later start) and `hold` (don't run it; ask the household). Hold exists for days when the household's rules can't all be met. Without it, the agent's only options would be breaking a rule or guessing.

**Verification and retries.** If `verify()` finds problems, the agent calls `decide()` again with the exact problems listed, up to 3 attempts in total. If no attempt passes, it never acts on a failed decision. It keeps the original schedule if that's valid, and otherwise holds the appliance, rather than break the household's rules. Either way the decision is marked `fallback` and anything unresolved is listed. API errors and unparseable replies also fall back safely.

**Cost.** The model is only called when the dryer is due, which is 3 times in 3 days, plus once to read the preferences. A full run costs a handful of calls, not 144.

### Preferences → constraints

1. **Voice (optional):** a recording goes to **Muse Voice Transcribe** (`muse-voice-transcribe-1.0`, Meta Model API, `POST https://api.meta.ai/v1/asr/transcribe`). That endpoint needs 16 kHz mono 16-bit WAV, so `to_wav16k()` converts browser recordings first.
2. **Text → constraints:** Muse Spark Open returns JSON `{finish_by, quiet_hours, max_household_kw, summary}`.
3. **Validation:** each field is checked (times must be on the half hour, the kW limit must be between 1 and 30). Anything malformed is dropped and reported, never trusted.

Default preferences: *"We need the laundry dry by 7am. Please don't run the dryer between midnight and 6am, the laundry room is right next to the kids' bedroom. And keep the whole flat under 4 kW, the old wiring trips if we go above that."* The 4 kW limit is set so it actually binds on this data: running the dryer at its scheduled time breaks it on 2 of the 3 evenings.

`samples/preferences.wav` is the same text spoken by macOS text-to-speech. It's recorded at 22.05 kHz, so it also tests the conversion.

### How the reasoning output is handled

Muse Spark Open always reasons before answering. On Baseten, the reasoning comes back in a separate field, `message.reasoning_content`, and `message.content` holds only the final answer. The agent:

- Parses the answer from `content` only. `extract_json()` in llm.py searches **backwards** for the last valid JSON object of the expected shape, so stray braces or draft answers can't be mistaken for the final one. It also strips `<think>...</think>` blocks in case a server ever returns the reasoning inline.
- Saves the reasoning with each attempt in the run log, and the dashboard shows it ("Model reasoning, attempt N").

### Live results (default preferences, spoken sample → transcript → constraints)

- Muse Voice Transcribe produced: *"We need the laundry dry by 7 am. please don't run the dryer between midnight and 6 am. … keep the whole flat under four kilowatts …"*
- Muse Spark Open turned that into `finish_by 07:00`, `quiet_hours 00:00–06:00` and `max_household_kw 4.0`.

| Dryer due | Decision | Model's reason | verify |
|---|---|---|---|
| 20 Oct 20:30 | moved to 23:00 | "Now violates 4.0kW limit and 23:00 is the lowest-cost valid slot before quiet hours" | passed |
| 21 Oct 21:00 | moved to 23:00 | "Cheapest valid slot that respects 4.0kW limit and avoids 00:00-06:00 quiet hours." | passed |
| 22 Oct 21:30 | moved to 23:00 | "Lowest cost (0.241 SGD/kWh) and respects 4.0kW limit and quiet hours." | passed |

**Total:** 15.78 → 15.33 SGD over 3 days (**−0.45 SGD, −2.8%**). CO2e is unchanged at 21.84 kg, because Singapore's grid carbon intensity is nearly flat overnight.

An earlier version with no preferences and no verify() chose 22:30 on 22 Oct, even though 23:00 (off-peak) was cheaper. The "costs more than running now" check and the forecast list now guard against that kind of slip.

### Live results (tight preferences: verify and hold in action)

The constraints were no dryer from 22:00 to 06:00, dry by 07:00, and the household under 3.5 kW. On days 1–2 the only valid start is 06:00. On day 3 there is **no** valid start, because the data ends at midnight, so the next 06:00 slot doesn't exist.

| Dryer due | Decision | Model's reason | verify |
|---|---|---|---|
| 20 Oct 20:30 | moved to 06:00 | "Now exceeds power limit and all earlier slots violate power or quiet-hour constraints, so 06:00 is the cheapest valid start." | passed |
| 21 Oct 21:00 | moved to 06:00 | "…only 06:00 meets power and quiet constraints before deadline" | passed |
| 22 Oct 21:30 | **hold** | "No start time satisfies both power limit and quiet-hours constraints." | passed (independently confirmed no valid start exists) |

**Total:** 15.78 → 15.49 SGD (−1.8%). The held run counts no saving.

**Why hold was added.** Before `hold` existed, the same day-3 situation went wrong:
1. The model's `no_action` was rightly rejected, because running now breaks the rules.
2. Pushed by the retry, it picked 23:00, which verify rejected for quiet hours.
3. The third reply couldn't be parsed.
4. The fallback then ran the dryer as scheduled, breaking the household's rules.

Adding `hold`, verified by code, fixed this. It's covered by 3 tests in `tests/test_agent.py` (18 tests in total).

### Known limits

- The data is synthetic and the household is simulated. Only one flexible appliance (the tumble dryer) is modelled.
- The cost saving per run is small (about 0.15 SGD) because the gap between peak and off-peak prices is about 7 cents per kWh.
