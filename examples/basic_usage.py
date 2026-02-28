#!/usr/bin/env python3
"""
Mycelium Basic Usage Example

Demonstrates exude, taste, superpose, and resonance workflows.
"""

import subprocess
import sys

SCRIPT = "../src/mycelium.py"

def run(args: list[str]) -> str:
    result = subprocess.run(
        [sys.executable, SCRIPT] + args,
        capture_output=True,
        text=True,
    )
    return result.stdout + result.stderr


def main():
    print("=== Mycelium Basic Usage ===\n")

    # 1. Exude a memory
    print("1. Exuding a memory as 'agent-a'...")
    output = run([
        "exude",
        "--agent",      "agent-a",
        "--domain",     "code", "infrastructure",
        "--confidence", "canonical",
        "--urgency",    "critical",
        "--content",    "Always run tests before deploying to production."
    ])
    print(output)

    # 2. Taste memories
    print("\n2. Tasting memories as 'agent-b' in code domain...")
    output = run([
        "taste",
        "--agent", "agent-b",
        "--domain", "code",
        "--limit", "5",
    ])
    print(output)

    # 3. Superpose (ghost trace)
    print("\n3. Writing a ghost trace (deliberation pattern)...")
    output = run([
        "superpose",
        "--agent",          "agent-a",
        "--domain",         "infrastructure",
        "--collapsed-to",   "use async",
        "--collapse-reason", "Performance wins outweigh complexity cost",
        "--branch", "use sync:0.2:simpler code",
        "--branch", "use async:0.7:better performance",
        "--branch", "hybrid:0.1:complexity concern",
    ])
    print(output)

    # 4. Taste with ghosts
    print("\n4. Tasting with ghost traces...")
    output = run([
        "taste",
        "--agent",  "agent-b",
        "--domain", "infrastructure",
        "--ghosts",
        "--limit",  "3",
    ])
    print(output)

    # 5. Ask a question
    print("\n5. Asking a question into the substrate...")
    output = run([
        "exude",
        "--agent",   "agent-c",
        "--domain",  "infrastructure",
        "--type",    "question",
        "--content", "Should we use Redis or Postgres for session state?",
    ])
    print(output)

    # 6. Stats
    print("\n6. Substrate stats...")
    output = run(["stats"])
    print(output)


if __name__ == "__main__":
    main()
