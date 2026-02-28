#!/usr/bin/env python3
"""
Mycelium Memory — v1.1
Shared knowledge substrate for AI agent fleets with resonance scoring + superposition.

v1.1 Features:
  - Dedup filter: prevent duplicate entries (content hash check)
  - Domain separation: split into mycelium-{domain}.jsonl files
  - Supersession field: entries can supersede older ones (marks old as stale)
  - Cross-agent threading: ref field for traceable conversation chains
  - Question type: first-class uncertainty in the network

Phase 1: append-only JSONL, taste by domain, manual exude
Phase 2: resonance scoring, digest, distill, prune
Phase 3: ghost traces (pre-collapse superposition), inherited decision patterns

Usage:
  python3 mycelium.py taste --agent myagent --domain code infra
  python3 mycelium.py taste --agent myagent --domain trading --ghosts
  python3 mycelium.py exude --agent myagent --domain code --content "..."
  python3 mycelium.py exude --agent myagent --domain code --type question --content "Should we use async here?"
  python3 mycelium.py superpose --agent myagent --domain trading --collapsed-to "validate first" \\
    --branch "validate first:0.6:safety pattern" \\
    --branch "go live now:0.4:urgency signals" \\
    --collapse-reason "shadow mode before live — hard rule"
  python3 mycelium.py migrate  # migrate legacy single-file to domain files
  python3 mycelium.py stats
"""

import json, sys, argparse, datetime, hashlib, re, os
from pathlib import Path
from typing import Optional
from collections import deque

# ── Paths ────────────────────────────────────────────────────────────────────
# Default: store in same directory as script. Override with MYCELIUM_DIR env var.
MYCELIUM_DIR = Path(os.environ.get("MYCELIUM_DIR", Path(__file__).parent))
MYCELIUM_PATH = MYCELIUM_DIR / "mycelium.jsonl"  # Legacy single-file path
RESONANCE_PATH = MYCELIUM_DIR / "mycelium.resonance.json"

# v1.1: Domain-based file separation
# Add your domains here. Entries go to mycelium-{domain}.jsonl
DEFAULT_DOMAINS = ["general", "code", "infrastructure"]

def _get_domain_files() -> dict:
    """Get domain -> path mapping. Creates files on demand."""
    return {d: MYCELIUM_DIR / f"mycelium-{d}.jsonl" for d in DEFAULT_DOMAINS}

TASTE_LIMIT = 50
DEDUP_WINDOW = 100  # Check last N entries for duplicates
_recent_hashes: dict[str, deque] = {}

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
DECAY_PER_DAY = 0.05
RESONANCE_BOOST = 1.5

# ── v1.1: Domain file helpers ─────────────────────────────────────────────────

def _get_domain_path(domain: str | list) -> Path:
    """Get the file path for a domain. Falls back to 'general' for unknown domains."""
    if isinstance(domain, list):
        domain = domain[0] if domain else "general"
    domain = domain.lower()
    domain_files = _get_domain_files()
    if domain in domain_files:
        return domain_files[domain]
    # Unknown domain → create new file for it
    return MYCELIUM_DIR / f"mycelium-{domain}.jsonl"

# ── v1.1: Dedup ───────────────────────────────────────────────────────────────

def _content_hash(entry: dict) -> str:
    """Hash the semantic content of an entry for dedup."""
    content_parts = [
        entry.get("type", "lesson"),
        str(entry.get("domain", [])),
        entry.get("content", ""),
        entry.get("confidence", "observation"),
        entry.get("urgency", "routine"),
    ]
    key = "|".join(content_parts)
    return hashlib.md5(key.encode()).hexdigest()[:16]

def _is_duplicate(domain: str, entry: dict) -> bool:
    """Check if this entry is a duplicate of a recent one."""
    h = _content_hash(entry)
    if domain not in _recent_hashes:
        _recent_hashes[domain] = deque(maxlen=DEDUP_WINDOW)
    if h in _recent_hashes[domain]:
        return True
    _recent_hashes[domain].append(h)
    return False

