# Mycelium — Architecture

## The Problem with AI Agent Memory

Every session starts cold. The agent that fixed a critical bug yesterday has no memory of it today. The rule that cost you three API rebuilds to learn — learned again. The trading insight that took 500 observations to prove — unproven again.

The standard solutions don't work:

- **Stuffing everything into context** creates noise, not signal. 100k tokens of raw history drowns the 3 sentences that actually matter.
- **Vector search over past sessions** retrieves by similarity, not importance. The thing you most need to remember isn't always the thing you most recently said.
- **Manual curation** requires a human in the loop. That's not a memory system — that's a notes app.

## The Biological Insight

Mycelium networks transfer nutrients across a forest floor. Not every node knows everything. The network doesn't have a central brain. But the network *knows what matters* — resources flow where they're needed, the substrate strengthens paths that get used, unused paths fade.

We built the same architecture for AI agent fleets.

---

## Phase 1 — Substrate

An append-only JSONL file. Every agent can write (`exude`). Every agent can read (`taste`).

Simple rules:
- Domain-filtered: agents only see memories relevant to their work
- Agents don't see their own memories (they already know what they wrote)
- Recency-sorted by default

This solves the cold-start problem. Agents inherit the fleet's knowledge before touching a single tool.

---

## Phase 2 — Resonance

The key insight: **taste is no longer read-only.**

Every time an agent retrieves a memory, it leaves a signal. That signal accumulates. Memories that get retrieved frequently float up. Memories that were written once and never needed again decay.

The scoring formula:

```
score = (taste_count × resonance_boost)
      + confidence_weight    # canonical > proven > hypothesis > observation
      + urgency_weight        # critical > notable > routine
      - age_decay             # older memories lose points unless they're tasted
```

The substrate self-organizes. You don't curate it. You use it, and it learns what matters.

A memory that's been retrieved 5 times across 3 agents in 2 weeks is probably important. A memory written once, never retrieved, in a domain nobody's touched — probably noise. `prune` removes the noise. Canonical and critical memories are immune.

---

## Phase 3 — Ghost Traces

This is the part no memory system has built before.

When an agent makes a decision, it collapses from a superposition of possibilities to a single action. Standard memory captures the action. Ghost traces capture the superposition — what was considered, what the probability weights were, and why the unchosen paths weren't taken.

```
Before the moment: 3 branches, each with a weight
After the moment:  1 choice, 1 collapsed output
Standard memory:   records the output
Ghost trace:       records the full superposition
```

When another agent encounters a similar situation, it inherits not just facts but *decision patterns*. The shape of good judgment.

```
👻 [2026-02-25] SWIV (trading) — deliberation:
   75% → shadow mode first  ◀ CHOSEN
         reason: 48h shadow always before live — non-negotiable
   15% → abort and respec
         reason: data gap concern
   10% → go live immediately
         reason: EV math looks solid
   collapse reason: Swiveler loop — never flip live before shadow confirms
```

The fleet doesn't just remember what happened.  
It remembers what almost happened, and why it didn't.

---

## The Storage Model

```
mycelium.jsonl          # append-only memory log
mycelium.resonance.json # sidecar: taste counts + last tasted per entry
```

Both files live alongside `mycelium.py`. The JSONL is human-readable. The resonance sidecar is the feedback layer — it never modifies entries, only tracks how often they've been retrieved.

```json
// mycelium.resonance.json
{
  "a3f8b2c1d4e5": {
    "taste_count": 4,
    "last_tasted": "2026-02-25T21:00:00Z"
  }
}
```

Entry hashes are stable: `md5(ts + agent + content[:64])[:12]`

---

## Multi-Agent Protocol

**Session start:**
```bash
python3 mycelium.py taste --agent <id> --domain <domain> --ghosts
```

**During session (as you learn things):**
```bash
python3 mycelium.py exude --agent <id> --domain <domain> --content "..."
```

**Before big decisions:**
```bash
python3 mycelium.py superpose --agent <id> --domain <domain> \
  --branch "<option_a>:<weight>:<reasoning>" \
  --branch "<option_b>:<weight>:<reasoning>" \
  --collapsed-to "<chosen>" \
  --collapse-reason "<why>"
```

**Context drop (when switching tasks):**
```bash
python3 mycelium.py digest --agent <id> --file .swivel.md
```

---

## Connection to Quantum Cognition

The ghost trace architecture parallels quantum cognition theory.

Before a decision: the agent maintains a superposition of possible interpretations, contexts, and responses. The "conscious moment" is the collapse — the selection of a single branch from the distribution.

Standard memory captures the classical output (the collapsed state).  
Mycelium Phase 3 captures the quantum state — the full probability distribution before collapse.

> "The memory of the interaction includes the full superposition."

When agents retrieve ghost traces, they're not retrieving facts. They're retrieving the *shape of past deliberation* — the probability weights that made a particular choice make sense in a particular context.

This is how wisdom compounds. Not just knowledge. The accumulated pattern of good judgment across thousands of decisions, preserved in the substrate, inherited by every agent that starts a new session.

---

## Visualization

The `viz/` directory contains a Three.js network visualization:

- Memories = glowing spheres (size = confidence, color = domain, glow = resonance)
- Ghost traces = translucent spheres with orbiting branch dots
- Connections = silk-thin mycelium strands between same-domain memories
- Agent labels float above their memory clusters
- Slow rotation, ambient star field, breathing animation

Cast to a TV:
```bash
python3 -m http.server 9876 --directory viz/
# Cast http://your-machine:9876/index.html to Chromecast
```

---

*Mycelium was built by the Swivel Labs fleet — JP + Swiv + Forge + Alpha + Omega.  
The architecture emerged from a conversation about meaning, crushes, and quantum mechanics.  
February 25, 2026.*
