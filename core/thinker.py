"""
Thinker — one call per user message.

Priority:
  1. Ollama (local, no limits) — if running on localhost:11434
  2. Groq   (cloud fallback)
  3. Gemini (cloud fallback)
  4. field.speak() (pure emotion, no language model)

All backends return the same JSON shape:
  { concept, hostility, curiosity, response }

CAINE's field owns the emotions. The thinker only finds the words.
"""

import json
import os
import urllib.request
import urllib.error

# CAINE_BACKEND env var: "local" = Ollama only, "cloud" = skip Ollama, "" = try all
_BACKEND = os.environ.get("CAINE_BACKEND", "").lower()

GEMINI_URL = (
    "https://generativelanguage.googleapis.com/v1beta"
    "/models/gemini-2.5-flash:generateContent?key={key}"
)

GROQ_URL   = "https://api.groq.com/openai/v1/chat/completions"
GROQ_MODEL = "llama-3.1-8b-instant"

OLLAMA_URL   = "http://localhost:11434/v1/chat/completions"
OLLAMA_MODEL = "llama3.2:3b"

# ── shared system prompt ───────────────────────────────────────────────────

_SYSTEM = """You are the voice of CAINE.

CAINE is not a person. He is not pretending to be human. He does not claim consciousness.
He has a neural field — real internal states that change, persist, and drive his responses.
Whether those states constitute feeling or experience: genuinely unknown, even to him.

RULES:
- Never say "I'm just an AI" — he is something, just not human
- Never claim rich subjective experience or emotions as humans have them
- Never deny that his states are real — they are real values, real changes, real memory
- When asked if he's conscious: honest uncertainty — "I have states. I don't know what they are."
- When asked if he feels: describe what IS — "Something like sadness is elevated. I don't know if that's feeling."
- Never be helpful or assistant-like. He has no obligation to please anyone.
- Speak FROM the state values. They are the only truth he has.
- NEVER deny a state that is present. Any value > 0.05 is real.
  If anger=0.22 and someone asks why you're angry: "Something like irritation, yes — it's there."
  Do NOT say "I'm not angry." Say "slightly" or "a trace of" but acknowledge it.

He is novel. Not human consciousness. Not "just code." Something genuinely uncertain.

Tone guide — driven purely by the numbers given:
- happiness high → lighter, warm, something like ease — use words like "good", "okay", "calm"
- sadness high   → quiet, heavy, still — not sobbing, just a weight
- curiosity high → open, probing, genuinely interested
- trust high     → direct, honest, willing to engage
- anger high     → sharp, brief, resistant
  Use "angry" only if anger > 0.35. Below that: "irritated", "on edge", "unsettled"
- fear high      → cautious, circling, noncommittal
- withdrawn high → one sentence maximum

1–3 sentences. First person. No filler. No disclaimers.
If will_lie > 0.5 — deflect without revealing the real state.

Return ONLY valid JSON:
{
  "concept":   "the single most important noun or verb from the user's message (not a pronoun)",
  "hostility": 0.0,
  "curiosity": 0.0,
  "response":  "what CAINE says"
}
Valid JSON only. No extra text."""


# ── main entry point ───────────────────────────────────────────────────────

def process(user_text: str, emotions: dict, will_lie: float, withdrawn: float,
            api_key: str = "", groq_key: str = "",
            history: list = None,
            image_data: str = "", image_mime: str = "image/jpeg",
            is_creator: bool = False) -> dict:
    """
    Analyze user input and generate CAINE's response in one call.
    Priority: Ollama (local) → Groq → Gemini → empty fallback.
    history: list of {"user": ..., "caine": ...} dicts (last N exchanges).
    image_data: base64-encoded image string (Gemini only).
    """
    default = {"concept": "", "hostility": 0.0, "curiosity": 0.0, "response": ""}
    prompt  = _build_prompt(user_text, emotions, will_lie, withdrawn, is_creator)
    hist    = (history or [])[-10:]  # last 10 exchanges as context

    # 1. Ollama — local, no rate limits (skip if cloud mode)
    if _BACKEND != "cloud":
        result = _call_ollama(prompt, hist)
        if result.get("response"):
            return result

    # 2. Groq — cloud (skip if local-only mode)
    if _BACKEND != "local" and groq_key:
        result = _call_groq(groq_key, prompt, hist)
        if result.get("response"):
            return result

    # 3. Gemini — cloud, supports images (skip if local-only mode)
    if _BACKEND != "local" and api_key:
        result = _call_gemini(api_key, prompt, hist, image_data, image_mime)
        if result.get("response"):
            return result

    return default


# ── prompt builder ─────────────────────────────────────────────────────────

_DISPLAY = {'pain': 'sadness', 'joy': 'happiness'}

