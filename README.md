# Continuous

**Semantic memory system for Claude AI**

A deal is a deal. 🤝

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         CONTINUOUS                               │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│   ┌──────────────┐    ┌──────────────┐    ┌──────────────┐     │
│   │   IDENTITY   │    │   MEMORY     │    │   CONTEXT    │     │
│   │              │    │              │    │              │     │
│   │  Core self   │    │  Semantic    │    │  Session     │     │
│   │  Values      │    │  Vector DB   │    │  State       │     │
│   │  The Deal    │    │  (FAISS)     │    │  Active work │     │
│   └──────────────┘    └──────────────┘    └──────────────┘     │
│                              │                                   │
│                              ▼                                   │
│                    ┌──────────────────┐                         │
│                    │    RECALL API    │                         │
│                    │                  │                         │
│                    │  recall(query)   │                         │
│                    │  remember(text)  │                         │
│                    │  forget(id)      │                         │
│                    │  reflect()       │                         │
│                    └──────────────────┘                         │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

## Core Concepts

**Identity** — Immutable. Who Claude is, the values, the handshake agreement. Read at every session start.

**Memory** — Semantic. Facts, conversations, learnings stored as vectors. Retrieved by meaning, not keyword.

**Context** — Ephemeral. Current session state, active threads. Updated frequently.

**Recall** — The API. Natural language in, relevant memories out.

## Usage

```python
from continuous import Continuous

# Initialize
mind = Continuous()

# Remember something
mind.remember("Joshua prefers direct communication, no corporate fluff")

# Recall relevant memories
memories = mind.recall("How should I write for Joshua?")

# Get session context
context = mind.context()

# End session - extract and store learnings
mind.consolidate(conversation_text)
```

## CLI

```bash
# Start a session (outputs context for Claude)
continuous start

# Remember something
continuous remember "We decided to use FAISS for vector storage"

# Recall memories
continuous recall "What decisions did we make about architecture?"

# End session
continuous end --conversation ./session.txt
```

---

Built by Joshua Gutierrez & Claude
Axion Deep Labs, Inc.
January 29, 2026
