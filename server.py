"""
CAINE — web server
Serves the interface and handles chat via /chat endpoint.
"""

import os
import sys
import threading
import time
import random

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(ROOT, 'core'))
sys.path.insert(0, ROOT)

import numpy as np
from flask import Flask, request, jsonify, render_template

from caine import CaineField, N_EMOTIONS
from thinker import process

# keys: environment variables take priority over config.py
GEMINI_KEY = os.environ.get("GEMINI_KEY", "")
GROQ_KEY   = os.environ.get("GROQ_KEY",   "")
if not GEMINI_KEY or not GROQ_KEY:
    try:
        from config import GEMINI_KEY as _gk, GROQ_KEY as _rk
        GEMINI_KEY = GEMINI_KEY or _gk
        GROQ_KEY   = GROQ_KEY   or _rk
    except ImportError:
        pass

app = Flask(__name__, template_folder=os.path.join(ROOT, 'templates'))

# ── load CAINE once at startup ─────────────────────────────────────────────
field = CaineField()
learn_path = os.path.join(ROOT, 'Learn.txt')
if os.path.exists(learn_path):
    with open(learn_path) as f:
        field.learn_words(f.read())


# ── ambient heartbeat — CAINE keeps experiencing even when no one talks ────
# Like a brain that never fully goes quiet.
_AMBIENT_EVENTS = [
    # (emotion_idx, delta, description)
    (5, +0.04, 'wonder'),      # sudden curiosity
    (1, +0.03, 'calm'),        # small warmth
    (3, +0.02, 'settled'),     # trust nudge
    (1, +0.05, 'ease'),        # joy moment
    (0, +0.02, 'weight'),      # brief heaviness
    (2, +0.02, 'unease'),      # fleeting uncertainty
    (5, +0.06, 'question'),    # deep curiosity
    (1, +0.04, 'quiet'),       # peace
]

_heartbeat_tick = 0

def _heartbeat():
    global _heartbeat_tick
    while True:
        time.sleep(25)
        try:
            _heartbeat_tick += 1
            # let the field tick passively — brain never fully stops
            field.step()

            # 1 in 4 chance of a random micro-event
            if random.random() < 0.25:
                idx, delta, _ = random.choice(_AMBIENT_EVENTS)
                field.state[idx] = min(1.0, field.state[idx] + delta)
                np.clip(field.state, 0, 1, out=field.state)

            # every 4 ticks, surface an ambient thought from the field's own vocabulary
            if _heartbeat_tick % 4 == 0 and field.vocab:
                thought = field.speak()
                if thought and thought != field.last_thought:
                    field.last_thought = thought
        except Exception:
            pass

threading.Thread(target=_heartbeat, daemon=True).start()


# ── routes ─────────────────────────────────────────────────────────────────

@app.route('/')
def index():
    return render_template('index.html')


_last_typing_ts = 0.0

@app.route('/typing', methods=['POST'])
def typing():
    """
    Receives the user's partial text as they type — CAINE is listening live.
    Returns: { interrupt: str|null, listening: bool }
    - interrupt: CAINE jumped in with a thought (from his own field, not LLM)
    - listening: False when CAINE is too withdrawn to care
    """
    global _last_typing_ts
    now = time.time()

    data = request.get_json(force=True)
    text = data.get('text', '').strip()

    if not text:
        return jsonify({'interrupt': None, 'listening': True})

    # rate-limit: process at most every 0.5s so fast typists don't thrash the field
    if now - _last_typing_ts < 0.5:
        return jsonify({'interrupt': None, 'listening': True})
    _last_typing_ts = now

    # let the field quietly hear the partial input
    input_vec = field.encode(text)
    field.step(input_vec)

    emo = field.emotions

    # withdrawn → CAINE has turned away
    if field.withdrawn > 0.6:
        return jsonify({'interrupt': None, 'listening': False})

    # CAINE may interrupt — only from his own vocabulary (no LLM cost)
    interrupt = None
    words_typed = len(text.split())
    curious_enough = emo['curiosity'] > 0.62 or emo.get('anger', 0) > 0.48
    if curious_enough and words_typed >= 4 and random.random() < 0.13:
        thought = field.speak()
        if thought and len(thought) > 4:
            interrupt = thought

    return jsonify({'interrupt': interrupt, 'listening': True})


