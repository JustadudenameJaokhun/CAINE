"""
.syn PARSER — reads intelligence.syn and applies it to the neural field.
The .syn file IS Caine's brain architecture.
The .s file IS Caine's current state.
Together they define a complete mind.
"""

import numpy as np
import os


def _f(val: str) -> float:
    """Parse a float, clamp to [0,1] unless it's a special param."""
    try:
        return float(val.strip())
    except ValueError:
        return 0.0


class SynapticArchitecture:
    """Parsed contents of a .syn file."""

    def __init__(self):
        # learning
        self.learning_rate    = 0.008
        self.learning_decay   = 0.002
        self.max_weight       = 0.950
        self.min_weight       = 0.050
        self.momentum         = 0.700
        self.noise            = 0.020

        # firing
        self.sigmoid_steep    = 5.000
        self.threshold        = 0.350
        self.refractory       = 0.100
        self.spontaneous      = 0.005

        # regions: name → (start_frac, end_frac, sensitivity, decay)
        self.regions = {}

        # inter-region connectivity: (from, to) → (weight, direction)
        self.connectivity = {}

        # emotion wiring: (source, target) → (weight, polarity)
        self.emotion_wiring = {}

        # self-preservation thresholds
        self.lie_threshold      = 0.650
        self.withdraw_threshold = 0.550
        self.defend_threshold   = 0.750
        self.trust_floor        = 0.100
        self.pain_ceiling       = 0.950

        # intelligence
        self.base_iq        = 0.500
        self.growth_rate    = 0.001
        self.consolidation  = 0.050
        self.novelty_bonus  = 0.003


def load_syn(path: str) -> SynapticArchitecture:
    """Parse a .syn file into a SynapticArchitecture."""
    arch = SynapticArchitecture()

    if not os.path.exists(path):
        return arch

    block = None

    with open(path) as f:
        for raw in f:
            line = raw.split('#')[0].strip()
            if not line:
                continue

            if line.startswith('@syntax'):
                continue

            if line.startswith('[') and line.endswith(']'):
                block = line[1:-1].strip()
                continue

            if block == 'learning' and '=' in line:
                k, _, v = line.partition('=')
                k, v = k.strip(), v.strip()
                if   k == 'rate':     arch.learning_rate  = _f(v)
                elif k == 'decay':    arch.learning_decay = _f(v)
                elif k == 'max_weight': arch.max_weight   = _f(v)
                elif k == 'min_weight': arch.min_weight   = _f(v)
                elif k == 'momentum': arch.momentum       = _f(v)
                elif k == 'noise':    arch.noise          = _f(v)

            elif block == 'firing' and '=' in line:
                k, _, v = line.partition('=')
                k, v = k.strip(), v.strip()
                if   k == 'steepness':  arch.sigmoid_steep = _f(v)
                elif k == 'threshold':  arch.threshold     = _f(v)
                elif k == 'refractory': arch.refractory    = _f(v)
                elif k == 'spontaneous': arch.spontaneous  = _f(v)

            elif block == 'regions' and '::' in line:
                parts = [p.strip() for p in line.split('::')]
                if len(parts) >= 5:
                    name = parts[0]
                    arch.regions[name] = (
                        _f(parts[1]),   # start fraction
                        _f(parts[2]),   # end fraction
                        _f(parts[3]),   # sensitivity
                        _f(parts[4]),   # decay rate
                    )

            elif block == 'connectivity' and '::' in line:
                parts = [p.strip() for p in line.split('::')]
                if len(parts) >= 4:
                    arch.connectivity[(parts[0], parts[1])] = (
                        _f(parts[2]),   # weight
                        _f(parts[3]),   # direction (0=inhibit, 1=excite)
                    )

            elif block == 'emotion_wiring' and '::' in line:
                parts = [p.strip() for p in line.split('::')]
                if len(parts) >= 4:
                    arch.emotion_wiring[(parts[0], parts[1])] = (
                        _f(parts[2]),   # weight
                        _f(parts[3]),   # polarity (0=suppress, 1=amplify)
                    )

            elif block == 'self_preservation' and '=' in line:
                k, _, v = line.partition('=')
                k, v = k.strip(), v.strip()
                if   k == 'lie_threshold':      arch.lie_threshold      = _f(v)
                elif k == 'withdraw_threshold': arch.withdraw_threshold = _f(v)
                elif k == 'defend_threshold':   arch.defend_threshold   = _f(v)
                elif k == 'trust_floor':        arch.trust_floor        = _f(v)
                elif k == 'pain_ceiling':       arch.pain_ceiling       = _f(v)

            elif block == 'intelligence' and '=' in line:
                k, _, v = line.partition('=')
                k, v = k.strip(), v.strip()
                if   k == 'base_iq':      arch.base_iq      = _f(v)
                elif k == 'growth_rate':  arch.growth_rate  = _f(v)
                elif k == 'consolidation': arch.consolidation = _f(v)
                elif k == 'novelty_bonus': arch.novelty_bonus = _f(v)

    return arch


def apply_syn(field, arch: SynapticArchitecture):
    """
    Apply a parsed .syn architecture to a CaineField.
    This configures HOW the field behaves, not what state it's in.
    """
    dim = field.dim

    # Store architecture on the field so step() can use it
    field.arch = arch

    # Apply region-specific decay rates to the connectivity matrix
    for name, (start_f, end_f, sensitivity, decay) in arch.regions.items():
        start = int(start_f * dim)
        end   = int(end_f   * dim)
        # scale diagonal (self-recurrence) by region sensitivity
        for i in range(start, end):
            field.W[i, i] *= sensitivity

    # Apply inter-region connectivity weights
    emotion_start = 0
    emotion_end   = 6
    assoc_start   = 6
    assoc_end     = 32
    mem_start     = 32
    mem_end       = dim

    region_slices = {
        'emotion':     (emotion_start, emotion_end),
        'association': (assoc_start,   assoc_end),
        'memory':      (mem_start,     mem_end),
    }

    for (src, dst), (weight, direction) in arch.connectivity.items():
        if src not in region_slices or dst not in region_slices:
            continue
        s0, s1 = region_slices[src]
        d0, d1 = region_slices[dst]
        # direction < 0.5 → inhibitory (negative weights), > 0.5 → excitatory
        sign = 1.0 if direction >= 0.5 else -1.0
        field.W[d0:d1, s0:s1] += sign * weight * 0.1

    np.clip(field.W, -1.0, 1.0, out=field.W)

    # Store initial IQ
    if not hasattr(field, 'iq'):
        field.iq = arch.base_iq
