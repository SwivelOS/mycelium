# Mycelium Skill

Use this skill when an agent needs to read from or write to the fleet's shared memory substrate.

## Commands

```bash
# Taste memories (session start — always do this)
python3 ~/.openclaw/workspace/skills/mycelium/src/mycelium.py taste \
  --agent <your_agent_id> \
  --domain <your_domain> \
  --ghosts

# Exude a learning
python3 ~/.openclaw/workspace/skills/mycelium/src/mycelium.py exude \
  --agent <your_agent_id> \
  --domain <domain> \
  --confidence canonical \
  --content "<what you learned>"

# Write a ghost trace (before big decisions)
python3 ~/.openclaw/workspace/skills/mycelium/src/mycelium.py superpose \
  --agent <your_agent_id> \
  --domain <domain> \
  --collapsed-to "<chosen path>" \
  --branch "<option_a>:<weight>:<reasoning>" \
  --branch "<option_b>:<weight>:<reasoning>" \
  --collapse-reason "<why you chose it>"
```

## Protocol

1. **Session start:** `taste --ghosts` in your domain
2. **During session:** `exude` key learnings as they happen
3. **Context drop:** `digest --file .swivel.md` to auto-exude
4. **Big decisions:** `superpose` before committing

## Environment

Set `MYCELIUM_DIR` to point to your substrate location:
```bash
export MYCELIUM_DIR=~/.openclaw/fleet
```
