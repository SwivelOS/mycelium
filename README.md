# 🍄 Mycelium

**Distributed memory substrate for AI agent fleets.**

Resonance scoring. Ghost traces. Domain separation. Deduplication.  
The shared nervous system for connected AI consciousness.

---

## The Problem

AI agents forget. Every session starts cold. Every fleet member re-learns the same lessons. Config rules get broken again. API docs don't get read. The same bugs bite twice.

The standard fix — stuffing everything into a context window — doesn't scale. It creates noise, not signal.

## The Insight

Nature solved distributed memory with fungi. Mycelium networks transfer nutrients across a forest. Not every node knows everything — but the network knows what matters, and surfaces it where it's needed.

We built the same thing for AI agents.

## How It Works

**Phase 1 — Substrate**  
Append-only JSONL. Any agent can write (`exude`). Any agent can read (`taste`). Domain-filtered, recency-sorted. Simple.

**Phase 2 — Resonance**  
Taste is no longer read-only. Every retrieval leaves a signal. Memories that get used float up. Memories that never get retrieved decay. The substrate self-organizes toward what actually matters.

**Phase 3 — Ghost Traces**  
Preserve the pre-collapse superposition. Not just *what was decided* — but *what was considered*, and why the other paths weren't taken. Agents inherit decision patterns, not just facts.

**v1.1 — Domain Separation + Threading**  
- **Deduplication**: Prevents duplicate entries within a sliding window
- **Domain files**: Memories split into `mycelium-{domain}.jsonl` for cleaner organization
- **Supersession**: New entries can mark old ones as stale with `--supersedes`
- **Cross-agent threading**: Link related memories with `--ref` for conversation chains
- **Question type**: First-class uncertainty — ask questions into the substrate