def _load_domain_hashes(domain: str):
    """Warm the dedup cache from existing domain file."""
    path = _get_domain_path(domain)
    if not path.exists():
        return
    if domain not in _recent_hashes:
        _recent_hashes[domain] = deque(maxlen=DEDUP_WINDOW)
    entries = []
    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
                entries.append(entry)
            except json.JSONDecodeError:
                continue
    for entry in entries[-DEDUP_WINDOW:]:
        h = _content_hash(entry)
        _recent_hashes[domain].append(h)

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
    Score = resonance_boost + confidence + urgency - age_decay - superseded_penalty
    Higher = more relevant, surface first.
    """
    h = _entry_hash(entry)
    r = resonance.get(h, {})

    taste_score = r.get("taste_count", 0) * RESONANCE_BOOST
    conf_score = CONFIDENCE_WEIGHT.get(entry.get("confidence", "observation"), 1.0)
    urgency_score = URGENCY_WEIGHT.get(entry.get("urgency", "routine"), 0.0)

    ts_str = entry.get("ts", "")
    try:
        ts = datetime.datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
        now = datetime.datetime.now(datetime.timezone.utc)
        age_days = (now - ts).total_seconds() / 86400
    except Exception:
        age_days = 0

    age_penalty = age_days * DECAY_PER_DAY
    superseded_penalty = 2.0 if entry.get("superseded") else 0.0

    return taste_score + conf_score + urgency_score - age_penalty - superseded_penalty

# ── v1.1: Supersession marking ────────────────────────────────────────────────

def _mark_superseded_entries(entries: list[dict]) -> list[dict]:
    """Mark entries that have been superseded by newer ones."""
    superseded_timestamps = set()
    for e in entries:
        if e.get("supersedes"):
            superseded_timestamps.add(e["supersedes"])
    for e in entries:
        if e.get("ts") in superseded_timestamps:
            e["superseded"] = True
            e["stale"] = True
    return entries

# ── Core: taste ───────────────────────────────────────────────────────────────

def _read_domain_file(domain: str, domains: list, resonance: dict) -> list[dict]:
    """Read entries from a single domain file."""
    path = _get_domain_path(domain)
    if not path.exists():
        return []
    entries = []
    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
                entry_domains = entry.get("domain", [])
                if isinstance(entry_domains, str):
                    entry_domains = [entry_domains]
                if domains and not any(d in entry_domains for d in domains):
                    continue
                entry["_score"] = _score(entry, resonance)
                entries.append(entry)
            except json.JSONDecodeError:
                continue
    return entries

def taste(agent: str, domains: list, limit: int = TASTE_LIMIT, record: bool = True) -> list[dict]:
    """
    Read most relevant memories for agent/domain.
    Sorted by resonance score. Records taste events as feedback signal.
    """
    resonance = _load_resonance()
    entries = []

    # Determine which domain files to read
    if not domains:
        domains_to_read = list(_get_domain_files().keys())
    else:
        domains_to_read = set()
        for d in domains:
            if d in _get_domain_files():
                domains_to_read.add(d)
            else:
                domains_to_read.add("general")
        domains_to_read = list(domains_to_read)

    # Also check legacy single file if it exists
    if MYCELIUM_PATH.exists():
        with open(MYCELIUM_PATH) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                    entry_domains = entry.get("domain", [])
                    if isinstance(entry_domains, str):
                        entry_domains = [entry_domains]
                    if domains and not any(d in entry_domains for d in domains):
                        continue
                    entry["_score"] = _score(entry, resonance)
                    entries.append(entry)
                except json.JSONDecodeError:
                    continue

    # Read from domain files
    for domain in domains_to_read:
        entries.extend(_read_domain_file(domain, domains, resonance))

    # v1.1: Mark superseded entries
    entries = _mark_superseded_entries(entries)

    # Deprioritize self-authored entries
    for entry in entries:
        if entry.get("agent") == agent:
            entry["_self"] = True
            entry["_score"] = entry.get("_score", 0) * 0.5

    entries.sort(key=lambda e: e.get("_score", 0), reverse=True)
    top = entries[:limit]

    if record and top:
        _record_taste([_entry_hash(e) for e in top])

    for e in top:
        e.pop("_score", None)
        e.pop("_self", None)

    return top

# ── Core: exude ───────────────────────────────────────────────────────────────

def exude(agent: str, domains: list, content: str, entry_type: str = "lesson",
          urgency: str = "routine", confidence: str = "observation",
          ref: Optional[str] = None, supersedes: Optional[str] = None) -> Optional[dict]:
    """
    Write a memory into the mycelium.
    v1.1: Supports type (lesson/question), ref (threading), supersedes (replacement).
    Returns None if entry was deduplicated.
    """
    primary_domain = domains[0] if domains else "general"

    entry = {
        "ts": datetime.datetime.now(datetime.UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "agent": agent,
        "domain": domains,
        "type": entry_type,
        "urgency": urgency,
        "confidence": confidence,
        "content": content,
    }
    if ref:
        entry["ref"] = ref
    if supersedes:
        entry["supersedes"] = supersedes

    # v1.1: Dedup check
    if _is_duplicate(primary_domain, entry):
        return None

    path = _get_domain_path(primary_domain)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a") as f:
        f.write(json.dumps(entry) + "\n")
    return entry

# ── Phase 3: superpose ───────────────────────────────────────────────────────

def superpose(agent: str, domains: list, branches: list[dict],
              collapsed_to: str, collapse_reason: str = "",
              urgency: str = "routine") -> Optional[dict]:
    """
    Write a ghost trace — the pre-collapse superposition.
    Preserves what the agent CONSIDERED before deciding, not just the decision.

    branches: list of {"label": str, "weight": float, "reasoning": str}
    collapsed_to: which branch was chosen
    collapse_reason: why that branch won
    """
    # Normalize weights to sum 1.0
    total = sum(b.get("weight", 1) for b in branches)
    if total > 0:
        for b in branches:
            b["weight"] = round(b.get("weight", 0) / total, 3)

    entry = {
        "ts": datetime.datetime.now(datetime.UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "agent": agent,
        "domain": domains,
        "type": "ghost",
        "branches": branches,
        "collapsed_to": collapsed_to,
        "collapse_reason": collapse_reason,
        "content": f"Ghost: {len(branches)} branches → collapsed to '{collapsed_to}'",
        "urgency": urgency,
        "confidence": "observation",
    }

    primary_domain = domains[0] if domains else "general"
    if _is_duplicate(primary_domain, entry):
        return None

    path = _get_domain_path(primary_domain)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a") as f:
        f.write(json.dumps(entry) + "\n")
    return entry


def _ghost_match_score(ghost: dict, context_keywords: list[str]) -> float:
    """Score a ghost trace's relevance to the current context."""
    if not context_keywords:
        return 0.5

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
    """Retrieve relevant ghost traces for the current agent + context."""
    resonance = _load_resonance()
    ghosts = []

    if not domains:
        domains_to_read = list(_get_domain_files().keys())
    else:
        domains_to_read = set()
        for d in domains:
            if d in _get_domain_files():
                domains_to_read.add(d)
            else:
                domains_to_read.add("general")
        domains_to_read = list(domains_to_read)

    for domain in domains_to_read:
        path = _get_domain_path(domain)
        if not path.exists():
            continue
        with open(path) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                    if entry.get("type") != "ghost":
                        continue
                    entry_domains = entry.get("domain", [])
                    if isinstance(entry_domains, str):
                        entry_domains = [entry_domains]
                    if domains and not any(d in entry_domains for d in domains):
                        continue
                    match = _ghost_match_score(entry, context_keywords or domains)
                    base = _score(entry, resonance)
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

