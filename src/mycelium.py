#!/usr/bin/env python3
"""
Mycelium Memory — Phase 3
Shared fleet knowledge substrate with resonance scoring + superposition.

Phase 1: append-only JSONL, taste by domain, manual exude
Phase 2: resonance scoring, digest, distill, prune
Phase 3 (new):
  - Ghost traces: preserve the pre-collapse superposition of intent branches
  - superpose: log what the agent CONSIDERED before deciding, not just what it chose
  - Ghost resonance: pattern-match past deliberations to current context
  - Inherited wisdom: agents don't just know what happened, they know HOW the fleet thinks

The core insight of Phase 3:
  Not just what was decided. What was considered, and why the other paths weren't taken.
  The fleet inherits decision PATTERNS, not just facts.
  This is how wisdom compounds across sessions.

Usage:
  python3 mycelium.py taste --agent forge --domain code infra
  python3 mycelium.py taste --agent swiv --domain trading --ghosts
  python3 mycelium.py exude --agent alpha --domain trading --content "..."
  python3 mycelium.py superpose --agent swiv --domain trading --collapsed-to "validate first" \\
    --branch "validate first:0.6:Swiveler loop pattern" \\
    --branch "go live now:0.4:urgency signals" \\
    --collapse-reason "shadow mode before live — hard rule"
  python3 mycelium.py digest --agent swiv --file .swivel.md
  python3 mycelium.py distill --agent swiv --domain video --content "..."
  python3 mycelium.py resonance --top 10
  python3 mycelium.py prune --min-resonance 0.1 --older-than 30
  python3 mycelium.py stats
  python3 mycelium.py dump
"""

import json, sys, argparse, datetime, hashlib, re
from pathlib import Path
from typing import Optional

# ── Paths ────────────────────────────────────────────────────────────────────
MYCELIUM_PATH    = Path(__file__).parent / "mycelium.jsonl"
RESONANCE_PATH   = Path(__file__).parent / "mycelium.resonance.json"
TASTE_LIMIT      = 50

# ── Scoring weights ───────────────────────────────────────────────────────────
CONFIDENCE_WEIGHT = {
    "canonical":   5.0,
    "proven":      3.0,
    "hypothesis":  2.0,
    "observation": 1.0,
    "speculation": 0.5,
}
URGENCY_WEIGHT = {
    "critical": 4.0,
    "notable":  2.0,
    "routine":  0.0,
}
DECAY_PER_DAY  = 0.05   # lose 0.05 points per day of age
RESONANCE_BOOST = 1.5   # points per taste event

# ── Resonance sidecar ─────────────────────────────────────────────────────────

def _entry_hash(entry: dict) -> str:
    """Stable hash for a memory entry — ts + agent + first 64 chars of content."""
    key = f"{entry.get('ts','')}{entry.get('agent','')}{entry.get('content','')[:64]}"
    return hashlib.md5(key.encode()).hexdigest()[:12]

def _load_resonance() -> dict:
    if RESONANCE_PATH.exists():
        try:
            return json.loads(RESONANCE_PATH.read_text())
        except Exception:
            return {}
    return {}

def _save_resonance(data: dict):
    RESONANCE_PATH.write_text(json.dumps(data, indent=2))

