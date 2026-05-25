"""
Shared Gemini API client for IntelliPredict.
Handles quota errors, model fallback, and retry logic.
"""

import json
import re
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
                json_mode: bool = False, timeout: int = 45) -> tuple:
    """Call one Gemini model. Returns (text, error).
    error == 'QUOTA_EXCEEDED' means try next model.
    error == None means success.
    """
    url  = f"{GEMINI_BASE}/{model}:generateContent?key={api_key}"
    body = {"contents": [{"parts": [{"text": prompt}]}]}
    if json_mode:
        body["generationConfig"] = {
            "temperature": 0.2,
            "responseMimeType": "application/json",
        }
    try:
        resp = requests.post(
            url,
            headers={"Content-Type": "application/json"},
            json=body,
            timeout=timeout,
        )
        data = resp.json()

        # ── Quota / rate-limit errors (may come as 200 OR 429) ────────────────
        if resp.status_code == 429:
            return None, "QUOTA_EXCEEDED"

        # Some quota errors return HTTP 200 with an error body
        if "error" in data:
            code    = data["error"].get("code", 0)
            message = data["error"].get("message", "")
            status  = data["error"].get("status", "")
            if code == 429 or "quota" in message.lower() or "RESOURCE_EXHAUSTED" in status:
                return None, "QUOTA_EXCEEDED"
            if code == 404 or "not found" in message.lower():
                return None, "MODEL_NOT_FOUND"
            return None, f"API error {code}: {message[:200]}"

        # ── Successful response ───────────────────────────────────────────────
        if resp.status_code == 200:
            candidates = data.get("candidates", [])
            if not candidates:
                # Safety block or empty response
                reason = data.get("promptFeedback", {}).get("blockReason", "empty response")
                return None, f"Blocked/empty: {reason}"
            try:
                text = candidates[0]["content"]["parts"][0]["text"]
                return text, None
            except (KeyError, IndexError) as e:
                return None, f"Unexpected response structure: {e} — raw: {str(data)[:200]}"

        return None, f"HTTP {resp.status_code}: {resp.text[:200]}"

    except requests.exceptions.Timeout:
        return None, "Request timed out — try again"
    except Exception as e:
        return None, f"Connection error: {str(e)}"


def call_gemini(prompt: str) -> str:
    """Call Gemini with model fallback. Returns text or friendly error message."""
    api_key = get_api_key()
    if not api_key:
        return "⚠️ GEMINI_API_KEY not set in Streamlit Secrets."

    last_err = ""
    for model in GEMINI_MODELS:
        text, err = _call_model(model, prompt, api_key)
        if text:
            return text
        if err in ("QUOTA_EXCEEDED", "MODEL_NOT_FOUND"):
            last_err = err
            continue   # silently try next model
        if err:
            # Real error — don't try other models
            return f"⚠️ AI error: {err}"

    # All models exhausted
    if last_err == "QUOTA_EXCEEDED":
        return (
            "⚠️ Gemini free-tier quota exhausted for all models. "
            "Wait 60 seconds and try again, or upgrade at https://ai.google.dev"
        )
    return "⚠️ All Gemini models unavailable. Please try again shortly."


def call_gemini_json(prompt: str) -> tuple:
    """Call Gemini expecting JSON. Returns (dict, error_str).
    On success error_str is None.
    """
    api_key = get_api_key()
    if not api_key:
        return {}, "GEMINI_API_KEY not set in Streamlit Secrets."

    last_err = ""
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
        if err in ("QUOTA_EXCEEDED", "MODEL_NOT_FOUND"):
            last_err = err
            continue
        if err:
            return {}, f"AI error ({model}): {err}"

    if last_err == "QUOTA_EXCEEDED":
        return {}, (
            "Gemini free-tier quota exhausted. "
            "Wait 60 seconds and try again."
        )
    return {}, "All Gemini models unavailable. Please try again shortly."


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


def show_gemini_error(err: str):
    """Show either a quota warning or a regular error based on error type."""
    if not err:
        return
    if any(x in err.lower() for x in ["quota", "exhausted", "429", "wait 60"]):
        gemini_quota_warning()
    else:
        st.error(f"❌ {err}")
