"""
Shared Gemini API client for IntelliPredict.
Handles quota errors, model fallback, and retry logic.
"""

import time
import json
import requests
import streamlit as st

GEMINI_MODELS = [
    "gemini-2.0-flash",
    "gemini-2.0-flash-lite",
    "gemini-1.5-flash",
]
GEMINI_BASE = "https://generativelanguage.googleapis.com/v1beta/models"


def get_api_key() -> str:
    try:
        return st.secrets.get("GEMINI_API_KEY", "")
    except Exception:
        return ""


def _call_model(model: str, prompt: str, api_key: str,
                json_mode: bool = False, timeout: int = 30) -> tuple:
    """Call one Gemini model. Returns (text, error)."""
    url  = f"{GEMINI_BASE}/{model}:generateContent?key={api_key}"
    body = {"contents": [{"parts": [{"text": prompt}]}]}
    if json_mode:
        body["generationConfig"] = {
            "temperature": 0.2,
            "responseMimeType": "application/json",
        }
    try:
        resp = requests.post(url, headers={"Content-Type": "application/json"},
                             json=body, timeout=timeout)
        if resp.status_code == 200:
            data = resp.json()
            if not data.get("candidates"):
                reason = data.get("promptFeedback", {}).get("blockReason", "Unknown")
                return None, f"Blocked: {reason}"
            return data["candidates"][0]["content"]["parts"][0]["text"], None
        elif resp.status_code == 429:
            return None, "QUOTA_EXCEEDED"
        else:
            return None, f"HTTP {resp.status_code}: {resp.text[:200]}"
    except Exception as e:
        return None, str(e)


def call_gemini(prompt: str, max_retries: int = 1) -> str:
    """Call Gemini with model fallback. Returns text or friendly error message."""
    api_key = get_api_key()
    if not api_key:
        return "⚠️ GEMINI_API_KEY not set in Streamlit Secrets."

    for model in GEMINI_MODELS:
        text, err = _call_model(model, prompt, api_key)
        if text:
            return text
        if err == "QUOTA_EXCEEDED":
            continue   # try next model
        if err:
            return f"⚠️ AI error: {err}"

    # All models quota-exceeded
    return (
        "⚠️ All Gemini free-tier models are quota-exhausted. "
        "Free tier resets every minute — please wait 60 seconds and try again. "
        "Or upgrade at https://ai.google.dev to get higher limits."
    )


def call_gemini_json(prompt: str) -> tuple:
    """Call Gemini expecting JSON. Returns (dict, error_str)."""
    api_key = get_api_key()
    if not api_key:
        return {}, "GEMINI_API_KEY not set in Streamlit Secrets."

    import re

    for model in GEMINI_MODELS:
        text, err = _call_model(model, prompt, api_key, json_mode=True)
        if text:
            try:
                clean = re.sub(r"```(?:json)?", "", text).strip().strip("`").strip()
                match = re.search(r"\{.*\}", clean, re.DOTALL)
                if match:
                    clean = match.group(0)
                return json.loads(clean), None
            except json.JSONDecodeError as je:
                return {}, f"JSON parse error: {je}. Raw: {text[:300]}"
        if err == "QUOTA_EXCEEDED":
            continue
        if err:
            return {}, f"AI error ({model}): {err}"

    return {}, (
        "All Gemini free-tier models are quota-exhausted. "
        "Free tier resets every minute — wait 60 seconds and try again. "
        "Upgrade at https://ai.google.dev for higher limits."
    )


def gemini_quota_warning():
    """Show a friendly quota warning in Streamlit."""
    st.warning(
        "⏳ **Gemini Free Tier Quota Reached**\n\n"
        "The free Gemini API resets every **60 seconds**. "
        "Please wait a moment and click the button again.\n\n"
        "💡 **Tip:** Go to [Google AI Studio](https://aistudio.google.com) → "
        "Get API Key → Upgrade to a paid plan for unlimited access.",
        icon="⚠️",
    )
