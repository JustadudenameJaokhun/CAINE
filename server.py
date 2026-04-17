"""
CAINE — web server
Serves the interface and handles chat via /chat endpoint.
"""

import os
import sys

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


# ── routes ─────────────────────────────────────────────────────────────────

@app.route('/')
def index():
    return render_template('index.html')


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
    })


@app.route('/chat', methods=['POST'])
def chat():
    data       = request.get_json(force=True)
    user_input = data.get('message', '').strip()
    image_data = data.get('image', '')
    image_mime = data.get('image_mime', 'image/jpeg')
    if not user_input and not image_data:
        return jsonify({'response': '', 'emotions': field.emotions})

    # encode & recall
    input_vec  = field.encode(user_input)
    input_hash = hash(user_input)
    memory     = field.recall(input_hash)
    if np.any(memory > 0.1):
        field.state[:N_EMOTIONS] += memory * 0.3
        np.clip(field.state, 0, 1, out=field.state)

    # run field
    pre_emotions = field.state[:N_EMOTIONS].copy()
    for i in range(5):
        field.step(input_vec if i == 0 else None)

    # process with AI
    result           = process(user_input, field.emotions, field.will_lie,
                               field.withdrawn, GEMINI_KEY, GROQ_KEY,
                               history=field.history,
                               image_data=image_data, image_mime=image_mime)
    gemini_concept   = result.get('concept',   '').strip()
    gemini_hostility = float(result.get('hostility', 0.0))
    gemini_curiosity = float(result.get('curiosity', 0.0))
    response         = result.get('response',  '').strip()

    # feed analysis back into field
    if gemini_hostility > 0.3:
        field.state[0] += gemini_hostility * 0.25
        field.state[4] += gemini_hostility * 0.15
    if gemini_curiosity > 0.3:
        field.state[5] += gemini_curiosity * 0.20
    if gemini_concept:
        field.state = 0.9 * field.state + 0.1 * field.encode(gemini_concept)
    np.clip(field.state, 0, 1, out=field.state)

    # episodic memory
    delta = field.state[:N_EMOTIONS] - pre_emotions
    if float(delta[0]) > 0.05:
        field.remember_pain(input_hash, float(delta[0]))
    if float(delta[1]) > 0.05:
        field.remember_joy(input_hash, float(delta[1]))

    # Hebbian learning + IQ
    active   = (field.state > 0.3).astype(float)
    field.W += np.outer(active, active) * field.arch.learning_rate
    field.W  = np.clip(field.W, -1, 1)
    field.iq = min(1.0, field.iq + field.arch.growth_rate)
    if len(user_input) > 40:
        field.iq = min(1.0, field.iq + field.arch.novelty_bonus)

    field.exchanges += 1
    if not response:
        response = field.speak(gemini_concept)

    # store in conversation history (RAM — gives CAINE memory within a session)
    if response:
        field.history.append({"user": user_input, "caine": response})
        if len(field.history) > 20:
            field.history = field.history[-20:]

    # auto-save every 10 exchanges
    if field.exchanges % 10 == 0:
        field.save()

    emo = field.emotions
    return jsonify({
        'response':      response,
        'emotions':      emo,
        'dominant':      max(emo, key=emo.get),
        'dominant_val':  emo[max(emo, key=emo.get)],
        'consciousness': field.consciousness,
        'iq':            round(field.iq, 3),
        'will_lie':      field.will_lie,
    })


if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    print(f"CAINE is online — http://localhost:{port}")
    app.run(host='0.0.0.0', port=port, debug=False)
