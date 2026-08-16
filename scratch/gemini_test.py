"""Credential-safe smoke test for the Gemini API.

Run from the repository root:

    uv --cache-dir .uv-cache run python scratch/gemini_test.py

Set GEMINI_API_KEY in the repository's local .env file first. Override the
default model with GEMINI_MODEL or the --model argument when needed.
"""

import argparse
import os
import sys
from pathlib import Path
from time import perf_counter

from dotenv import load_dotenv
from google import genai
from google.genai import types

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
EXPECTED_TOKEN = "CASCADE_GEMINI_OK"
DEFAULT_MODEL = "gemini-3.5-flash"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Test the CASCADE Gemini API connection.")
    parser.add_argument(
        "--model",
        default=os.getenv("GEMINI_MODEL", DEFAULT_MODEL),
        help=f"Gemini model name. Default: GEMINI_MODEL or {DEFAULT_MODEL}.",
    )
    return parser.parse_args()


def redact(message: str, secret: str) -> str:
    """Remove the API key if an SDK error unexpectedly includes it."""
    return message.replace(secret, "[REDACTED]")


def main() -> int:
    load_dotenv(REPOSITORY_ROOT / ".env", override=False)
    args = parse_args()
    api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")

    if not api_key:
        print("Gemini smoke test skipped: GEMINI_API_KEY is not configured.", file=sys.stderr)
        print("Copy .env.example to .env and add a Google AI Studio API key.", file=sys.stderr)
        return 2

    client = genai.Client(
        api_key=api_key,
        http_options=types.HttpOptions(timeout=20_000),
    )
    started = perf_counter()
    try:
        response = client.models.generate_content(
            model=args.model,
            contents=f"Reply with exactly this token and nothing else: {EXPECTED_TOKEN}",
            config=types.GenerateContentConfig(
                temperature=0,
                max_output_tokens=32,
            ),
        )
        response_text = (response.text or "").strip()
    except Exception as error:  # The SDK exposes several transport-specific errors.
        safe_message = redact(str(error), api_key)
        print(f"Gemini smoke test failed: {type(error).__name__}: {safe_message}", file=sys.stderr)
        return 3
    finally:
        client.close()

    elapsed_ms = round((perf_counter() - started) * 1000)
    if response_text != EXPECTED_TOKEN:
        print(
            f"Gemini responded, but verification failed. Received: {response_text!r}",
            file=sys.stderr,
        )
        return 4

    print(f"Gemini API OK | model={args.model} | latency_ms={elapsed_ms}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
