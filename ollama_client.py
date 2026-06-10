# ollama_client.py — call the local Ollama LLM to generate answers

import requests
from config import OLLAMA_BASE_URL, OLLAMA_LLM_MODEL


def generate_answer(prompt: str) -> str:
    """Send a prompt to gemma4:e4b via Ollama and return the response text."""
    resp = requests.post(
        f"{OLLAMA_BASE_URL}/api/generate",
        json={"model": OLLAMA_LLM_MODEL, "prompt": prompt, "stream": False},
        timeout=180,
    )
    resp.raise_for_status()
    return resp.json()["response"].strip()