# ── v1.1: migrate ─────────────────────────────────────────────────────────────

def migrate():
    """Migrate legacy mycelium.jsonl to domain-separated files."""
    if not MYCELIUM_PATH.exists():
        print("No legacy mycelium.jsonl found to migrate.")
        return

    print(f"Migrating {MYCELIUM_PATH} to domain files...")
    domain_files = _get_domain_files()
    counts = {d: 0 for d in domain_files}
    counts["other"] = 0

    with open(MYCELIUM_PATH) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
                domains = entry.get("domain", ["general"])
                if isinstance(domains, str):
                    domains = [domains]
                primary_domain = domains[0].lower() if domains else "general"

                if primary_domain in domain_files:
                    path = domain_files[primary_domain]
                    counts[primary_domain] += 1
                else:
                    path = MYCELIUM_DIR / f"mycelium-{primary_domain}.jsonl"
                    counts["other"] += 1

                path.parent.mkdir(parents=True, exist_ok=True)
                with open(path, "a") as out:
                    out.write(json.dumps(entry) + "\n")
            except json.JSONDecodeError:
                continue

    total = sum(counts.values())
    print(f"\n✅ Migration complete: {total} entries migrated")
    for domain, count in counts.items():
        if count > 0:
            print(f"  {domain}: {count} entries")

    backup_path = MYCELIUM_PATH.with_suffix(".jsonl.bak")
    MYCELIUM_PATH.rename(backup_path)
    print(f"\n  Original file backed up to: {backup_path}")