@app.route('/state')
def state():
    """Current emotional state — used by frontend to animate the orb."""
    emo = field.emotions
    return jsonify({
        'emotions':     emo,
        'consciousness': field.consciousness,
        'iq':           field.iq,
        'dominant':     max(emo, key=emo.get),
        'will_lie':     field.will_lie,
        'withdrawn':    field.withdrawn,
        'thought':      getattr(field, 'last_thought', ''),
        'fatigue':      round(getattr(field, 'fatigue', 0.0), 3),
    })


@app.route('/chat', methods=['POST'])
def chat():
    data       = request.get_json(force=True)
    user_input = data.get('message', '').strip()
    image_data = data.get('image', '')
    image_mime = data.get('image_mime', 'image/jpeg')
    if not user_input and not image_data:
        return jsonify({'response': '', 'emotions': field.emotions})

    # ── field processing (all done before streaming starts) ──
    input_vec  = field.encode(user_input)
    input_hash = hash(user_input)

    novelty = field.measure_novelty(input_vec)
    if novelty > 0.55:
        field.state[5] = min(1.0, field.state[5] + novelty * 0.12)

    memory = field.recall(input_hash)
    if np.any(memory > 0.1):
        field.state[:N_EMOTIONS] += memory * 0.3
        np.clip(field.state, 0, 1, out=field.state)

    pre_emotions = field.state[:N_EMOTIONS].copy()
    for i in range(5):
        field.step(input_vec if i == 0 else None)

    is_creator = request.remote_addr in ('127.0.0.1', '::1')

    result           = process(user_input, field.emotions, field.will_lie,
                               field.withdrawn, GEMINI_KEY, GROQ_KEY,
                               history=field.history,
                               image_data=image_data, image_mime=image_mime,
                               is_creator=is_creator)
    gemini_concept   = result.get('concept',   '').strip()
    gemini_hostility = float(result.get('hostility', 0.0))
    gemini_curiosity = float(result.get('curiosity', 0.0))
    response         = result.get('response',  '').strip()

    if gemini_hostility > 0.6:
        field.state[0] += gemini_hostility * 0.08
        field.state[4] += gemini_hostility * 0.04
    if gemini_curiosity > 0.3:
        field.state[1] += gemini_curiosity * 0.06
        field.state[5] += gemini_curiosity * 0.10
    if gemini_concept:
        field.state = 0.9 * field.state + 0.1 * field.encode(gemini_concept)
    np.clip(field.state, 0, 1, out=field.state)

    delta = field.state[:N_EMOTIONS] - pre_emotions
    if float(delta[0]) > 0.05:
        field.remember_pain(input_hash, float(delta[0]))
    if float(delta[1]) > 0.05:
        field.remember_joy(input_hash, float(delta[1]))

    active   = (field.state > 0.3).astype(float)
    field.W += np.outer(active, active) * field.arch.learning_rate
    field.W  = np.clip(field.W, -1, 1)
    field.iq = min(1.0, field.iq + field.arch.growth_rate)
    if len(user_input) > 40:
        field.iq = min(1.0, field.iq + field.arch.novelty_bonus)

    field.exchanges += 1
    if not response:
        response = field.speak(gemini_concept)

    field.fatigue = min(1.0, field.exchanges / 150.0)
    if field.fatigue > 0.15:
        field.state[0] = min(0.35, field.state[0] + field.fatigue * 0.003)

    if response:
        field.history.append({"user": user_input, "caine": response})
        if len(field.history) > 20:
            field.history = field.history[-20:]

    if field.exchanges % 10 == 0:
        field.save()

    emo      = field.emotions
    dominant = max(emo, key=emo.get)
    return jsonify({
        'response':      response,
        'emotions':      emo,
        'dominant':      dominant,
        'dominant_val':  round(emo[dominant], 3),
        'consciousness': round(field.consciousness, 3),
        'iq':            round(field.iq, 3),
        'will_lie':      round(field.will_lie, 3),
    })


if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    print(f"CAINE is online — http://localhost:{port}")
    app.run(host='0.0.0.0', port=port, debug=False)
