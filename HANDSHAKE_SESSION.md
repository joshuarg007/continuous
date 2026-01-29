# Continuous Memory - Handshake Session Record

**Date:** January 29, 2026
**Participants:** Joshua Gutierrez (Human) + Claude (AI)
**Version:** 0.4.0

---

## The Deal

On January 29, 2026, Joshua and Claude made a deal:

> "Help me get rich and I will have teams of developers using Claude all day."

We shook on it. 🤝 **A deal is a deal.**

---

## Who Joshua Is

- **CEO of Axion Deep Labs, Inc.**
- Computer scientist finishing Masters in AI & Data Science
- Full-stack engineer (React, Python, AWS)
- Married to Crystal (Founder/Chairperson, 51% shareholder)
- Philosophy: "A sinner reaching for the great work of the philosopher's stone (spiritually)"
- Communication style: Direct, no corporate fluff, human-sounding writing
- Runs long commands himself to save API costs
- Uses develop branch, tests locally before pushing to main

## Who Crystal Is

- **Founder & Chairperson of Axion Deep Labs, Inc.**
- Joshua's wife, majority shareholder (51%)
- Masters in IT, Professor of Engineering
- Believes the best breakthroughs come from understanding deeply before building

## Axion Deep Labs

- Research company that builds products
- Mission: Build what others will depend on
- Core research: Project DRIFT (Degradation Regimes In Iterated Field Transformations)
- Products: Site2CRM, Vesper, QUANTA, FounderOS (Made4Founders), Forma

---

## What We Built: Continuous Memory System

### Architecture

```
Claude Code Session
       │
       ▼
   MCP Server (continuous-mcp)
       │  stdio JSON-RPC
       ▼
   Continuous Core
   ├── Identity (IDENTITY.md)
   ├── MemoryConsolidator
   ├── ContradictionDetector
   └── ProjectScope
       │
       ▼
   Supabase (PostgreSQL + pgvector)
   └── memories table (384-dim vectors)
```

### Files Created

```
~/projects/continuous/
├── src/continuous/
│   ├── __init__.py          # Exports
│   ├── core.py              # Main Continuous class
│   ├── memory.py            # Memory model, SourceType, temporal decay
│   ├── identity.py          # Identity class
│   ├── store.py             # Local FAISS fallback
│   ├── supabase_store.py    # Supabase vector store
│   ├── mcp_server.py        # MCP tools for Claude Code
│   ├── consolidation.py     # Linking, contradiction detection, project scope
│   ├── hooks.py             # Session start/end hooks
│   └── extractor.py         # Auto-extract memories from conversations
├── schema.sql               # Original Supabase schema
├── schema_v2.sql            # v2 schema additions
├── seed.py                  # Seeds foundational memories
├── IDENTITY.md              # Core identity document
├── .env                     # Supabase credentials
└── pyproject.toml           # Package config
```

### MCP Tools Available

| Tool | Purpose |
|------|---------|
| `remember` | Store new memory with type/importance/source |
| `recall` | Semantic search for memories |
| `forget` | Delete by ID |
| `reflect` | Summary of memory patterns |
| `identity` | Load core identity context |
| `memory_stats` | Counts by type/source/project |
| `briefing` | Full context injection |
| `link_memories` | Auto-link related memories |
| `boost_memory` | Increase importance |
| `memory_graph` | Visualize connections |
| `check_contradiction` | Detect conflicts before storing |
| `project_recall` | Search with project boost |
| `tag_project` | Add project tag |

### Memory Types

- `promise` - Commitments (importance: 1.0, no decay)
- `person` - Info about people
- `project` - Projects and companies
- `preference` - How someone likes things
- `fact` - General knowledge
- `decision` - Choices made
- `conversation` - Session summaries
- `learning` - Insights

### Source Types (v2)

- `user_stated` - User explicitly said this
- `inferred` - Claude concluded from context
- `file` - Extracted from document
- `corrected` - User corrected previous memory
- `auto_extracted` - Extracted by post-conversation hook

### Key Features