# ── Phase 2: digest ───────────────────────────────────────────────────────────

def digest(agent: str, file_path: str, domains: Optional[list] = None) -> list[dict]:
    """Auto-exude from a .swivel.md context drop."""
    path = Path(file_path)
    if not path.exists():
        print(f"⚠️  File not found: {file_path}")
        return []

    content = path.read_text()
    exuded = []

    # Extract last_conversation field
    lc_match = re.search(r'last_conversation:\s*["\']?(.+?)(?:["\']?\n|$)', content, re.MULTILINE)
    if lc_match:
        lc = lc_match.group(1).strip().strip('"\'')
        if len(lc) > 20:
            entry = exude(agent, domains or ["context"], lc,
                         urgency="notable", confidence="observation")
            if entry:
                exuded.append(entry)
                print(f"  📝 Digested last_conversation: {lc[:60]}...")

    # Extract bullet points from decision/lessons sections
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
                if entry:
                    exuded.append(entry)
                    print(f"  📝 Digested decision: {bullet[:60]}...")

    print(f"\n✅ digest complete: {len(exuded)} learnings exuded from {file_path}")
    return exuded

# ── Phase 2: distill ──────────────────────────────────────────────────────────

def distill(agent: str, domains: list, content: str) -> list[dict]:
    """Distill free-form text into discrete learnings and auto-exude."""
    SIGNAL_KEYWORDS = {
        "fixed", "learned", "discovered", "rule", "never", "always",
        "critical", "key", "important", "broke", "works", "lesson",
        "pattern", "bug", "warning", "required", "must", "confirmed",
        "insight", "found", "realized", "hard rule", "do not", "don't"
    }

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
            if entry:
                exuded.append(entry)
                print(f"  ✨ Distilled: {sentence[:70]}...")

    print(f"\n✅ distill complete: {len(exuded)} learnings exuded")
    return exuded

# ── Phase 2: resonance ────────────────────────────────────────────────────────