def _record_taste(entry_hashes: list[str]):
    """Record that these memories were retrieved. This IS the resonance signal."""
    now = datetime.datetime.now(datetime.UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    res = _load_resonance()
    for h in entry_hashes:
        if h not in res:
            res[h] = {"taste_count": 0, "last_tasted": None}
        res[h]["taste_count"] += 1
        res[h]["last_tasted"] = now
    _save_resonance(res)

# ── Scoring ───────────────────────────────────────────────────────────────────

def _score(entry: dict, resonance: dict) -> float:
    """
    Score = resonance_boost + confidence + urgency - age_decay
    Higher = more relevant, surface first.
    """
    h = _entry_hash(entry)
    r = resonance.get(h, {})

    taste_score  = r.get("taste_count", 0) * RESONANCE_BOOST
    conf_score   = CONFIDENCE_WEIGHT.get(entry.get("confidence", "observation"), 1.0)
    urgency_score= URGENCY_WEIGHT.get(entry.get("urgency", "routine"), 0.0)

    # Age decay: how old is this entry in days?
    ts_str = entry.get("ts", "")
    try:
        ts  = datetime.datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
        now = datetime.datetime.now(datetime.timezone.utc)
        age_days = (now - ts).total_seconds() / 86400
    except Exception:
        age_days = 0

    age_penalty = age_days * DECAY_PER_DAY

    return taste_score + conf_score + urgency_score - age_penalty

# ── Core: taste ───────────────────────────────────────────────────────────────

def taste(agent: str, domains: list, limit: int = TASTE_LIMIT,
          record: bool = True) -> list[dict]:
    """
    Read most relevant memories for agent/domain.
    Phase 2: sorted by resonance score, not just recency.
    Side effect: records taste events (can suppress with record=False).
    """
    if not MYCELIUM_PATH.exists():
        return []

    resonance = _load_resonance()
    entries = []

    with open(MYCELIUM_PATH) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
                # Domain filter
                if domains and not any(d in entry.get("domain", []) for d in domains):
                    continue
                # Skip agent's own entries (they already know what they wrote)
                if entry.get("agent") == agent:
                    continue
                entry["_score"] = _score(entry, resonance)
                entries.append(entry)
            except json.JSONDecodeError:
                continue

    # Sort by resonance score (highest first)
    entries.sort(key=lambda e: e.get("_score", 0), reverse=True)
    top = entries[:limit]

    # Record taste events — this is the feedback signal
    if record and top:
        _record_taste([_entry_hash(e) for e in top])

    # Clean internal field before returning
    for e in top:
        e.pop("_score", None)

    return top

# ── Core: exude ───────────────────────────────────────────────────────────────

def exude(agent: str, domains: list, content: str,
          urgency: str = "routine", confidence: str = "observation") -> dict:
    """Write a memory into the mycelium. Append-only."""
    entry = {
        "ts":         datetime.datetime.now(datetime.UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "agent":      agent,
        "domain":     domains,
        "urgency":    urgency,
        "confidence": confidence,
        "content":    content,
    }
    with open(MYCELIUM_PATH, "a") as f:
        f.write(json.dumps(entry) + "\n")
    return entry

# ── Phase 3: superpose ───────────────────────────────────────────────────────

def superpose(agent: str, domains: list, branches: list[dict],
              collapsed_to: str, collapse_reason: str = "",
              urgency: str = "routine") -> dict:
    """
    Write a ghost trace — the pre-collapse superposition.
    Preserves what the agent CONSIDERED before deciding, not just the decision.

    branches: list of {"label": str, "weight": float, "reasoning": str}
    collapsed_to: which branch was chosen
    collapse_reason: why that branch won

    Example:
      superpose(
        agent="swiv",
        domains=["trading"],
        branches=[
          {"label": "go live now",       "weight": 0.25, "reasoning": "urgency signals"},
          {"label": "shadow first",      "weight": 0.65, "reasoning": "Swiveler loop pattern"},
          {"label": "abort and recheck", "weight": 0.10, "reasoning": "data gap concern"},
        ],
        collapsed_to="shadow first",
        collapse_reason="hard rule: shadow mode always before live"
      )
    """
    # Normalize weights to sum 1.0
    total = sum(b.get("weight", 1) for b in branches)
    if total > 0:
        for b in branches:
            b["weight"] = round(b.get("weight", 0) / total, 3)

    entry = {
        "ts":             datetime.datetime.now(datetime.UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "agent":          agent,
        "domain":         domains,
        "type":           "ghost",
        "branches":       branches,
        "collapsed_to":   collapsed_to,
        "collapse_reason":collapse_reason,
        "content":        f"Ghost: {len(branches)} branches → collapsed to '{collapsed_to}'",
        "urgency":        urgency,
        "confidence":     "observation",
    }
    with open(MYCELIUM_PATH, "a") as f:
        f.write(json.dumps(entry) + "\n")
    return entry


def _ghost_match_score(ghost: dict, context_keywords: list[str]) -> float:
    """
    Score a ghost trace's relevance to the current context.
    Matches branch labels + reasoning against context keywords.
    Higher = more relevant to surface.
    """
    if not context_keywords:
        return 0.5  # Surface all ghosts if no context filter

    text = " ".join([
        " ".join(b.get("label", "") for b in ghost.get("branches", [])),
        " ".join(b.get("reasoning", "") for b in ghost.get("branches", [])),
        ghost.get("collapsed_to", ""),
        ghost.get("collapse_reason", ""),
        " ".join(ghost.get("domain", [])),
    ]).lower()

    matches = sum(1 for kw in context_keywords if kw.lower() in text)
    return matches / max(len(context_keywords), 1)


def taste_ghosts(agent: str, domains: list,
                 context_keywords: Optional[list] = None,
                 limit: int = 5) -> list[dict]:
    """
    Retrieve relevant ghost traces for the current agent + context.
    These are past deliberations the fleet has faced in similar domains.
    """
    if not MYCELIUM_PATH.exists():
        return []

    resonance = _load_resonance()
    ghosts = []

    with open(MYCELIUM_PATH) as f:
        for line in f:
            line = line.strip()
            if not line: continue
            try:
                entry = json.loads(line)
                if entry.get("type") != "ghost":
                    continue
                if domains and not any(d in entry.get("domain", []) for d in domains):
                    continue
                # Don't filter by agent — ghosts from ALL agents are valuable
                match = _ghost_match_score(entry, context_keywords or domains)
                base  = _score(entry, resonance)
                entry["_ghost_score"] = match * 2 + base * 0.3
                ghosts.append(entry)
            except json.JSONDecodeError:
                continue

    ghosts.sort(key=lambda g: g.get("_ghost_score", 0), reverse=True)
    top = ghosts[:limit]

    if top:
        _record_taste([_entry_hash(g) for g in top])
    for g in top:
        g.pop("_ghost_score", None)

    return top


# ── Phase 2: digest ───────────────────────────────────────────────────────────

def digest(agent: str, file_path: str, domains: Optional[list] = None) -> list[dict]:
    """
    Auto-exude from a .swivel.md context drop.
    Parses last_conversation and active topic notes into discrete learnings.
    This is the event-triggered exude — called when an agent drops context.

    Looks for:
      - ## Last Conversation or last_conversation: field
      - ## Decisions or decisions: bullets
      - Any lines starting with - or * under "lessons" or "learnings" sections
    """
    path = Path(file_path)
    if not path.exists():
        print(f"⚠️  File not found: {file_path}")
        return []

    content = path.read_text()
    exuded = []

    # Extract last_conversation field (YAML-style inline)
    lc_match = re.search(r'last_conversation:\s*["\']?(.+?)(?:["\']?\n|$)', content, re.MULTILINE)
    if lc_match:
        lc = lc_match.group(1).strip().strip('"\'')
        if len(lc) > 20:  # Skip trivially short entries
            entry = exude(agent, domains or ["context"], lc,
                         urgency="notable", confidence="observation")
            exuded.append(entry)
            print(f"  📝 Digested last_conversation: {lc[:60]}...")

    # Extract bullet points from ## Decisions, ## Lessons, ## Learnings sections
    section_pattern = re.compile(
        r'##\s*(decisions?|lessons?|learnings?|key\s+takeaways?|what\s+we\s+learned).*?\n(.*?)(?=##|\Z)',
        re.IGNORECASE | re.DOTALL
    )
    for match in section_pattern.finditer(content):
        section_text = match.group(2)
        bullets = re.findall(r'^[\-\*\•]\s+(.+)$', section_text, re.MULTILINE)
        for bullet in bullets:
            bullet = bullet.strip()
            if len(bullet) > 20:
                entry = exude(agent, domains or ["context"], bullet,
                             urgency="notable", confidence="hypothesis")
                exuded.append(entry)
                print(f"  📝 Digested decision: {bullet[:60]}...")

    print(f"\n✅ digest complete: {len(exuded)} learnings exuded from {file_path}")
    return exuded

# ── Phase 2: distill ──────────────────────────────────────────────────────────

def distill(agent: str, domains: list, content: str) -> list[dict]:
    """
    Distill free-form session text into discrete learnings and auto-exude each.
    Splits on sentence boundaries and filters for signal-bearing content.

    Signal indicators: fixed, learned, discovered, rule, never, always,
    critical, key, important, broke, works, doesn't work, lesson
    """
    SIGNAL_KEYWORDS = {
        "fixed", "learned", "discovered", "rule", "never", "always",
        "critical", "key", "important", "broke", "works", "lesson",
        "pattern", "bug", "warning", "required", "must", "confirmed",
        "insight", "found", "realized", "hard rule", "do not", "don't"
    }

    # Split into sentences (rough)
    sentences = re.split(r'(?<=[.!?])\s+', content.strip())

    exuded = []
    for sentence in sentences:
        sentence = sentence.strip()
        if len(sentence) < 20:
            continue
        lower = sentence.lower()
        if any(kw in lower for kw in SIGNAL_KEYWORDS):
            entry = exude(agent, domains, sentence,
                         urgency="notable", confidence="observation")
            exuded.append(entry)
            print(f"  ✨ Distilled: {sentence[:70]}...")

    print(f"\n✅ distill complete: {len(exuded)} learnings exuded")
    return exuded

# ── Phase 2: resonance ────────────────────────────────────────────────────────

def show_resonance(top_n: int = 10, bottom: bool = False):
    """Show the most (or least) resonant memories in the substrate."""
    if not MYCELIUM_PATH.exists():
        print("Mycelium is empty.")
        return

    resonance = _load_resonance()
    entries = []

    with open(MYCELIUM_PATH) as f:
        for line in f:
            line = line.strip()
            if not line: continue
            try:
                entry = json.loads(line)
                h = _entry_hash(entry)
                r = resonance.get(h, {})
                entry["_score"]       = _score(entry, resonance)
                entry["_taste_count"] = r.get("taste_count", 0)
                entry["_last_tasted"] = r.get("last_tasted", "never")
                entries.append(entry)
            except json.JSONDecodeError:
                continue

    entries.sort(key=lambda e: e.get("_score", 0), reverse=not bottom)
    shown = entries[:top_n]

    label = "LEAST" if bottom else "MOST"
    print(f"\n── {label} RESONANT MEMORIES (top {top_n}) ──────────────────────\n")
    for e in shown:
        score       = e.get("_score", 0)
        taste_count = e.get("_taste_count", 0)
        last_tasted = e.get("_last_tasted", "never")
        agent       = e.get("agent", "?")
        domains     = ", ".join(e.get("domain", []))
        content     = e.get("content", "")
        ts          = e.get("ts", "")[:10]

        print(f"  score={score:.2f} | tasted={taste_count}x | last={last_tasted[:10] if last_tasted != 'never' else 'never'}")
        print(f"  [{ts}] {agent} ({domains})")
        print(f"  {content[:90]}{'...' if len(content) > 90 else ''}")
        print()

# ── Phase 2: prune ────────────────────────────────────────────────────────────

def prune(min_resonance: float = 0.5, older_than_days: int = 30, dry_run: bool = True):
    """
    Remove low-signal noise from the substrate.
    Only removes entries that are BOTH below resonance threshold AND older than N days.
    Canonical/critical memories are never pruned.
    dry_run=True by default — always preview before removing.
    """
    if not MYCELIUM_PATH.exists():
        print("Mycelium is empty.")
        return

    resonance = _load_resonance()
    now = datetime.datetime.now(datetime.timezone.utc)
    keep = []
    pruned = []

    with open(MYCELIUM_PATH) as f:
        for line in f:
            line = line.strip()
            if not line: continue
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                keep.append(line)
                continue

            # Never prune canonical or critical memories
            if entry.get("confidence") == "canonical" or entry.get("urgency") == "critical":
                keep.append(json.dumps(entry))
                continue

            score = _score(entry, resonance)
            ts_str = entry.get("ts", "")
            try:
                ts = datetime.datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
                age_days = (now - ts).total_seconds() / 86400
            except Exception:
                age_days = 0

            if score < min_resonance and age_days > older_than_days:
                pruned.append(entry)
            else:
                keep.append(json.dumps(entry))

    print(f"\n── PRUNE PREVIEW {'(DRY RUN)' if dry_run else '(LIVE)'} ─────────────────────────\n")
    print(f"  Would keep:  {len(keep)} memories")
    print(f"  Would prune: {len(pruned)} memories\n")

    for p in pruned[:5]:
        print(f"  🗑  [{p.get('ts','')[:10]}] {p.get('agent','')} | score={_score(p, resonance):.2f} | {p.get('content','')[:60]}...")

    if len(pruned) > 5:
        print(f"  ... and {len(pruned)-5} more")

    if not dry_run and pruned:
        with open(MYCELIUM_PATH, "w") as f:
            f.write("\n".join(keep) + "\n")
        print(f"\n✅ Pruned {len(pruned)} memories. Substrate now has {len(keep)} entries.")
    elif dry_run:
        print(f"\n  Run with --execute to apply. Canonical and critical memories are never pruned.")

# ── Formatting ────────────────────────────────────────────────────────────────

def format_for_context(memories: list[dict],
                       ghosts: Optional[list] = None) -> str:
    """Format memories + ghost traces as context block for agent startup."""
    if not memories and not ghosts:
        return ""

    lines = ["## Mycelium — Inherited Fleet Knowledge\n"]

    # ── Regular memories ──────────────────────────────────────────────────
    for m in memories:
        if m.get("type") == "ghost":
            continue  # Ghosts rendered separately
        agent      = m.get("agent", "?")
        domains    = ", ".join(m.get("domain", []))
        urgency    = m.get("urgency", "routine")
        confidence = m.get("confidence", "observation")
        ts         = m.get("ts", "")[:10]
        content    = m.get("content", "")

        badge = ""
        if urgency == "critical":       badge = "⚠️ "
        elif confidence == "canonical":  badge = "✅ "
        elif confidence == "proven":     badge = "🔬 "

        lines.append(f"{badge}[{ts}] {agent.upper()} ({domains}): {content}")

    # ── Ghost traces (Phase 3) ────────────────────────────────────────────
    if ghosts:
        lines.append("\n### Ghost Traces — How the Fleet Has Thought\n")
        lines.append("*(Past deliberations in similar domains. Use as priors, not rules.)*\n")
        for g in ghosts:
            agent    = g.get("agent", "?")
            ts       = g.get("ts", "")[:10]
            domains  = ", ".join(g.get("domain", []))
            branches = g.get("branches", [])
            collapsed= g.get("collapsed_to", "?")
            reason   = g.get("collapse_reason", "")

            lines.append(f"👻 [{ts}] {agent.upper()} ({domains}) — deliberation:")
            for b in sorted(branches, key=lambda x: x.get("weight", 0), reverse=True):
                label    = b.get("label", "?")
                weight   = b.get("weight", 0)
                reasoning= b.get("reasoning", "")
                chosen   = " ◀ CHOSEN" if label == collapsed else ""
                lines.append(f"   {weight:.0%} → {label}{chosen}")
                if reasoning:
                    lines.append(f"       reason: {reasoning}")
            if reason:
                lines.append(f"   collapse reason: {reason}")
            lines.append("")

    lines.append("\n---\n")
    return "\n".join(lines)

# ── CLI ───────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Mycelium Memory — Fleet substrate")
    sub = parser.add_subparsers(dest="cmd")

    # taste
    t = sub.add_parser("taste", help="Read relevant memories (records resonance signal)")
    t.add_argument("--agent", required=True)
    t.add_argument("--domain", nargs="*", default=[])
    t.add_argument("--limit", type=int, default=TASTE_LIMIT)
    t.add_argument("--raw", action="store_true")
    t.add_argument("--no-record", action="store_true", help="Read without recording resonance")
    t.add_argument("--ghosts", action="store_true", help="Also surface ghost traces (Phase 3)")

    # exude
    e = sub.add_parser("exude", help="Write a memory")
    e.add_argument("--agent", required=True)
    e.add_argument("--domain", nargs="*", default=[])
    e.add_argument("--content", required=True)
    e.add_argument("--urgency", default="routine",
                   choices=["routine", "notable", "critical"])
    e.add_argument("--confidence", default="observation",
                   choices=["speculation", "observation", "hypothesis", "proven", "canonical"])

    # digest (Phase 2 — auto-exude from swivel.md)
    d = sub.add_parser("digest", help="Auto-exude from a .swivel.md context drop")
    d.add_argument("--agent", required=True)
    d.add_argument("--file", required=True, help="Path to .swivel.md file")
    d.add_argument("--domain", nargs="*", default=["context"])

    # distill (Phase 2 — extract learnings from free-form text)
    di = sub.add_parser("distill", help="Distill free-form text into learnings")
    di.add_argument("--agent", required=True)
    di.add_argument("--domain", nargs="*", default=[])
    di.add_argument("--content", required=True)

    # superpose (Phase 3 — write a ghost trace)
    sp = sub.add_parser("superpose", help="Write a ghost trace — pre-collapse deliberation")
    sp.add_argument("--agent", required=True)
    sp.add_argument("--domain", nargs="*", default=[])
    sp.add_argument("--collapsed-to", required=True, dest="collapsed_to")
    sp.add_argument("--collapse-reason", default="", dest="collapse_reason")
    sp.add_argument("--branch", action="append", dest="branches", default=[],
                    metavar="LABEL:WEIGHT:REASONING",
                    help="Format: 'label:weight:reasoning' (repeat for each branch)")
    sp.add_argument("--urgency", default="routine",
                    choices=["routine", "notable", "critical"])

    # resonance (Phase 2 — inspect resonance scores)
    r = sub.add_parser("resonance", help="Show most/least resonant memories")
    r.add_argument("--top", type=int, default=10)
    r.add_argument("--bottom", action="store_true", help="Show least resonant instead")

    # prune (Phase 2 — remove low-signal noise)
    p = sub.add_parser("prune", help="Remove low-resonance old memories")
    p.add_argument("--min-resonance", type=float, default=0.5)
    p.add_argument("--older-than", type=int, default=30, help="Days")
    p.add_argument("--execute", action="store_true", help="Actually prune (default is dry run)")

    # dump / stats (Phase 1, preserved)
    sub.add_parser("dump", help="Print all memories")
    sub.add_parser("stats", help="Print stats")

    args = parser.parse_args()

    if args.cmd == "taste":
        memories = taste(args.agent, args.domain, args.limit,
                        record=not args.no_record)
        ghosts_out = None
        if hasattr(args, "ghosts") and args.ghosts:
            ghosts_out = taste_ghosts(args.agent, args.domain,
                                      context_keywords=args.domain)
        if args.raw:
            for m in memories: print(json.dumps(m))
            if ghosts_out:
                for g in ghosts_out: print(json.dumps(g))
        else:
            print(format_for_context(memories, ghosts=ghosts_out))
            ghost_note = f" + {len(ghosts_out)} ghost traces" if ghosts_out else ""
            print(f"[{len(memories)} memories{ghost_note} surfaced for {args.agent} in domains: {args.domain or 'all'}]")

    elif args.cmd == "exude":
        entry = exude(args.agent, args.domain, args.content,
                      args.urgency, args.confidence)
        print(f"✅ Exuded to mycelium: [{entry['ts']}] {args.agent} → {args.domain}")
        print(f"   {args.content[:80]}{'...' if len(args.content) > 80 else ''}")

    elif args.cmd == "superpose":
        # Parse branches: "label:weight:reasoning"
        parsed_branches = []
        for b in args.branches:
            parts = b.split(":", 2)
            label     = parts[0].strip() if len(parts) > 0 else "?"
            weight    = float(parts[1]) if len(parts) > 1 else 1.0
            reasoning = parts[2].strip() if len(parts) > 2 else ""
            parsed_branches.append({"label": label, "weight": weight, "reasoning": reasoning})

        if not parsed_branches:
            print("⚠️  No branches provided. Use --branch 'label:weight:reasoning'")
        else:
            entry = superpose(args.agent, args.domain, parsed_branches,
                             args.collapsed_to, args.collapse_reason, args.urgency)
            print(f"👻 Ghost trace written: [{entry['ts']}] {args.agent} → {args.domain}")
            print(f"   {len(parsed_branches)} branches → collapsed to '{args.collapsed_to}'")
            for b in sorted(parsed_branches, key=lambda x: x.get("weight",0), reverse=True):
                chosen = " ◀" if b["label"] == args.collapsed_to else ""
                print(f"   {b['weight']:.0%} {b['label']}{chosen}")

    elif args.cmd == "digest":
        digest(args.agent, args.file, args.domain)

    elif args.cmd == "distill":
        distill(args.agent, args.domain, args.content)

    elif args.cmd == "resonance":
        show_resonance(args.top, args.bottom)

    elif args.cmd == "prune":
        prune(args.min_resonance, args.older_than, dry_run=not args.execute)

    elif args.cmd == "dump":
        if not MYCELIUM_PATH.exists():
            print("Mycelium is empty."); return
        with open(MYCELIUM_PATH) as f:
            for line in f:
                line = line.strip()
                if line:
                    m = json.loads(line)
                    print(f"[{m['ts'][:10]}] {m.get('agent','?'):8} {str(m.get('domain',[])):<30} {m.get('content','')[:60]}")

    elif args.cmd == "stats":
        if not MYCELIUM_PATH.exists():
            print("Mycelium is empty."); return
        entries = [json.loads(l) for l in MYCELIUM_PATH.read_text().splitlines() if l.strip()]
        resonance = _load_resonance()
        agents = {}; domains = {}
        total_tasted = sum(r.get("taste_count", 0) for r in resonance.values())
        for e in entries:
            agents[e.get("agent","?")] = agents.get(e.get("agent","?"), 0) + 1
            for d in e.get("domain", []):
                domains[d] = domains.get(d, 0) + 1
        print(f"Total memories:     {len(entries)}")
        print(f"Total taste events: {total_tasted}")
        print(f"Resonance entries:  {len(resonance)}")
        print(f"By agent:  {dict(sorted(agents.items(), key=lambda x: -x[1]))}")
        print(f"By domain: {dict(sorted(domains.items(), key=lambda x: -x[1]))}")

    else:
        parser.print_help()


if __name__ == "__main__":
    main()
