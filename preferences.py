"""Household instructions: plain language (typed or spoken) -> a plan the home brain can carry out and check.

Muse Spark Open reads how the household lives and returns the devices it mentions,
exact-time commands, keep windows, appliance tasks and a power limit, each with the
household's own words. household.validate_plan then keeps only well-formed items, so
anything the model gets wrong is dropped and reported, not trusted.
"""
import io
import wave

import numpy as np

from household import DEVICE_TYPES, validate_plan
from llm import ask_spark_open, extract_json, transcribe

DEFAULT_PREFERENCES = (
    "I wake up at 7 am - I need the lights on exactly at 7 am. The automatic curtains must open for me "
    "at 7am, and the bathroom toilet must heat up at 7:05 am. I wash the clothes at 7:30 am, and for the "
    "rest of the day until 9pm, keep the lights closed. After 9:30pm, turn on the lights."
)

SYSTEM_PROMPT = f"""You turn a household's plain-language description of their day into a plan that a
smart-home brain can carry out and check. Cover any household electrical device they mention.

Device types: {", ".join(DEVICE_TYPES)}.

You may think first. Then end your reply with exactly one JSON object on its own line, and nothing after it:
{{"devices": [{{"id": "<snake_case id>", "name": "<short name, e.g. Bedroom lights>", "type": "<device type>", "kw": <typical kW while on>}}],
 "commands": [{{"device": "<id>", "at": "HH:MM", "state": "on|off|open|closed", "quote": "<the household's exact words>"}}],
 "keep": [{{"device": "<id>", "from": "HH:MM", "until": "HH:MM", "state": "on|off|open|closed", "quote": "<exact words>"}}],
 "tasks": [{{"device": "<id>", "minutes": <cycle length>, "start": "HH:MM or null", "earliest": "HH:MM or null", "finish_by": "HH:MM or null", "quote": "<exact words>"}}],
 "max_household_kw": <number or null>, "limit_quote": "<exact words, or null>",
 "summary": "<one sentence restating the plan>"}}

Rules:
- Times are 24-hour HH:MM within one day. "24:00" means midnight at the end of the day.
- commands: a device switched to a state at an exact time ("lights on at 7am", "turn on the lights after 9:30pm").
- keep: a device that must stay in a state for a period ("keep the lights off until 9pm",
  "no dryer between midnight and 6am"). "until" is when the period ends. If the start of the period is
  implied by an earlier event ("for the rest of the day"), start it at the end of that event.
- tasks: appliances that run a cycle (washing machine, dryer, dishwasher, EV charging, water heater).
  Use "start" when the household gives an exact time. Otherwise give the window it may run in
  ("earliest", "finish_by") so the brain can choose the cheapest time. "minutes" is the cycle length
  they state, or a typical one.
- For lights and other on/off devices, "closed" or "shut" means off.
- Use one device id per physical device and reuse it everywhere.
- Quote the household's own words for every item.
- Only include what the household said. Do not invent devices, times or limits."""


def extract_plan(text):
    """Ask Muse Spark Open for a plan; return (plan, reasoning, warnings)."""
    answer, reasoning = ask_spark_open(SYSTEM_PROMPT, f"Household's description of their day:\n{text}")
    raw = extract_json(answer, lambda o: isinstance(o.get("devices"), list) and "summary" in o)
    if raw is None:
        return None, reasoning, ["could not read a plan from the model reply"]
    plan, warnings = validate_plan(raw)
    return plan, reasoning, warnings


def to_wav16k(audio_bytes):
    """Convert any PCM WAV (e.g. a browser recording) to 16 kHz mono 16-bit, as Muse Voice Transcribe needs."""
    with wave.open(io.BytesIO(audio_bytes)) as w:
        rate, channels, width = w.getframerate(), w.getnchannels(), w.getsampwidth()
        frames = w.readframes(w.getnframes())
    dtype = {1: np.uint8, 2: np.int16, 4: np.int32}[width]
    samples = np.frombuffer(frames, dtype=dtype).astype(np.float64)
    if width == 1:
        samples = (samples - 128) * 256
    elif width == 4:
        samples = samples / 65536
    samples = samples.reshape(-1, channels).mean(axis=1)
    if rate != 16000:
        n = int(len(samples) * 16000 / rate)
        samples = np.interp(np.linspace(0, len(samples) - 1, n), np.arange(len(samples)), samples)
    out = io.BytesIO()
    with wave.open(out, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(16000)
        w.writeframes(np.clip(samples, -32768, 32767).astype(np.int16).tobytes())
    return out.getvalue()


def transcribe_preferences(audio_bytes):
    """Spoken instructions -> text, via Muse Voice Transcribe."""
    return transcribe(to_wav16k(audio_bytes))