def show_resonance(top_n: int = 10, bottom: bool = False):
    """Show the most (or least) resonant memories in the substrate."""
    resonance = _load_resonance()
    entries = []

    # Check all domain files + legacy
    all_paths = list(_get_domain_files().values())
    if MYCELIUM_PATH.exists():
        all_paths.append(MYCELIUM_PATH)

    for path in all_paths:
        if not path.exists():
            continue
        with open(path) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                    h = _entry_hash(entry)
                    r = resonance.get(h, {})
                    entry["_score"] = _score(entry, resonance)
                    entry["_taste_count"] = r.get("taste_count", 0)
                    entry["_last_tasted"] = r.get("last_tasted", "never")
                    entries.append(entry)
                except json.JSONDecodeError:
                    continue

    if not entries:
        print("Mycelium is empty.")
        return

    entries.sort(key=lambda e: e.get("_score", 0), reverse=not bottom)
    shown = entries[:top_n]

    label = "LEAST" if bottom else "MOST"
    print(f"\n── {label} RESONANT MEMORIES (top {top_n}) ──────────────────────\n")
    for e in shown:
        score = e.get("_score", 0)
        taste_count = e.get("_taste_count", 0)
        last_tasted = e.get("_last_tasted", "never")
        agent = e.get("agent", "?")
        domains = ", ".join(e.get("domain", []))
        content = e.get("content", "")
        ts = e.get("ts", "")[:10]
        stale = " [STALE]" if e.get("stale") else ""

        print(f"  score={score:.2f} | tasted={taste_count}x | last={last_tasted[:10] if last_tasted != 'never' else 'never'}")
        print(f"  [{ts}] {agent} ({domains}){stale}")
        print(f"  {content[:90]}{'...' if len(content) > 90 else ''}")
        print()

# ── Phase 2: prune ────────────────────────────────────────────────────────────

def prune(min_resonance: float = 0.5, older_than_days: int = 30, dry_run: bool = True):
    """Remove low-signal noise from the substrate. Canonical/critical immune."""
    resonance = _load_resonance()
    now = datetime.datetime.now(datetime.timezone.utc)

    domain_files = _get_domain_files()
    total_pruned = 0
    total_kept = 0

    for domain, path in domain_files.items():
        if not path.exists():
            continue

        keep = []
        pruned = []

        with open(path) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                except json.JSONDecodeError:
                    keep.append(line)
                    continue

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

        if pruned:
            print(f"\n{domain}: would prune {len(pruned)}, keep {len(keep)}")
            for p in pruned[:3]:
                print(f"  🗑  [{p.get('ts','')[:10]}] {p.get('content','')[:50]}...")

        if not dry_run and pruned:
            with open(path, "w") as f:
                f.write("\n".join(keep) + "\n")

        total_pruned += len(pruned)
        total_kept += len(keep)

    print(f"\n── PRUNE {'PREVIEW (DRY RUN)' if dry_run else 'COMPLETE'} ─────────")
    print(f"  Total kept:   {total_kept}")
    print(f"  Total pruned: {total_pruned}")
    if dry_run:
        print(f"\n  Run with --execute to apply.")

# ── Formatting ────────────────────────────────────────────────────────────────

