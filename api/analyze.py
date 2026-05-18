"""
POST /api/analyze — Analyze an incident using Hindsight memory + Groq LLM.
Serverless-safe: no threads, no async, no cascadeflow (pure HTTP calls).
"""

import json
import os
import time
from http.server import BaseHTTPRequestHandler
import requests as http_requests

# ── Config ────────────────────────────────────────────────────────────────────
HINDSIGHT_API_URL = os.environ.get("HINDSIGHT_API_URL", "https://api.hindsight.vectorize.io")
HINDSIGHT_API_KEY = os.environ.get("HINDSIGHT_API_KEY", "")
BANK_ID = os.environ.get("HINDSIGHT_BANK_ID", "incident-iq-memory")
GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")

# cascadeflow-style model routing config
MODELS = {
    "drafter": {"name": "llama-3.1-8b-instant", "cost_per_1k": 0.00005},
    "verifier": {"name": "llama-3.3-70b-versatile", "cost_per_1k": 0.00059},
}
BUDGETS = {"P1": 0.50, "P2": 0.25, "P3": 0.10}


def _hs_headers():
    return {"Authorization": f"Bearer {HINDSIGHT_API_KEY}", "Content-Type": "application/json"}


def recall(service_name, error_message):
    """Semantic recall from Hindsight memory."""
    try:
        r = http_requests.post(
            f"{HINDSIGHT_API_URL}/v1/default/banks/{BANK_ID}/memories/recall",
            headers=_hs_headers(),
            json={
                "query": f"Incident on {service_name}: {error_message}. Root cause and fix?",
                "max_tokens": 2000,
                "budget": "high",
            },
            timeout=20,
        )
        if r.status_code == 200:
            return [m.get("text", "") for m in r.json().get("results", []) if m.get("text")]
    except Exception:
        pass
    return []


def call_groq(prompt, model_name, max_tokens=1024):
    """Direct Groq API call — no SDK needed, pure HTTP."""
    try:
        r = http_requests.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {GROQ_API_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "model": model_name,
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": max_tokens,
                "temperature": 0.3,
            },
            timeout=30,
        )
        if r.status_code == 200:
            data = r.json()
            usage = data.get("usage", {})
            content = data["choices"][0]["message"]["content"]
            return content, usage
    except Exception:
        pass
    return None, {}


def cascade_route(prompt, severity):
    """
    cascadeflow-style routing: try drafter first, escalate to verifier for P1.
    Returns (response, model_used, cost, latency_ms).
    """
    t0 = time.time()

    # For P1 critical: go straight to the verifier
    if severity == "P1":
        model = MODELS["verifier"]
        content, usage = call_groq(prompt, model["name"], max_tokens=1200)
        latency = (time.time() - t0) * 1000
        tokens = usage.get("total_tokens", 0)
        cost = tokens * model["cost_per_1k"] / 1000
        return content, model["name"], cost, latency, "verifier"

    # For P2/P3: use cheap drafter
    model = MODELS["drafter"]
    content, usage = call_groq(prompt, model["name"], max_tokens=1024)
    latency = (time.time() - t0) * 1000
    tokens = usage.get("total_tokens", 0)
    cost = tokens * model["cost_per_1k"] / 1000
    return content, model["name"], cost, latency, "drafter"


# ── Vercel Handler ────────────────────────────────────────────────────────────
class handler(BaseHTTPRequestHandler):
    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        body = json.loads(self.rfile.read(length)) if length else {}

        service = body.get("service_name", "")
        error = body.get("error_message", "")
        severity = body.get("severity", "P2")

        if not service or not error:
            self._json(400, {"error": "service_name and error_message required"})
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

        # 3. Route through cascade
        content, model_used, cost, latency, route_type = cascade_route(prompt, severity)

        if content is None:
            content = "⚠️ LLM call failed. Check GROQ_API_KEY."

        budget = BUDGETS.get(severity, 0.25)
        verifier_cost = MODELS["verifier"]["cost_per_1k"]
        drafter_cost = MODELS["drafter"]["cost_per_1k"]
        savings = ((verifier_cost - drafter_cost) / verifier_cost * 100) if route_type == "drafter" else 0

        self._json(200, {
            "response": content,
            "model_used": model_used,
            "total_cost": cost,
            "cost_saved_percentage": round(savings, 1),
            "latency_ms": round(latency, 1),
            "severity_budget": budget,
            "route_type": route_type,
            "memories": memories[:5],
            "memory_count": len(memories),
            "summary": {"route": route_type, "model": model_used, "budget": budget},
            "trace": [{"step": 1, "action": route_type, "reason": f"Severity {severity} → {route_type}"}],
        })

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def _json(self, code, data):
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(json.dumps(data, default=str).encode())
