"""
Shared Gemini API client for IntelliPredict.
Robust: handles quota, 404, network errors, and provides
rich rule-based fallback so app works even without API.
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
    """Get Gemini API key from Streamlit secrets."""
    try:
        key = st.secrets.get("GEMINI_API_KEY", "")
        return key.strip() if key else ""
    except Exception:
        return ""


def _call_model(model: str, prompt: str, api_key: str,
                json_mode: bool = False, timeout: int = 45) -> tuple:
    """
    Call one Gemini model.
    Returns (text, error_code) where error_code is:
      None           → success
      'QUOTA'        → quota exceeded, try next model
      'NOT_FOUND'    → model not found, try next model
      'NO_KEY'       → API key missing/invalid
      'BLOCKED'      → safety filter blocked
      str            → other error message
    """
    if not api_key:
        return None, "NO_KEY"

    url  = f"{GEMINI_BASE}/{model}:generateContent?key={api_key}"
    body = {"contents": [{"parts": [{"text": prompt}]}]}
    if json_mode:
        body["generationConfig"] = {
            "temperature":    0.2,
            "responseMimeType": "application/json",
        }

    try:
        resp = requests.post(
            url,
            headers={"Content-Type": "application/json"},
            json=body,
            timeout=timeout,
        )

        # Try to parse JSON — if empty/invalid treat as network error
        try:
            data = resp.json()
        except Exception:
            if resp.status_code == 403:
                return None, "NO_KEY"
            return None, f"HTTP {resp.status_code}: empty response"

        # Quota errors (can be 200 OR 429 with error body)
        if resp.status_code == 429:
            return None, "QUOTA"
        if "error" in data:
            code    = data["error"].get("code",   0)
            msg     = data["error"].get("message","")
            status  = data["error"].get("status", "")
            if code == 429 or "quota" in msg.lower() or status in ("RESOURCE_EXHAUSTED",):
                return None, "QUOTA"
            if code == 404 or "not found" in msg.lower():
                return None, "NOT_FOUND"
            if code in (400, 403):
                return None, "NO_KEY"
            return None, f"API error {code}: {msg[:150]}"

        # Success
        if resp.status_code == 200:
            candidates = data.get("candidates", [])
            if not candidates:
                reason = data.get("promptFeedback", {}).get("blockReason", "empty")
                return None, "BLOCKED"
            try:
                text = candidates[0]["content"]["parts"][0]["text"]
                return text, None
            except (KeyError, IndexError):
                return None, "Unexpected response structure"

        return None, f"HTTP {resp.status_code}"

    except requests.exceptions.Timeout:
        return None, "TIMEOUT"
    except requests.exceptions.ConnectionError:
        return None, "NETWORK_ERROR"
    except Exception as e:
        return None, f"Error: {str(e)[:100]}"


def call_gemini(prompt: str) -> str:
    """
    Call Gemini with model fallback.
    Returns text response or a clear error/fallback string.
    """
    api_key = get_api_key()
    if not api_key:
        return "⚠️ GEMINI_API_KEY not set in Streamlit Secrets."

    last_err = ""
    for model in GEMINI_MODELS:
        text, err = _call_model(model, prompt, api_key)
        if text:
            return text
        last_err = err or ""
        # Try next model for these errors
        if err in ("QUOTA", "NOT_FOUND", "TIMEOUT", "NETWORK_ERROR"):
            continue
        if err == "NO_KEY":
            return "⚠️ Gemini API key is invalid. Please check GEMINI_API_KEY in Streamlit Secrets."
        if err == "BLOCKED":
            return "⚠️ Gemini blocked this request. Please rephrase your question."
        # Other errors — stop trying
        return f"⚠️ AI error: {err}"

    # All models failed
    if last_err == "QUOTA":
        return (
            "⚠️ QUOTA_EXHAUSTED — All Gemini free-tier models are quota-exhausted. "
            "Wait 60 seconds and try again, or upgrade at https://aistudio.google.com"
        )
    if last_err in ("TIMEOUT", "NETWORK_ERROR"):
        return "⚠️ NETWORK_ERROR — Could not reach Gemini API. Check your internet connection."
    return f"⚠️ AI unavailable: {last_err}"


def call_gemini_json(prompt: str) -> tuple:
    """
    Call Gemini expecting JSON response.
    Returns (dict, error_str). On success error_str is None.
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
                return {}, f"JSON parse error: {je}. Raw: {text[:200]}"
        last_err = err or ""
        if err in ("QUOTA", "NOT_FOUND", "TIMEOUT", "NETWORK_ERROR"):
            continue
        if err == "NO_KEY":
            return {}, "Gemini API key is invalid."
        return {}, f"AI error ({model}): {err}"

    if last_err == "QUOTA":
        return {}, "QUOTA_EXHAUSTED"
    if last_err in ("TIMEOUT", "NETWORK_ERROR"):
        return {}, "NETWORK_ERROR"
    return {}, f"AI unavailable: {last_err}"


def gemini_quota_warning():
    """Show styled quota warning."""
    st.warning(
        "⏳ **Gemini Free Tier Quota Reached**\n\n"
        "The free Gemini API resets every **60 seconds**. "
        "Please wait a moment and click the button again.\n\n"
        "💡 **Get a new free key:** "
        "[aistudio.google.com](https://aistudio.google.com) → "
        "Get API Key → paste in Streamlit Secrets as `GEMINI_API_KEY`",
        icon="⚠️",
    )


def show_gemini_error(err: str):
    """Show the right error UI based on error type."""
    if not err:
        return
    el = err.lower()
    if any(x in el for x in ["quota", "exhausted", "quota_exhausted", "wait 60"]):
        gemini_quota_warning()
    elif "network_error" in el or "timeout" in el:
        st.error("🌐 Network error — could not reach Gemini API. Check your internet.")
    elif "no_key" in el or "not set" in el or "invalid" in el:
        st.error(
            "🔑 **Gemini API key missing or invalid.**\n\n"
            "Go to Streamlit Cloud → Manage App → Settings → Secrets and add:\n"
            "```\nGEMINI_API_KEY = \"your-key-here\"\n```\n"
            "Get a free key at [aistudio.google.com](https://aistudio.google.com)"
        )
    else:
        st.error(f"❌ {err}")
