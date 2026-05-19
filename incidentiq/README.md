# 🚨 IncidentIQ — AI-Powered Incident Response Agent

> **An AI agent that remembers past production incidents, learns from them, and gets smarter over time.**

When a critical alert fires at 3 AM, your on-call engineer doesn't need generic advice — they need *your team's specific fix* from the last time this happened. IncidentIQ provides exactly that by combining **persistent AI memory** with **intelligent model routing**.

---

## 🎯 The Problem

| Traditional Approach | IncidentIQ |
|---------------------|------------|
| Search Confluence/Slack for 20 min | **Instant recall** of similar past incidents |
| Generic LLM advice ("check your logs") | **Specific fix**: "Last time, @devops increased pool to 20" |
| No learning between incidents | **Learns in real-time** when you resolve an incident |
| Same expensive model for everything | **Cost-optimized routing** — P3 uses cheap model, P1 escalates |

## 🏗️ Architecture

```
┌─────────────┐     ┌────────────────────┐     ┌──────────────┐
│  New Alert   │────▸│  Hindsight Memory  │────▸│  cascadeflow │
│  (Service,   │     │  • Semantic recall  │     │  • Budget    │
│   Error,     │     │  • 20+ past fixes   │     │  • Model     │
│   Severity)  │     │  • Entity graph     │     │    routing   │
└─────────────┘     └────────────────────┘     │  • Audit     │
                                                └──────┬───────┘
                                                       │
                                            ┌──────────▼──────────┐
                                            │  Groq LLM Response  │
                                            │  8B drafter (fast)   │
                                            │  70B verifier (deep) │
                                            └──────────┬──────────┘
                                                       │
                                            ┌──────────▼──────────┐
                                             │  Web Dashboard       │
                                             │  • Assessment        │
                                             │  • Suggested Fix     │
                                             │  • Next Steps        │
                                             │  • Audit Trail       │
                                             └─────────────────────┘
```

## 🛠️ Tech Stack

