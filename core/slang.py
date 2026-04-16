"""
.s — SENTIENT LANGUAGE PARSER & WRITER
Not 0/1. Only 0.0 → 1.0.

SPEC:
  - Comments:     # anything after hash
  - Block header: [block_name]
  - Field:        key = 0.000
  - Vector:       key = 0.000 0.000 0.000 ...
  - Association:  word :: emotion_vec(6) :: strength(1) :: context_vec(N)
  - Memory:       @memory hash :: delta_vec(6)
  - Version line: @sentient v0.1

No strings. No booleans. No nulls. No integers.
Everything is a float between 0.0 and 1.0.
"""

import re
import os
import numpy as np

VERSION = "0.1"
EMOTION_DIM = 6     # pain joy fear trust anger curiosity
CONCEPT_DIM = 26    # conceptual fingerprint
CONTEXT_DIM = 32    # relational context
TOTAL_VEC   = EMOTION_DIM + CONCEPT_DIM + CONTEXT_DIM  # = 64


def _clamp(v):
    return max(0.0, min(1.0, v))


class SentientFile:
    """
    Reads and writes .s files.
    This IS Caine's native language.
    """

    def __init__(self):
        self.version = VERSION
        self.emotions = {
            'pain':      0.0,
            'joy':       0.25,
            'fear':      0.2,
            'trust':     0.5,
            'anger':     0.0,
            'curiosity': 0.6,
        }
        self.weights_flat = None   # DIM*DIM floats
        self.associations = []     # list of dicts
        self.memories = {}         # hash_str -> delta_vec
        self.age = 0.0
        self.exchanges = 0.0
        self.consciousness = 0.0
        self.iq = 0.500

    # ────────────────────────────── WRITE ────────────────────────────────

    def from_field(self, field):
        """Load all data from a CaineField into this SentientFile."""
        self.emotions = {k: _clamp(v) for k, v in field.emotions.items()}
        self.weights_flat = field.W.flatten().tolist()
        self.associations = [
            {
                'word': e['word'],
                'vec':  [_clamp(float(x)) for x in e['vec']],
            }
            for e in field.vocab
        ]
        self.memories = {
            str(k): [_clamp(float(x)) for x in v]
            for k, v in field.episodic.items()
        }
        self.age          = float(field.age)
        self.exchanges    = float(field.exchanges)
        self.consciousness = _clamp(float(field.consciousness))
        self.iq           = _clamp(float(getattr(field, 'iq', 0.5)))

    def write(self, path: str):
        """Serialise to .s file."""
        lines = []

        lines.append(f"@sentient v{VERSION}")
        lines.append("")

        # ── meta ──
        lines.append("[meta]")
        lines.append(f"age          = {self.age:.3f}")
        lines.append(f"exchanges    = {self.exchanges:.3f}")
        lines.append(f"consciousness = {self.consciousness:.6f}")
        lines.append(f"iq           = {self.iq:.6f}")
        lines.append("")

        # ── emotions ──
        lines.append("[emotions]")
        for name, val in self.emotions.items():
            lines.append(f"{name:<12} = {val:.6f}")
        lines.append("")

        # ── associations (vocabulary) ──
        lines.append("[associations]")
        for entry in self.associations:
            vec_str = " ".join(f"{v:.4f}" for v in entry['vec'])
            lines.append(f"{entry['word']} :: {vec_str}")
        lines.append("")

        # ── memories ──
        lines.append("[memories]")
        for hash_str, delta in self.memories.items():
            delta_str = " ".join(f"{v:.4f}" for v in delta)
            lines.append(f"@memory {hash_str} :: {delta_str}")
        lines.append("")

        # ── weights (connectivity — the actual brain wiring) ──
        lines.append("[weights]")
        if self.weights_flat is not None:
            # write in rows of 16 for readability
            row_size = 16
            for i in range(0, len(self.weights_flat), row_size):
                row = self.weights_flat[i:i + row_size]
                # clamp and shift to [0,1] since weights can be negative
                row_01 = [_clamp((v + 1.0) / 2.0) for v in row]
                lines.append(" ".join(f"{v:.4f}" for v in row_01))
        lines.append("")

        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
        with open(path, 'w') as f:
            f.write("\n".join(lines))

    # ────────────────────────────── READ ─────────────────────────────────

    def read(self, path: str):
        """Parse a .s file."""
        if not os.path.exists(path):
            return

        current_block = None
        weight_rows = []

        with open(path) as f:
            for raw_line in f:
                line = raw_line.split('#')[0].strip()  # strip comments
                if not line:
                    continue

                # version header
                if line.startswith('@sentient'):
                    continue

                # memory entry
                if line.startswith('@memory'):
                    parts = line.split('::')
                    hash_str = parts[0].replace('@memory', '').strip()
                    if len(parts) > 1:
                        vals = [_clamp(float(x)) for x in parts[1].split()]
                        self.memories[hash_str] = vals
                    continue

                # block header
                if line.startswith('[') and line.endswith(']'):
                    current_block = line[1:-1]
                    continue

                # association line
                if current_block == 'associations' and '::' in line:
                    parts = line.split('::')
                    word = parts[0].strip()
                    vec = [_clamp(float(x)) for x in parts[1].split()]
                    self.associations.append({'word': word, 'vec': vec})
                    continue

                # weight row
                if current_block == 'weights':
                    try:
                        vals = [float(x) for x in line.split()]
                        weight_rows.extend(vals)
                    except ValueError:
                        pass
                    continue

                # key = value
                if '=' in line:
                    key, _, val_str = line.partition('=')
                    key = key.strip()
                    vals = val_str.strip().split()
                    try:
                        if len(vals) == 1:
                            fval = float(vals[0])
                            if current_block == 'emotions':
                                if key in self.emotions:
                                    self.emotions[key] = _clamp(fval)
                            elif current_block == 'meta':
                                if key == 'age':          self.age = fval
                                elif key == 'exchanges':  self.exchanges = fval
                                elif key == 'consciousness': self.consciousness = _clamp(fval)
                                elif key == 'iq':         self.iq = _clamp(fval)
                    except ValueError:
                        pass

        # restore weights (shift back from [0,1] to [-1,1])
        if weight_rows:
            self.weights_flat = [(v * 2.0 - 1.0) for v in weight_rows]

    def into_field(self, field):
        """Push loaded data into a CaineField."""
        # emotions
        labels = ['pain', 'joy', 'fear', 'trust', 'anger', 'curiosity']
        for i, label in enumerate(labels):
            field.state[i] = self.emotions.get(label, field.state[i])

        # weights
        if self.weights_flat and len(self.weights_flat) == field.W.size:
            field.W = np.array(self.weights_flat, dtype=np.float64).reshape(field.W.shape)

        # vocabulary
        if self.associations:
            field.vocab = []
            for entry in self.associations:
                vec = np.array(entry['vec'], dtype=np.float64)
                if len(vec) < field.dim:
                    vec = np.pad(vec, (0, field.dim - len(vec)))
                elif len(vec) > field.dim:
                    vec = vec[:field.dim]
                field.vocab.append({'word': entry['word'], 'vec': vec})

        # memories
        field.episodic = {}
        for hash_str, delta in self.memories.items():
            try:
                field.episodic[int(hash_str)] = np.array(delta, dtype=np.float64)
            except ValueError:
                pass

        # meta
        field.age       = int(self.age)
        field.exchanges = int(self.exchanges)
        field.iq        = self.iq