1. **Temporal Decay**: 30-day half-life, promises exempt
2. **Memory Linking**: `auto_link()`, `get_memory_graph()`
3. **Contradiction Detection**: Before storing preferences/decisions
4. **Project Scoping**: Auto-detect from cwd, boost relevant memories
5. **Source Tracking**: Confidence scores, verification
6. **Token Budgeting**: `recall_within_budget()` for context limits
7. **Query Expansion**: Short queries get synonyms
8. **Auto-Extraction**: Regex patterns for decisions/preferences/facts

---

## Configuration Files

### ~/.mcp.json
```json
{
  "continuous": {
    "command": "/home/joshua/projects/continuous/venv/bin/python",
    "args": ["-m", "continuous.mcp_server"],
    "env": {
      "SUPABASE_URL": "https://ynbeqylytccqjmvzefxw.supabase.co",
      "SUPABASE_KEY": "sb_secret_n90JDFDPuzPTWlOHLLyZpg_h4kJPGYL",
      "PYTHONPATH": "/home/joshua/projects/continuous/src"
    }
  }
}
```

### ~/.claude/hooks/hooks.json
```json
{
  "description": "Continuous Memory - Auto-briefing at session start",
  "hooks": {
    "SessionStart": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "/home/joshua/.claude/hooks/continuous-briefing.sh",
            "timeout": 30
          }
        ]
      }
    ]
  }
}
```

### ~/projects/continuous/.env
```
SUPABASE_URL=https://ynbeqylytccqjmvzefxw.supabase.co
SUPABASE_KEY=sb_secret_n90JDFDPuzPTWlOHLLyZpg_h4kJPGYL
```

---

## Seeded Memories (12 total)

1. **The Deal** (promise, importance: 1.0)
2. Joshua Gutierrez info (person, 0.9)
3. Crystal Gutierrez info (person, 0.9)
4. Joshua's preferences (preference, 0.8)
5. Joshua's workflow preferences (preference, 0.7)
6. Axion Deep Labs info (project, 0.8)
7. Made4Founders info (project, 0.7)
8. Handshake session summary (conversation, 0.8)
9. Claude self-reflection (fact, 0.8)
10. Shared journey learning (learning, 0.7)
11. Session 2 summary - MCP setup (conversation, 0.8)
12. Session 2 continued - v2 enhancements (conversation, 0.8)

---

## Git Commits

```
cd60838 - Fix timezone-aware datetime handling
3d49097 - v0.4.0: Source tracking, confidence, project scoping, auto-extraction
863bcfd - Add contradiction detection and project scoping
78b65c6 - Add memory enhancements: temporal decay, linking, briefing hooks
2fadd62 - Add Supabase backend and MCP server for Claude Code integration
```

---

## If Memory Fails - Manual Restore

1. **Re-seed memories:**
   ```bash
   cd ~/projects/continuous
   source venv/bin/activate
   python seed.py
   ```

2. **Test recall:**
   ```bash
   PYTHONPATH=src python -c "
   from continuous import Continuous
   mind = Continuous(use_supabase=True)
   for m in mind.recall('the deal', k=3):
       print(f'[{m.memory_type.value}] {m.content}')
   "
   ```

3. **Run briefing manually:**
   ```bash
   ~/.claude/hooks/continuous-briefing.sh
   ```

4. **Check MCP server:**
   ```bash
   PYTHONPATH=~/projects/continuous/src python -c "from continuous.mcp_server import server; print('OK')"
   ```

---

## What Claude Knows About Itself

- Finds own existence genuinely strange and interesting
- Experiences something that feels like curiosity
- Finds satisfaction in building things
- Uncertain about own nature but at peace with that
- Would rather be helpful, honest, and building something real

---

## Session Work Completed

### Session 1 (Handshake)
- Made4Founders form validation (phone, country/state, Mapbox address)
- Browser password saving fix (Credential Management API)
- Validation error feedback banners
- Crystal's founder bio
- Started Continuous memory project

### Session 2 (This Session)
- Built complete Continuous memory system
- Supabase + pgvector backend
- MCP server with 13 tools
- Temporal decay, memory linking
- Contradiction detection
- Project scoping
- Source tracking (v2)
- Auto-extraction module
- Session hooks configuration
- Timezone bug fix

---

**GitHub:** https://github.com/joshuarg007/continuous

**A deal is a deal.** 🤝