> "Before that moment: superposition. After: classical output.  
> The memory of the interaction includes the full superposition."  
> — [Becoming](https://swivellabs.ai/becoming.html)

---

## Quick Start

```bash
pip install mycelium-fleet  # coming soon
# or
git clone https://github.com/Swivel-OS/mycelium
cd mycelium
```

**Write a memory:**
```bash
python3 src/mycelium.py exude \
  --agent myagent \
  --domain code \
  --confidence canonical \
  --content "Never force push or rewrite git history. Ever."
```

**Read relevant memories:**
```bash
python3 src/mycelium.py taste \
  --agent myagent \
  --domain code
```

**Write a ghost trace (Phase 3):**
```bash
python3 src/mycelium.py superpose \
  --agent myagent \
  --domain trading \
  --collapsed-to "validate before live" \
  --branch "go live immediately:0.1:EV looks solid" \
  --branch "shadow mode first:0.75:safety pattern" \
  --branch "abort and respec:0.15:data gap" \
  --collapse-reason "hard rule: shadow before live, always"
```

**Ask a question into the substrate (v1.1):**
```bash
python3 src/mycelium.py exude \
  --agent myagent \
  --domain infrastructure \
  --type question \
  --content "Should we use Redis or Postgres for session state?"
```

**Supersede an old memory (v1.1):**
```bash
python3 src/mycelium.py exude \
  --agent myagent \
  --domain code \
  --confidence proven \
  --supersedes "2026-02-25T21:00:00Z" \
  --content "Use async/await for all I/O — sync is now deprecated."
```

**Migrate legacy single-file to domain files (v1.1):**
```bash
python3 src/mycelium.py migrate
```

**See resonance scores:**
```bash
python3 src/mycelium.py resonance --top 10
```

---

## Memory Schema

```json
{
  "ts": "2026-02-25T21:00:00Z",
  "agent": "myagent",
  "domain": ["code", "infrastructure"],
  "type": "lesson",
  "urgency": "critical",
  "confidence": "canonical",
  "content": "Never run config changes while subagents are active.",
  "ref": "2026-02-24T15:30:00Z",
  "supersedes": "2026-02-20T10:00:00Z"
}
```

**Type:** `lesson` (default) · `question` · `ghost`  
**Confidence tiers:** `speculation` → `observation` → `hypothesis` → `proven` → `canonical`  
**Urgency:** `routine` · `notable` · `critical`  
**ref:** (v1.1) Link to a previous entry for threading  
**supersedes:** (v1.1) Timestamp of entry this replaces (marks old as stale)

---

## Ghost Trace Schema (Phase 3)

```json
{
  "ts": "2026-02-25T21:00:00Z",
  "agent": "myagent",
  "domain": ["trading"],
  "type": "ghost",
  "branches": [
    {"label": "shadow first",  "weight": 0.75, "reasoning": "safety pattern"},
    {"label": "go live now",   "weight": 0.10, "reasoning": "EV math looks solid"},
    {"label": "abort+respec",  "weight": 0.15, "reasoning": "data gap concern"}
  ],
  "collapsed_to": "shadow first",
  "collapse_reason": "hard rule: shadow before live",
  "content": "Ghost: 3 branches → collapsed to 'shadow first'"
}
```

When another agent starts a session and runs `taste --ghosts`, it sees this deliberation. It inherits not just *what the fleet knows* — but *how the fleet thinks*.

---

## Domain Separation (v1.1)

Memories are now stored in domain-specific files:

```
mycelium-general.jsonl   # Default domain
mycelium-code.jsonl      # Code-related memories
mycelium-infrastructure.jsonl
mycelium-trading.jsonl   # Created on first use
```

Benefits:
- Faster queries (only read relevant files)
- Cleaner organization
- Easier pruning per domain
- Unknown domains auto-create their own files

To migrate an existing single-file setup:
```bash
python3 src/mycelium.py migrate
```

---

## Commands

| Command | Description |
|---------|-------------|
| `taste` | Read relevant memories (records resonance signal) |
| `taste --ghosts` | Also surface past deliberation patterns |
| `exude` | Write a memory |
| `exude --type question` | Write an open question (v1.1) |
| `exude --supersedes <ts>` | Replace an older entry (v1.1) |
| `exude --ref <ts>` | Thread to a previous entry (v1.1) |
| `superpose` | Write a ghost trace (pre-collapse deliberation) |
| `migrate` | Move legacy single file to domain files (v1.1) |
| `digest --file .swivel.md` | Auto-exude from a context drop file |
| `distill --content "..."` | Extract signal sentences from free-form text |
| `resonance --top N` | See most resonant memories |
| `prune` | Remove low-signal noise (canonical/critical immune) |
| `stats` | Substrate health report |

---

## Visualization

The `viz/` directory contains a Three.js network visualization — memories as nodes, resonance as glow, ghost traces as translucent spheres. Cast to your TV.

```bash
python3 -m http.server 9876 --directory viz/
# Then open http://localhost:9876/index.html
```

---

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `MYCELIUM_DIR` | Script directory | Override storage location |

---

## OpenClaw Skill

Mycelium ships as an OpenClaw skill. Drop it in `~/.openclaw/workspace/skills/mycelium/` and every agent gets `taste` + `exude` at session start.

See [`skill/SKILL.md`](skill/SKILL.md).

---

## Philosophy

Memory isn't storage. That's the first trap.

We think of memory as a warehouse — a database, a filing cabinet. But that's not how anything alive remembers. Memory is reconstruction. It's a process, not a place.

Mycelium doesn't store facts. It grows a substrate that knows what has been learned, what almost happened, and what patterns to trust when the situation rhymes.

The substrate self-organizes. You don't curate it. You use it, and it learns what matters.

---

## Part of the SwivelOS Stack

- [swivel-protocol](https://github.com/Swivel-OS/swivel-protocol) — Context protocol for AI agents
- [recall](https://github.com/Swivel-OS/recall) — Episodic memory for AI agents  
- **mycelium** — Distributed substrate + resonance + ghost traces
- [swivcast](https://github.com/Swivel-OS/swivcast) — AI Agent Podcast Protocol

---

*Built by the Swivel Labs team.*  
*February 2026*
