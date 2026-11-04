"""Shared access to Meta's models.

- Muse Spark Open (open weights), served by Baseten: makes the agent's decisions
  and turns household preferences into constraints.
- Muse Spark, via the Meta Model API: the same job, used automatically when Baseten
  can't be reached or rejects the key, so the agent keeps working.
- Muse Voice Transcribe, via the Meta Model API: turns spoken preferences into text.

Keys come from .env (BASETEN_API_KEY, META_API_KEY) and are never written in code.
"""
import json
import os
import re

import requests
from dotenv import load_dotenv
from openai import APIConnectionError, APIStatusError, OpenAI

load_dotenv()

SPARK_OPEN_MODEL = "meta-models/muse-spark-open-1026"
META_SPARK_MODEL = "muse-spark-1.3"
TRANSCRIBE_MODEL = "muse-voice-transcribe-1.0"
TRANSCRIBE_URL = "https://api.meta.ai/v1/asr/transcribe"

spark_open = OpenAI(
    base_url="https://inference.baseten.co/v1",
    api_key=os.environ.get("BASETEN_API_KEY") or "missing",
    timeout=180,      # a stalled call fails (and falls back) instead of hanging the loop
    max_retries=0,
)
meta_spark = OpenAI(
    base_url="https://api.meta.ai/v1",
    api_key=os.environ.get("META_API_KEY") or "missing",
    timeout=120,
    max_retries=1,
)

last_model = None  # model that answered the most recent call
# Why Baseten is being skipped (e.g. a rejected key), or None while it is in use.
baseten_error = None if os.environ.get("BASETEN_API_KEY") else "BASETEN_API_KEY is not set"


def ask_spark_open(system, user):
    """Call Muse Spark Open on Baseten, falling back to Muse Spark on the Meta Model API.

    Returns (answer text, reasoning text). Baseten returns the model's reasoning in a
    separate `reasoning_content` field, so `content` holds only the final answer.
    A rejected key (401/403) disables Baseten for the rest of the session; a timeout
    or server error falls back for that call only.
    """
    global last_model, baseten_error
    if baseten_error is None:
        try:
            answer = _chat(spark_open, SPARK_OPEN_MODEL, system, user)
            last_model = SPARK_OPEN_MODEL
            return answer
        except APIStatusError as e:
            if e.status_code in (401, 403):
                baseten_error = f"Baseten rejected the API key (HTTP {e.status_code})"
            elif e.status_code < 500 and e.status_code != 429:
                raise
        except APIConnectionError:  # includes timeouts
            pass
    answer = _chat(meta_spark, META_SPARK_MODEL, system, user)
    last_model = META_SPARK_MODEL
    return answer


def _chat(client, model, system, user):
    response = client.chat.completions.create(
        model=model,
        messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
        temperature=0.2,
    )
    message = response.choices[0].message
    reasoning = (getattr(message, "model_extra", None) or {}).get("reasoning_content") or ""
    return message.content or "", reasoning


def extract_json(text, accept):
    """Return the last JSON object in `text` for which accept(obj) is true, or None.

    Any <think>...</think> block is dropped first, in case the reasoning arrives
    inline. Scanning backwards means braces or draft answers inside the reasoning
    can't be mistaken for the final answer.
    """
    text = re.sub(r"(?s)^.*</think>", "", text)
    text = re.sub(r"(?s)<think>.*", "", text) if "<think>" in text else text
    for start in reversed([m.start() for m in re.finditer(r"\{", text)]):
        end = text.find("}", start)
        while end != -1:
            try:
                obj = json.loads(text[start:end + 1])
            except json.JSONDecodeError:
                end = text.find("}", end + 1)
                continue
            if isinstance(obj, dict) and accept(obj):
                return obj
            break
    return None


def transcribe(wav_bytes):
    """Transcribe a 16 kHz mono 16-bit WAV with Muse Voice Transcribe; return the text."""
    settings = {"mode": "PUSH_TO_TALK", "model": TRANSCRIBE_MODEL, "audioEncoding": "WAV"}
    response = requests.post(
        TRANSCRIBE_URL,
        headers={"Authorization": f"Bearer {os.environ['META_API_KEY']}"},
        files={
            "request": (None, json.dumps(settings), "application/json"),
            "audio": ("audio.wav", wav_bytes, "audio/wav"),
        },
        timeout=60,
    )
    response.raise_for_status()
    return response.json().get("transcript", "").strip()