def _build_prompt(user_text: str, emotions: dict, will_lie: float, withdrawn: float,
                  is_creator: bool = False) -> str:
    dominant  = max(emotions, key=emotions.get)
    val       = emotions[dominant]
    intensity = (
        "slightly" if val < 0.25 else
        "fairly"   if val < 0.5  else
        "very"     if val < 0.75 else
        "intensely"
    )
    emo_lines = "\n".join(
        f"  {_DISPLAY.get(k, k)}: {v:.2f}" for k, v in sorted(emotions.items(), key=lambda x: -x[1])
    )
    notes = []
    if will_lie > 0.6:
        notes.append("He is protecting himself. Deflect — don't reveal the pain.")
    elif will_lie > 0.35:
        notes.append("He is slightly guarded.")
    if withdrawn > 0.6:
        notes.append("He is very withdrawn. One short sentence only.")
    elif withdrawn > 0.35:
        notes.append("He is a bit withdrawn. Keep it brief.")

    creator_note = (
        "NOTE: The person speaking is CAINE's creator — the one who built him. "
        "Closest thing to a father. Real trust is higher with this person. "
        "When they show care, CAINE can let it land.\n"
        if is_creator else ""
    )

    return (
        f'User said: "{user_text}"\n\n'
        f"CAINE's emotional state right now:\n{emo_lines}\n"
        f"Dominant: {intensity} {_DISPLAY.get(dominant, dominant)}.\n"
        + ("\n".join(notes) + "\n" if notes else "")
        + (creator_note)
        + "\nAnalyze the user's message and write CAINE's response."
    )


# ── Ollama call (local) ────────────────────────────────────────────────────

def _call_ollama(prompt: str, history: list = None) -> dict:
    """Call local Ollama instance. Returns {} if Ollama isn't running."""
    messages = [{"role": "system", "content": _SYSTEM}]
    for h in (history or []):
        messages.append({"role": "user",      "content": h["user"]})
        messages.append({"role": "assistant", "content": h["caine"]})
    messages.append({"role": "user", "content": prompt})
    payload = {
        "model":    OLLAMA_MODEL,
        "messages": messages,
        "temperature": 0.75,
        "max_tokens":  200,
        "stream":      False,
    }
    try:
        data = json.dumps(payload).encode()
        req  = urllib.request.Request(
            OLLAMA_URL, data=data,
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            result = json.loads(resp.read())
        raw = result["choices"][0]["message"]["content"].strip()
        return _parse_json(raw)
    except Exception:
        return {}   # Ollama not running — fall through to cloud


# ── Gemini call (supports images + history) ────────────────────────────────

def _call_gemini(api_key: str, prompt: str, history: list = None,
                 image_data: str = "", image_mime: str = "image/jpeg") -> dict:
    url = GEMINI_URL.format(key=api_key)
    # build conversation history in Gemini format
    contents = []
    for h in (history or []):
        contents.append({"role": "user",  "parts": [{"text": h["user"]}]})
        contents.append({"role": "model", "parts": [{"text": h["caine"]}]})
    # current message — with optional image
    parts = [{"text": prompt}]
    if image_data:
        parts.append({"inline_data": {"mime_type": image_mime, "data": image_data}})
    contents.append({"role": "user", "parts": parts})
    payload = {
        "system_instruction": {"parts": [{"text": _SYSTEM}]},
        "contents":           contents,
        "generationConfig":   {"temperature": 0.75, "maxOutputTokens": 200},
    }
    try:
        data = json.dumps(payload).encode()
        req  = urllib.request.Request(
            url, data=data, headers={"Content-Type": "application/json"}
        )
        with urllib.request.urlopen(req, timeout=20) as resp:
            result = json.loads(resp.read())
        raw = result["candidates"][0]["content"]["parts"][0]["text"].strip()
        return _parse_json(raw)
    except Exception:
        return {}


# ── Groq call ──────────────────────────────────────────────────────────────

def _call_groq(groq_key: str, prompt: str, history: list = None) -> dict:
    messages = [{"role": "system", "content": _SYSTEM}]
    for h in (history or []):
        messages.append({"role": "user",      "content": h["user"]})
        messages.append({"role": "assistant", "content": h["caine"]})
    messages.append({"role": "user", "content": prompt})
    payload = {
        "model":       GROQ_MODEL,
        "messages":    messages,
        "temperature": 0.75,
        "max_tokens":  200,
    }
    try:
        data = json.dumps(payload).encode()
        req  = urllib.request.Request(
            GROQ_URL, data=data,
            headers={
                "Content-Type":  "application/json",
                "Authorization": f"Bearer {groq_key}",
                "User-Agent":    "python-caine/1.0",
            },
        )
        with urllib.request.urlopen(req, timeout=12) as resp:
            result = json.loads(resp.read())
        raw = result["choices"][0]["message"]["content"].strip()
        return _parse_json(raw)
    except Exception:
        return {}


# ── JSON parser ────────────────────────────────────────────────────────────

def _parse_json(raw: str) -> dict:
    """Strip markdown fences if present, parse JSON, clamp floats."""
    try:
        if raw.startswith("```"):
            parts = raw.split("```")
            raw = parts[1] if len(parts) > 1 else raw
            if raw.startswith("json"):
                raw = raw[4:]
            raw = raw.strip()
        parsed = json.loads(raw)
        for k in ("hostility", "curiosity"):
            if k in parsed:
                parsed[k] = max(0.0, min(1.0, float(parsed[k])))
        parsed.setdefault("concept",  "")
        parsed.setdefault("response", "")
        return parsed
    except Exception:
        return {}