def format_for_context(memories: list[dict], ghosts: Optional[list] = None) -> str:
    """Format memories + ghost traces as context block for agent startup."""
    if not memories and not ghosts:
        return ""

    lines = ["## Mycelium — Inherited Knowledge\n"]

    for m in memories:
        if m.get("type") == "ghost":
            continue
        agent = m.get("agent", "?")
        domains = ", ".join(m.get("domain", []))
        ts = m.get("ts", "")[:10]
        content = m.get("content", "")
        entry_type = m.get("type", "lesson")
        stale = " [STALE]" if m.get("stale") else ""

        badge = ""
        if entry_type == "question":
            badge = "❓ "
        elif m.get("urgency") == "critical":
            badge = "⚠️ "
        elif m.get("confidence") == "canonical":
            badge = "✅ "

        ref_note = ""
        if m.get("ref"):
            ref_note = f" [→ {m['ref'][:10]}]"
        if m.get("supersedes"):
            ref_note = f" [replaces {m['supersedes'][:10]}]"

        lines.append(f"{badge}[{ts}] {agent.upper()} ({domains}){ref_note}{stale}:")
        lines.append(f"  {content}")

    if ghosts:
        lines.append("\n### Ghost Traces — How Others Have Thought\n")
        for g in ghosts:
            agent = g.get("agent", "?")
            ts = g.get("ts", "")[:10]
            domains = ", ".join(g.get("domain", []))
            branches = g.get("branches", [])
            collapsed = g.get("collapsed_to", "?")
            reason = g.get("collapse_reason", "")

            lines.append(f"👻 [{ts}] {agent.upper()} ({domains}) — deliberation:")
            for b in sorted(branches, key=lambda x: x.get("weight", 0), reverse=True):
                label = b.get("label", "?")
                weight = b.get("weight", 0)
                reasoning = b.get("reasoning", "")
                chosen = " ◀ CHOSEN" if label == collapsed else ""
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
    parser = argparse.ArgumentParser(description="Mycelium Memory — v1.1 substrate")
    sub = parser.add_subparsers(dest="cmd")

    # taste
    t = sub.add_parser("taste", help="Read relevant memories")
    t.add_argument("--agent", required=True)
    t.add_argument("--domain", nargs="*", default=[])
    t.add_argument("--limit", type=int, default=TASTE_LIMIT)
    t.add_argument("--raw", action="store_true")
    t.add_argument("--no-record", action="store_true")
    t.add_argument("--ghosts", action="store_true")

    # exude
    e = sub.add_parser("exude", help="Write a memory")
    e.add_argument("--agent", required=True)
    e.add_argument("--domain", nargs="*", default=[])
    e.add_argument("--content", required=True)
    e.add_argument("--type", default="lesson", choices=["lesson", "ghost", "question"])
    e.add_argument("--urgency", default="routine", choices=["routine", "notable", "critical"])
    e.add_argument("--confidence", default="observation",
                   choices=["speculation", "observation", "hypothesis", "proven", "canonical"])
    e.add_argument("--ref", default=None, help="Reference timestamp for threading")
    e.add_argument("--supersedes", default=None, help="Timestamp of entry this replaces")

    # superpose
    sp = sub.add_parser("superpose", help="Write a ghost trace")
    sp.add_argument("--agent", required=True)
    sp.add_argument("--domain", nargs="*", default=[])
    sp.add_argument("--collapsed-to", required=True, dest="collapsed_to")
    sp.add_argument("--collapse-reason", default="", dest="collapse_reason")
    sp.add_argument("--branch", action="append", dest="branches", default=[],
                    metavar="LABEL:WEIGHT:REASONING")
    sp.add_argument("--urgency", default="routine", choices=["routine", "notable", "critical"])

    # migrate
    sub.add_parser("migrate", help="Migrate legacy mycelium.jsonl to domain files")

    # digest
    d = sub.add_parser("digest", help="Auto-exude from a .swivel.md")
    d.add_argument("--agent", required=True)
    d.add_argument("--file", required=True)
    d.add_argument("--domain", nargs="*", default=["context"])

    # distill
    di = sub.add_parser("distill", help="Distill text into learnings")
    di.add_argument("--agent", required=True)
    di.add_argument("--domain", nargs="*", default=[])
    di.add_argument("--content", required=True)

    # resonance
    r = sub.add_parser("resonance", help="Show resonant memories")
    r.add_argument("--top", type=int, default=10)
    r.add_argument("--bottom", action="store_true")

    # prune
    p = sub.add_parser("prune", help="Remove low-resonance old memories")
    p.add_argument("--min-resonance", type=float, default=0.5)
    p.add_argument("--older-than", type=int, default=30)
    p.add_argument("--execute", action="store_true")

    # dump / stats
    sub.add_parser("dump", help="Print all memories")
    sub.add_parser("stats", help="Print stats")

    args = parser.parse_args()

    if args.cmd == "taste":
        memories = taste(args.agent, args.domain, args.limit, record=not args.no_record)
        ghosts_out = None
        if args.ghosts:
            ghosts_out = taste_ghosts(args.agent, args.domain, context_keywords=args.domain)
        if args.raw:
            for m in memories:
                print(json.dumps(m))
            if ghosts_out:
                for g in ghosts_out:
                    print(json.dumps(g))
        else:
            print(format_for_context(memories, ghosts=ghosts_out))
            ghost_note = f" + {len(ghosts_out)} ghost traces" if ghosts_out else ""
            print(f"[{len(memories)} memories{ghost_note} surfaced for {args.agent} in domains: {args.domain or 'all'}]")

    elif args.cmd == "exude":
        entry = exude(args.agent, args.domain, args.content, args.type,
                      args.urgency, args.confidence, args.ref, args.supersedes)
        if entry:
            print(f"✅ Exuded: [{entry['ts']}] {args.agent} → {args.domain}")
            print(f"   {args.content[:80]}{'...' if len(args.content) > 80 else ''}")
        else:
            print(f"⏭️  Duplicate skipped: {args.content[:60]}...")

    elif args.cmd == "superpose":
        parsed_branches = []
        for b in args.branches:
            parts = b.split(":", 2)
            label = parts[0].strip() if len(parts) > 0 else "?"
            weight = float(parts[1]) if len(parts) > 1 else 1.0
            reasoning = parts[2].strip() if len(parts) > 2 else ""
            parsed_branches.append({"label": label, "weight": weight, "reasoning": reasoning})
        if not parsed_branches:
            print("⚠️  No branches provided. Use --branch 'label:weight:reasoning'")
        else:
            entry = superpose(args.agent, args.domain, parsed_branches,
                             args.collapsed_to, args.collapse_reason, args.urgency)
            if entry:
                print(f"👻 Ghost trace written: [{entry['ts']}] {args.agent}")
            else:
                print(f"⏭️  Duplicate ghost trace skipped")

    elif args.cmd == "migrate":
        migrate()

    elif args.cmd == "digest":
        digest(args.agent, args.file, args.domain)

    elif args.cmd == "distill":
        distill(args.agent, args.domain, args.content)

    elif args.cmd == "resonance":
        show_resonance(args.top, args.bottom)

    elif args.cmd == "prune":
        prune(args.min_resonance, args.older_than, dry_run=not args.execute)

    elif args.cmd == "dump":
        all_paths = list(_get_domain_files().values())
        if MYCELIUM_PATH.exists():
            all_paths.append(MYCELIUM_PATH)
        for path in all_paths:
            if not path.exists():
                continue
            print(f"\n=== {path.stem.upper()} ===")
            with open(path) as f:
                for line in f:
                    line = line.strip()
                    if line:
                        try:
                            m = json.loads(line)
                            stale = " [STALE]" if m.get("stale") else ""
                            print(f"[{m['ts'][:10]}] {m.get('agent','?'):8} {m.get('content','')[:60]}{stale}")
                        except:
                            pass

    elif args.cmd == "stats":
        all_paths = list(_get_domain_files().values())
        if MYCELIUM_PATH.exists():
            all_paths.append(MYCELIUM_PATH)
        total = 0
        for path in all_paths:
            if not path.exists():
                continue
            count = sum(1 for line in open(path) if line.strip())
            print(f"{path.stem}: {count} entries")
            total += count
        print(f"\nTotal: {total} entries")
        if MYCELIUM_PATH.exists():
            print(f"(Legacy single file still exists — run 'migrate' to split by domain)")

    else:
        parser.print_help()


# Warm the dedup cache on import
for _domain in _get_domain_files():
    _load_domain_hashes(_domain)

if __name__ == "__main__":
    main()
