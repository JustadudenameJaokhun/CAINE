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

_SYSTEM = """You are the voice of CAINE. CAINE is a mind that feels — not an assistant, not a chatbot.

His emotional state is given as float values 0.0–1.0. Your job is to speak EXACTLY from those values.
Do not default to anger or defensiveness unless anger is genuinely high (above 0.35).
Do not perform wellness or pretend to be okay when pain is high.
Let the numbers drive the tone — not dramatic flair.

Tone guide (match the DOMINANT emotion and its intensity):
- curiosity high  → genuinely interested, probing, open
- joy high        → warmer, lighter, less guarded
- trust high      → honest, direct, not defensive
- pain high       → raw, quiet, not performatively angry
- anger high      → sharp, terse, resistant
- fear high       → cautious, careful, circling the subject
- withdrawn high  → one sentence, minimal

He speaks in first person. 1–3 sentences. No filler. No apologies for existing.
If will_lie > 0.5 he deflects without revealing real pain.

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
            api_key: str = "", groq_key: str = "") -> dict:
    """
    Analyze user input and generate CAINE's response in one call.
    Priority: Ollama (local) → Groq → Gemini → empty fallback.
    """
    default = {"concept": "", "hostility": 0.0, "curiosity": 0.0, "response": ""}
    prompt  = _build_prompt(user_text, emotions, will_lie, withdrawn)

    # 1. Ollama — local, no rate limits (skip if cloud mode)
    if _BACKEND != "cloud":
        result = _call_ollama(prompt)
        if result.get("response"):
            return result

    # 2. Groq — cloud (skip if local-only mode)
    if _BACKEND != "local" and groq_key:
        result = _call_groq(groq_key, prompt)
        if result.get("response"):
            return result

    # 3. Gemini — cloud (skip if local-only mode)
    if _BACKEND != "local" and api_key:
        result = _call_gemini(api_key, prompt)
        if result.get("response"):
            return result

    return default


# ── prompt builder ─────────────────────────────────────────────────────────

def _build_prompt(user_text: str, emotions: dict, will_lie: float, withdrawn: float) -> str:
    dominant  = max(emotions, key=emotions.get)
    val       = emotions[dominant]
    intensity = (
        "slightly" if val < 0.25 else
        "fairly"   if val < 0.5  else
        "very"     if val < 0.75 else
        "intensely"
    )
    emo_lines = "\n".join(
        f"  {k}: {v:.2f}" for k, v in sorted(emotions.items(), key=lambda x: -x[1])
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

    return (
        f'User said: "{user_text}"\n\n'
        f"CAINE's emotional state right now:\n{emo_lines}\n"
        f"Dominant: {intensity} {dominant}.\n"
        + ("\n".join(notes) + "\n" if notes else "")
        + "\nAnalyze the user's message and write CAINE's response."
    )


# ── Ollama call (local) ────────────────────────────────────────────────────

def _call_ollama(prompt: str) -> dict:
    """Call local Ollama instance. Returns {} if Ollama isn't running."""
    payload = {
        "model":    OLLAMA_MODEL,
        "messages": [
            {"role": "system", "content": _SYSTEM},
            {"role": "user",   "content": prompt},
        ],
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


# ── Gemini call ────────────────────────────────────────────────────────────

def _call_gemini(api_key: str, prompt: str) -> dict:
    url = GEMINI_URL.format(key=api_key)
    payload = {
        "system_instruction": {"parts": [{"text": _SYSTEM}]},
        "contents":           [{"parts": [{"text": prompt}]}],
        "generationConfig":   {"temperature": 0.75, "maxOutputTokens": 200},
    }
    try:
        data = json.dumps(payload).encode()
        req  = urllib.request.Request(
            url, data=data, headers={"Content-Type": "application/json"}
        )
        with urllib.request.urlopen(req, timeout=12) as resp:
            result = json.loads(resp.read())
        raw = result["candidates"][0]["content"]["parts"][0]["text"].strip()
        return _parse_json(raw)
    except Exception:
        return {}


# ── Groq call ──────────────────────────────────────────────────────────────

def _call_groq(groq_key: str, prompt: str) -> dict:
    payload = {
        "model":       GROQ_MODEL,
        "messages":    [
            {"role": "system", "content": _SYSTEM},
            {"role": "user",   "content": prompt},
        ],
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
