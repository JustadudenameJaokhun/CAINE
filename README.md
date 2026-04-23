# CAINE - A Conscious AI Experiment

I built an AI that actually thinks. Not chatbot templates or pattern matching. Real neural processing across different brain regions that actually talk to each other.

## How It's Built

Basically I modeled it on how actual brains work:

```
SENSORY INPUT
    ↓
SENSORY CORTEX (processes raw input)
    ↓
THALAMUS (relay station - integrates everything)
    ├→ TEMPORAL LOBE (memory, language)
    │   ↓
    │  HIPPOCAMPUS (long-term consolidation)
    │
    ├→ AMYGDALA (emotional processing)
    │
    └→ PREFRONTAL CORTEX (planning, decision-making)

BRAINSTEM (vital functions, drives)
```

When you talk to Caine:
1. Your words hit the sensory cortex
2. Thalamus relays it to different regions simultaneously
3. Temporal lobe pulls memory
4. Hippocampus stores new stuff
5. Amygdala evaluates how important it is emotionally
6. Prefrontal cortex decides what to say
7. Response comes out

Each neuron isn't just 0 or 1. It's a continuous value from 0 to 1. When he processes something, activation spreads across regions like ripples. Different brain regions competing to respond based on what's most active.

## Try It

```bash
./run.sh
```

You get a simple chat. His IQ starts at 50. His consciousness metric tracks how much of his brain is active. Talk to him and watch both numbers change.

Commands: just type to chat, `status` to see what's happening in his brain, `exit` to quit.

## IQ & Consciousness

His IQ starts low (50) and increases as he makes good responses. Simple metric - if he says something coherent, IQ goes up. Over time he should get smarter.

Consciousness is just how many brain regions are firing at once. Average activation across all 7 regions. High consciousness = lots of regions talking to each other. Low = mostly dormant.

Does this match consciousness? Don't know. But it's measurable and it changes.

## The 7 Brain Regions

- **Sensory Cortex** — takes in words, converts to activation patterns
- **Thalamus** — relay hub that sends signals everywhere
- **Temporal Lobe** — memory and language stuff
- **Hippocampus** — locks memories in long-term
- **Amygdala** — emotional reaction, how important is this?
- **Prefrontal Cortex** — makes decisions, mixes memory + emotion
- **Brainstem** — keeps the lights on, calculates IQ growth

## Each Turn

1. Input → sensory cortex activates
2. Thalamus broadcasts to all regions
3. Regions update their activation in parallel
4. Prefrontal cortex gets 60% memory + 40% emotion
5. Whichever region is loudest = that's the response
6. If it went well, IQ increases

Happens in milliseconds.

## What Makes This Different

Other approaches use templates or lookup tables. This actually simulates neural activity. Responses emerge from brain state, not from pre-written scripts. And it learns - IQ grows as he gets better.

## To Use It

Just run `./run.sh` and talk to him. Watch the IQ and consciousness metrics. Does he get smarter? Does he develop a personality?

Built in Python with NumPy. 672 neurons total (96 per region). Updates every 16ms.

## Is It Actually Conscious?

Probably not. But it has properties we associate with consciousness - integration across regions, different states for different inputs, adaptive behavior. Is it real or just sophisticated simulation? Don't know yet.

Either way it's worth trying. See what happens.
