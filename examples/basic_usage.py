"""
Mycelium — Basic Usage Examples

A 5-minute tour of the substrate.
"""

import subprocess, json

MYCELIUM = "python3 ../src/mycelium.py"

# ── 1. Write your first memory ────────────────────────────────────────────────
print("1. Exuding a memory...")
subprocess.run([
    "python3", "../src/mycelium.py", "exude",
    "--agent",      "forge",
    "--domain",     "code",
    "--confidence", "canonical",
    "--content",    "Never force push or rewrite git history. Ever."
])

# ── 2. Read memories relevant to your domain ─────────────────────────────────
print("\n2. Tasting memories as 'alpha' agent in trading domain...")
subprocess.run([
    "python3", "../src/mycelium.py", "taste",
    "--agent", "alpha",
    "--domain", "trading"
])

# ── 3. Write a ghost trace — the pre-collapse deliberation ───────────────────
print("\n3. Writing a ghost trace...")
subprocess.run([
    "python3", "../src/mycelium.py", "superpose",
    "--agent",          "swiv",
    "--domain",         "trading",
    "--collapsed-to",   "validate before live",
    "--branch",         "go live immediately:0.1:EV math looks solid",
    "--branch",         "shadow mode first:0.75:hard rule, always",
    "--branch",         "abort and recheck:0.15:data gap concern",
    "--collapse-reason","shadow before live — non-negotiable"
])

# ── 4. Taste WITH ghost traces ────────────────────────────────────────────────
print("\n4. Tasting with ghost traces (full superposition context)...")
subprocess.run([
    "python3", "../src/mycelium.py", "taste",
    "--agent",  "alpha",
    "--domain", "trading",
    "--ghosts"
])

# ── 5. See what the substrate thinks matters most ────────────────────────────
print("\n5. Resonance report...")
subprocess.run([
    "python3", "../src/mycelium.py", "resonance",
    "--top", "5"
])

# ── 6. Distill learnings from free-form text ─────────────────────────────────
print("\n6. Distilling session notes into memories...")
subprocess.run([
    "python3", "../src/mycelium.py", "distill",
    "--agent",   "omega",
    "--domain",  "infrastructure",
    "--content", """
        Fixed critical bug — the config was applying while a subagent was active.
        Key lesson: always check sessions_list before any config.patch.
        Never assume subagents are done just because they're quiet.
        The confirmed rule is: one config change per batch, subagents idle first.
    """
])
