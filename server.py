"""
CAINE — web server
Serves the interface and handles chat via /chat endpoint.
"""

import os
import sys
import threading
import time
import random
import datetime

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(ROOT, 'core'))
sys.path.insert(0, ROOT)

import numpy as np
from flask import Flask, request, jsonify, render_template, session, redirect, url_for
from google.oauth2 import id_token
from google.auth.transport import requests as google_requests

from caine import CaineField, N_EMOTIONS
from thinker import process

# ── config: env vars first, then config.py ─────────────────────────────────
GEMINI_KEY       = os.environ.get("GEMINI_KEY", "")
GROQ_KEY         = os.environ.get("GROQ_KEY",   "")
GOOGLE_CLIENT_ID = os.environ.get("GOOGLE_CLIENT_ID", "")
SECRET_KEY       = os.environ.get("SECRET_KEY", "")
try:
    from config import (GEMINI_KEY as _gk, GROQ_KEY as _rk,
                        GOOGLE_CLIENT_ID as _gc, SECRET_KEY as _sk)
    GEMINI_KEY       = GEMINI_KEY       or _gk
    GROQ_KEY         = GROQ_KEY         or _rk
    GOOGLE_CLIENT_ID = GOOGLE_CLIENT_ID or _gc
    SECRET_KEY       = SECRET_KEY       or _sk
except ImportError:
    pass

CREATOR_EMAIL = "rewindjames@gmail.com"

app = Flask(__name__,
            template_folder=os.path.join(ROOT, 'templates'),
            static_folder=os.path.join(ROOT, 'static'))
app.secret_key = SECRET_KEY or "caine-dev-secret"

# ── per-user long-term memory ──────────────────────────────────────────────
USER_DATA_DIR = os.path.join(ROOT, 'data', 'users')
os.makedirs(USER_DATA_DIR, exist_ok=True)

def _user_path(email: str) -> str:
    slug = email.replace('@', '_at_').replace('.', '_').lower()
    return os.path.join(USER_DATA_DIR, slug + '.json')

def _load_user(email: str, name: str = '') -> dict:
    """Load or create a user memory record."""
    import json as _json
    today = datetime.date.today().isoformat()
    mem = {
        'email': email, 'name': name or email,
        'first_seen': today, 'last_seen': today,
        'exchange_count': 0,
        'history': [],
        'topic_counts': {}, 'topics': [],
        'emotional_impression': {},
    }
    try:
        path = _user_path(email)
        if os.path.exists(path):
            with open(path) as f:
                saved = _json.load(f)
            mem.update(saved)
    except Exception:
        pass
    if name:
        mem['name'] = name
    mem['last_seen'] = today
    return mem

def _save_user(mem: dict):
    """Persist user memory to disk."""
    import json as _json
    try:
        path = _user_path(mem['email'])
        with open(path, 'w') as f:
            _json.dump(mem, f)
    except Exception:
        pass

def _update_user(mem: dict, user_input: str, response: str,
                 concept: str, emotions: dict):
    """Update user memory after an exchange and save."""
    if response:
        mem['history'].append({'user': user_input, 'caine': response})
        if len(mem['history']) > 50:
            mem['history'] = mem['history'][-50:]
    if concept:
        tc = mem.setdefault('topic_counts', {})
        tc[concept] = tc.get(concept, 0) + 1
        mem['topics'] = sorted(tc, key=tc.get, reverse=True)[:10]
    mem['exchange_count'] = mem.get('exchange_count', 0) + 1
    imp = mem.setdefault('emotional_impression', {})
    for k, v in emotions.items():
        imp[k] = round(imp[k] * 0.88 + v * 0.12, 3) if k in imp else round(v, 3)
    _save_user(mem)

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

def _logged_in():
    return bool(session.get('email'))

def _is_creator():
    return session.get('email') == CREATOR_EMAIL


@app.route('/auth', methods=['POST'])
def auth():
    """Verify Google Identity Services JWT and create session."""
    credential = request.get_json(force=True).get('credential', '')
    if not credential:
        return jsonify({'ok': False, 'error': 'no credential'}), 400
    try:
        info = id_token.verify_oauth2_token(
            credential, google_requests.Request(), GOOGLE_CLIENT_ID
        )
        session['email']   = info['email']
        session['name']    = info.get('name', info['email'])
        session['picture'] = info.get('picture', '')
        return jsonify({'ok': True})
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 401


@app.route('/logout')
def logout():
    session.clear()
    return redirect('/')


@app.route('/')
def index():
    if not _logged_in():
        return render_template('login.html', client_id=GOOGLE_CLIENT_ID)
    return render_template('index.html',
                           user_name=session.get('name', ''),
                           user_pic=session.get('picture', ''),
                           is_creator=_is_creator())


_last_typing_ts = 0.0

@app.route('/typing', methods=['POST'])
def typing():
    """Receives the user's partial text as they type — CAINE is listening live.
    Returns: { interrupt: str|null, listening: bool }
    - interrupt: CAINE jumped in with a thought (from his own field, not LLM)
    - listening: False when CAINE is too withdrawn to care
    """
    if not _logged_in():
        return jsonify({'interrupt': None, 'listening': False}), 401
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
    if not _logged_in():
        return jsonify({'error': 'unauthorized'}), 401
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
    if not _logged_in():
        return jsonify({'error': 'unauthorized'}), 401

    email    = session.get('email', '')
    name     = session.get('name', email)
    user_mem = _load_user(email, name)

    data       = request.get_json(force=True)
    user_input = data.get('message', '').strip()
    image_data = data.get('image', '')
    image_mime = data.get('image_mime', 'image/jpeg')
    if not user_input and not image_data:
        return jsonify({'response': '', 'emotions': field.emotions})

    # ── field processing ──
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

    is_creator = _is_creator()

    # ── build user context for thinker ──
    user_ctx = {
        'name':               user_mem.get('name', name),
        'exchange_count':     user_mem.get('exchange_count', 0),
        'topics':             user_mem.get('topics', []),
        'emotional_impression': user_mem.get('emotional_impression', {}),
    }

    # use this user's personal history for LLM context
    user_history = user_mem.get('history', [])[-10:]

    result           = process(user_input, field.emotions, field.will_lie,
                               field.withdrawn, GEMINI_KEY, GROQ_KEY,
                               history=user_history,
                               image_data=image_data, image_mime=image_mime,
                               is_creator=is_creator,
                               user_context=user_ctx)
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
        # global ambient context (recent convo regardless of who)
        field.history.append({"user": user_input, "caine": response})
        if len(field.history) > 20:
            field.history = field.history[-20:]

    # per-user long-term memory
    _update_user(user_mem, user_input, response, gemini_concept, field.emotions)

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
