import os
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

client = OpenAI(
    base_url="https://api.meta.ai/v1",    # confirm against Meta quickstart
    api_key=os.environ["META_API_KEY"],   # reads from .env — no key in this file
)

response = client.chat.completions.create(
    model="muse-spark-1.3",               # confirm exact string in Meta model list
    messages=[{"role": "user", "content": "Reply with just: meta pipe works"}],
)
print(response.choices[0].message.content)