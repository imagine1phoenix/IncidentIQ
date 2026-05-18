"""
POST /api/analyze — Analyze an incident using Hindsight memory + cascadeflow routing.

Request body:
  { "service_name": "user-db", "error_message": "...", "severity": "P1" }

Response:
  { "response": "...", "model_used": "...", "total_cost": 0.0, ... , "memories": [...] }
"""

import json
import os
import time
import asyncio
import threading
from concurrent.futures import Future
from http.server import BaseHTTPRequestHandler

import requests as http_requests

# ── Hindsight config ─────────────────────────────────────────────────────────
HINDSIGHT_API_URL = os.environ.get("HINDSIGHT_API_URL", "https://api.hindsight.vectorize.io")
HINDSIGHT_API_KEY = os.environ.get("HINDSIGHT_API_KEY", "")
BANK_ID = os.environ.get("HINDSIGHT_BANK_ID", "incident-iq-memory")


def _hs_headers():
    return {"Authorization": f"Bearer {HINDSIGHT_API_KEY}", "Content-Type": "application/json"}


def recall(service_name, error_message):
    """Semantic recall from Hindsight."""
    query = f"Incident on {service_name}: {error_message}. What was the root cause and fix?"
    try:
        r = http_requests.post(
            f"{HINDSIGHT_API_URL}/v1/default/banks/{BANK_ID}/memories/recall",
            headers=_hs_headers(),
            json={"query": query, "max_tokens": 2000, "budget": "high"},
            timeout=25,
        )
        if r.status_code == 200:
            return [m.get("text", "") for m in r.json().get("results", []) if m.get("text")]
        return []
    except Exception:
        return []


# ── cascadeflow agent ────────────────────────────────────────────────────────
import cascadeflow
from cascadeflow import CascadeAgent, ModelConfig

cascadeflow.init(mode="enforce")


def _get_agent():
    return CascadeAgent(
        models=[
            ModelConfig(name="llama-3.1-8b-instant", provider="groq", cost=0.00005),
            ModelConfig(name="llama-3.3-70b-versatile", provider="groq", cost=0.00059),
        ],
        quality={"confidence_thresholds": {"default": 0.7}},
    )


def _run_async(coro):
    fut = Future()

    def _target():
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            fut.set_result(loop.run_until_complete(coro))
        except Exception as e:
            fut.set_exception(e)
        finally:
            loop.close()

    t = threading.Thread(target=_target)
    t.start()
    t.join(timeout=55)
    return fut.result(timeout=5)


async def _agent_run(prompt, severity):
    agent = _get_agent()
    budget = {"P1": 0.50, "P2": 0.25, "P3": 0.10}.get(severity, 0.25)
    t0 = time.time()

    try:
        with cascadeflow.run(budget=budget, max_tool_calls=5, max_latency_ms=30000) as session:
            result = await agent.run(prompt)
            return {
                "response": result.content,
                "model_used": result.model_used or "—",
                "total_cost": getattr(result, "total_cost", 0.0),
                "cost_saved_percentage": getattr(result, "cost_saved_percentage", 0.0),
                "latency_ms": (time.time() - t0) * 1000,
                "severity_budget": budget,
                "summary": session.summary(),
                "trace": session.trace(),
            }
    except Exception as e:
        return {
            "response": f"⚠️ Agent error: {e}",
            "model_used": "—",
            "total_cost": 0.0,
            "cost_saved_percentage": 0.0,
            "latency_ms": (time.time() - t0) * 1000,
            "severity_budget": budget,
            "summary": {},
            "trace": [],
            "error": str(e),
        }


# ── Handler ──────────────────────────────────────────────────────────────────
class handler(BaseHTTPRequestHandler):
    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        body = json.loads(self.rfile.read(length)) if length else {}

        service = body.get("service_name", "")
        error = body.get("error_message", "")
        severity = body.get("severity", "P2")

        if not service or not error:
            self.send_response(400)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"error": "service_name and error_message required"}).encode())
            return

        # 1. Recall from Hindsight
        memories = recall(service, error)

        # 2. Build prompt
        if memories:
            block = "═══ PAST INCIDENTS FROM HINDSIGHT MEMORY ═══\n"
            for i, m in enumerate(memories[:5], 1):
                block += f"\n▸ Memory #{i}:\n{m}\n"
            block += "\n═══ END ═══"
        else:
            block = "═══ NO PAST INCIDENTS FOUND ═══\nProvide general DevOps best-practice advice.\n═══ END ═══"

        prompt = f"""You are IncidentIQ — an AI-powered DevOps Incident Response Agent.

━━━ ALERT ━━━
SERVICE: {service}
ERROR: {error}
SEVERITY: {severity}

{block}

Respond with:
### 🔍 Assessment
What is likely happening.

### 🔧 Suggested Fix
If past incident matched: "**Based on past incident** on [date]: [fix from memory]".
Otherwise: "**General suggestion:** [best practice]".

### ⚡ Immediate Next Steps
3-5 actionable items for the on-call engineer.

Be concise and specific."""

        # 3. Run agent
        try:
            data = _run_async(_agent_run(prompt, severity))
        except Exception as e:
            data = {"response": f"Agent error: {e}", "error": str(e)}

        data["memories"] = memories[:5]
        data["memory_count"] = len(memories)

        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(json.dumps(data, default=str).encode())

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()
