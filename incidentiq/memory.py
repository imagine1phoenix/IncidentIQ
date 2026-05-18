"""
memory.py — Hindsight integration layer for IncidentIQ.

Provides two operations:
  • recall_similar_incidents() — semantic search for past incidents
  • log_incident_resolution() — store a newly resolved incident so the agent learns

All calls go through the Hindsight Cloud REST API.
API docs: /v1/default/banks/{bank_id}/memories (retain) and /memories/recall
"""

import os
import time
import requests
from dotenv import load_dotenv

load_dotenv()

HINDSIGHT_API_URL = os.environ.get("HINDSIGHT_API_URL", "https://api.hindsight.vectorize.io")
HINDSIGHT_API_KEY = os.environ.get("HINDSIGHT_API_KEY", "")
BANK_ID = os.environ.get("HINDSIGHT_BANK_ID", "incident-iq-memory")


def _headers():
    return {
        "Authorization": f"Bearer {HINDSIGHT_API_KEY}",
        "Content-Type": "application/json",
    }


# ─── RECALL ──────────────────────────────────────────────────────────────────

def recall_similar_incidents(service_name: str, error_message: str) -> list[dict]:
    """
    Search Hindsight for similar past incidents via semantic recall.
    Returns a list of dicts: [{"text": "...", "type": "..."}]
    """
    query = f"Incident on {service_name}: {error_message}. What was the root cause and fix?"
    t0 = time.time()

    try:
        res = requests.post(
            f"{HINDSIGHT_API_URL}/v1/default/banks/{BANK_ID}/memories/recall",
            headers=_headers(),
            json={
                "query": query,
                "max_tokens": 2000,
                "budget": "high",
            },
            timeout=30,
        )
        latency_ms = (time.time() - t0) * 1000

        if res.status_code == 200:
            data = res.json()
            results = data.get("results", [])
            # Return structured results
            return [
                {
                    "text": r.get("text", ""),
                    "type": r.get("type", "unknown"),
                    "latency_ms": latency_ms,
                }
                for r in results
                if r.get("text")
            ]
        else:
            print(f"[memory] Recall error {res.status_code}: {res.text[:300]}")
            return []
    except Exception as e:
        print(f"[memory] Recall exception: {e}")
        return []


# ─── RETAIN (Resolution Logging) ─────────────────────────────────────────────

def log_incident_resolution(
    service_name: str,
    error_message: str,
    severity: str,
    root_cause: str,
    fix_applied: str,
    resolved_by: str,
    resolution_time_minutes: int = 0,
) -> bool:
    """
    Log a resolved incident back to Hindsight memory.
    This is how the agent learns and gets smarter over time.
    """
    from datetime import datetime, timezone

    now = datetime.now(timezone.utc).isoformat()

    content = (
        f"Incident ({now}): {error_message} on service {service_name} "
        f"(Severity: {severity}). "
        f"Root Cause: {root_cause}. "
        f"Fix Applied: {fix_applied}. "
        f"Resolved by: {resolved_by}"
        + (f" in {resolution_time_minutes} minutes." if resolution_time_minutes else ".")
    )

    try:
        res = requests.post(
            f"{HINDSIGHT_API_URL}/v1/default/banks/{BANK_ID}/memories",
            headers=_headers(),
            json={
                "items": [
                    {
                        "content": content,
                        "context": "resolved production incident",
                        "timestamp": now,
                        "metadata": {
                            "service": service_name,
                            "severity": severity,
                            "resolved_by": resolved_by,
                            "source": "incidentiq_ui",
                        },
                    }
                ],
                "async": False,
            },
            timeout=30,
        )
        if res.status_code == 200:
            print(f"[memory] ✓ Logged resolution for {service_name}: {error_message[:60]}")
            return True
        else:
            print(f"[memory] Retain error {res.status_code}: {res.text[:300]}")
            return False
    except Exception as e:
        print(f"[memory] Retain exception: {e}")
        return False


# ─── STATS ───────────────────────────────────────────────────────────────────

def get_bank_stats() -> dict:
    """Get memory bank stats (total memories, entities, etc.)."""
    try:
        res = requests.get(
            f"{HINDSIGHT_API_URL}/v1/default/banks/{BANK_ID}/stats",
            headers=_headers(),
            timeout=10,
        )
        if res.status_code == 200:
            return res.json()
        return {}
    except Exception:
        return {}