| Component | Technology | Purpose |
|-----------|-----------|---------|
| **Memory** | [Hindsight](https://hindsight.vectorize.io) | Persistent incident memory — semantic recall, entity graphs, temporal search |
| **Runtime** | [cascadeflow](https://docs.cascadeflow.ai/) | Model routing, budget enforcement, full audit trail per query |
| **LLMs** | [Groq](https://console.groq.com) | `llama-3.1-8b-instant` (drafter) + `llama-3.3-70b-versatile` (verifier) |
| **UI** | HTML/CSS/JS + [Streamlit](https://streamlit.io) | Web dashboard (Vercel) + Streamlit (local dev) |
| **Hosting** | [Vercel](https://vercel.com) | Serverless Python functions + static frontend |
| **Language** | Python 3.9+ | |

## 🧠 How Hindsight Memory Works

IncidentIQ uses Hindsight's three core operations:

### Retain (Learning)
When an incident is resolved in the UI, the error, root cause, fix, and resolver are written to a Hindsight **Memory Bank** (`incident-iq-memory`). Hindsight doesn't store raw text — it **extracts structured facts**, builds an **entity graph**, and creates **temporal connections**.

### Recall (Remembering)
When a new alert fires, IncidentIQ sends a semantic query to Hindsight:
```
"Incident on user-db: DB connection pool exhausted. What was the root cause and fix?"
```
Hindsight returns the most relevant past incidents — ranked by semantic similarity, entity overlap, and temporal relevance.

### Continuous Learning Loop
```
Alert → Recall past fixes → Agent responds → Engineer resolves →
Log fix to memory → Next similar alert instantly recalls this fix
```

## 🚦 How cascadeflow Routing Works

IncidentIQ uses severity-based budget allocation:

| Severity | Budget | Strategy |
|----------|--------|----------|
| **P1 Critical** | $0.50 | Drafter attempts → **escalates to 70B verifier** if quality is low |
| **P2 High** | $0.25 | Standard drafter-first with quality gates |
| **P3 Medium** | $0.10 | Fast 8B drafter only — handles ~70% of queries |

This means **P3 incidents cost ~11x less** than P1 incidents while still getting accurate responses.

The audit trail shows exactly:
- Which model was selected and why
- Token cost breakdown
- Latency metrics
- Budget remaining

## ⚙️ Setup

### 1. Prerequisites
- Python 3.9+
- [Hindsight Cloud](https://ui.hindsight.vectorize.io) account (promo: `MEMHACK515` for $50 free)
- [Groq](https://console.groq.com/keys) API key (free tier)

### 2. Install
```bash
git clone https://github.com/imagine1phoenix/IncidentIQ.git
cd IncidentIQ/incidentiq
pip install -r requirements.txt
```

### 3. Configure
Create `.env`:
```env
HINDSIGHT_API_KEY=your_hindsight_key
HINDSIGHT_API_URL=https://api.hindsight.vectorize.io
HINDSIGHT_BANK_ID=incident-iq-memory
GROQ_API_KEY=your_groq_key
```

### 4. Seed Memory (20 synthetic incidents)
```bash
python seed.py
```

### 5. Deploy to Vercel

🔗 **Live Demo**: [incident-iq-inky.vercel.app](https://incident-iq-inky.vercel.app)

To deploy your own:
1. Import the GitHub repo at [vercel.com/new](https://vercel.com/new)
2. Set these **Environment Variables** in the Vercel dashboard:
   - `HINDSIGHT_API_KEY`
   - `HINDSIGHT_API_URL`
   - `HINDSIGHT_BANK_ID`
   - `GROQ_API_KEY`
3. Deploy — Vercel auto-detects `api/` (Python serverless) and `public/` (static frontend)

### 5b. Run Locally (Streamlit — optional)
```bash
pip install streamlit
streamlit run main.py
```

## 🎥 Demo Script (60 seconds)

### 1️⃣ The "No Memory" Baseline (10s)
Enter a novel error: `Kafka partition rebalance timeout`
→ Agent gives **general advice**. Badge shows **"NEW ERROR TYPE"**.

### 2️⃣ The Memory Recall (15s)
Enter a seeded error: `DB connection pool exhausted` on `user-db`
→ Badge shows **"✓ MEMORY MATCH"**. Agent says: *"Based on past incident on May 3rd: connection leak in reporting service. Fix: Increase pool to 20."*

### 3️⃣ The Learning Loop (20s)
Go back to Kafka error → Resolve it with root cause *"Zookeeper session timeout"* and fix *"Increased session.timeout.ms to 30000"* → Click **Log to Memory**

### 4️⃣ Prove It Learned (10s)
Re-enter `Kafka partition rebalance timeout`
→ Now shows **"✓ MEMORY MATCH"** with the fix you *just* logged. **Real-time learning.**

### 5️⃣ Show the Audit Trail (5s)
Point to right panel: model routing, cost savings, budget enforcement.

## 📁 Project Structure

```
├── api/                     # Vercel serverless functions (repo root)
│   ├── analyze.py           # POST /api/analyze — memory recall + LLM
│   ├── resolve.py           # POST /api/resolve — log fix to Hindsight
│   └── stats.py             # GET /api/stats — memory bank stats
├── public/                  # Static frontend (repo root)
│   ├── index.html           # Premium dark-mode dashboard
│   ├── styles.css           # Design system
│   └── app.js               # Client-side logic
├── requirements.txt         # Python dependencies
└── incidentiq/              # Core logic + Streamlit (local dev)
    ├── main.py              # Streamlit UI
    ├── agent.py             # Core agent logic
    ├── memory.py            # Hindsight client
    ├── runtime.py           # cascadeflow config
    ├── seed.py              # Seeds 20 incidents into Hindsight
    └── data/
        └── seed_incidents.json
```

## 🏆 Hackathon Criteria Addressed

| Criteria | Implementation |
|----------|---------------|
| **Hindsight Integration** | Retain + Recall + continuous learning loop with live memory bank |
| **cascadeflow Integration** | Per-severity budget routing, drafter/verifier cascade, full audit trail |
| **Innovation** | Agent that *learns* from your team's fixes — not generic knowledge |
| **Demo Quality** | Before/after memory recall + real-time learning in 60 seconds |
| **Production Readiness** | Vercel deployment, serverless API, dark-mode UI, session history |
