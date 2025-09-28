import os
import json
import requests
from dotenv import load_dotenv

load_dotenv()

API_URL = os.getenv("LLM_API_URL")
API_KEY = os.getenv("LLM_API_KEY")
MODEL = os.getenv("LLM_MODEL", "gpt-4o-mini")
DEFAULT_TEMPERATURE = float(os.getenv("LLM_TEMPERATURE", "0.0"))
DEFAULT_MAX_TOKENS = int(os.getenv("LLM_MAX_TOKENS", "1024"))

if not API_URL or not API_KEY:
    raise RuntimeError("LLM_API_URL and LLM_API_KEY must be set in .env")

# keep track of running total
running_cost = 0.0

# Pricing for GPT-4o mini (USD per million tokens)
PRICE_INPUT = 0.15 / 1_000_000
PRICE_OUTPUT = 0.60 / 1_000_000


def call_llm(prompt: str, temperature: float = DEFAULT_TEMPERATURE, max_tokens: int = DEFAULT_MAX_TOKENS) -> str:
    global running_cost

    payload = {
        "model": MODEL,
        "temperature": temperature,
        "max_tokens": max_tokens,
        "messages": [{"role": "user", "content": prompt}]
    }

    headers = {"Content-Type": "application/json"}
    if "openai" in API_URL:
        headers["Authorization"] = f"Bearer {API_KEY}"
    else:
        headers["X-api-key"] = API_KEY  # for company LLMs

    try:
        resp = requests.post(API_URL, headers=headers, json=payload, timeout=60)
        resp.raise_for_status()
        data = resp.json()

        # --- Extract text reply ---
        text_out = None
        if "choices" in data and len(data["choices"]) > 0:
            first = data["choices"][0]
            if "message" in first and "content" in first["message"]:
                text_out = first["message"]["content"].strip()
            elif "text" in first:
                text_out = first["text"].strip()

        # --- Extract usage info ---
        usage = data.get("usage", {})
        prompt_tokens = usage.get("prompt_tokens", 0)
        completion_tokens = usage.get("completion_tokens", 0)
        total_tokens = usage.get("total_tokens", prompt_tokens + completion_tokens)

        # cost estimate (only accurate for GPT-4o mini; adjust if you change model)
        call_cost = (prompt_tokens * PRICE_INPUT) + (completion_tokens * PRICE_OUTPUT)
        running_cost += call_cost

        print(f"\n📊 Token usage for this call:")
        print(f"  Prompt tokens     : {prompt_tokens}")
        print(f"  Completion tokens : {completion_tokens}")
        print(f"  Total tokens      : {total_tokens}")
        print(f"  Cost this call    : ${call_cost:.6f}")
        print(f"  Running total cost: ${running_cost:.6f}\n")

        if text_out:
            return text_out

        # fallback: try top-level fields
        for k in ("text", "output", "response"):
            if k in data and isinstance(data[k], str):
                return data[k].strip()

        return json.dumps(data)[:4000]

    except requests.exceptions.RequestException as e:
        raise RuntimeError(f"LLM API request failed: {e}")
