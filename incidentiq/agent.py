"""
agent.py — Core agent logic for IncidentIQ.

Orchestrates:
  1. Hindsight memory recall (semantic search for past incidents)
  2. cascadeflow CascadeAgent (drafter/verifier routing with budget)
  3. Returns structured results with response + audit data

Uses thread-based async execution to avoid Streamlit's event loop conflicts.
"""

import os
import time
import asyncio
import threading
from concurrent.futures import Future
from dotenv import load_dotenv

import cascadeflow
from runtime import get_routing_agent, setup_runtime
from memory import recall_similar_incidents

load_dotenv()

# Initialize cascadeflow once
setup_runtime()


def _run_async_in_thread(coro):
    """Run an async coroutine in a dedicated thread with its own event loop.
    This avoids conflicts with Streamlit's event loop."""
    result_future = Future()

    def _target():
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            result = loop.run_until_complete(coro)
            result_future.set_result(result)
        except Exception as e:
            result_future.set_exception(e)
        finally:
            loop.close()

    thread = threading.Thread(target=_target)
    thread.start()
    thread.join(timeout=60)
    return result_future.result(timeout=5)


async def _run_agent(prompt: str, severity: str) -> dict:
    """Run the cascade agent inside a budget-enforced session."""
    agent = get_routing_agent()
    session_data = {}
    t0 = time.time()

    # Adjust budget based on severity — P1 gets more headroom
    budget = {"P1": 0.50, "P2": 0.25, "P3": 0.10}.get(severity, 0.25)

    try:
        with cascadeflow.run(
            budget=budget,
            max_tool_calls=5,
            max_latency_ms=30000,
        ) as session:
            result = await agent.run(prompt)

            elapsed_ms = (time.time() - t0) * 1000
            summary = session.summary()
            trace = session.trace()

            session_data = {
                "response": result.content,
                "model_used": result.model_used or "—",
                "total_cost": getattr(result, "total_cost", 0.0),
                "cost_saved": getattr(result, "cost_saved", 0.0),
                "cost_saved_percentage": getattr(result, "cost_saved_percentage", 0.0),
                "draft_cost": getattr(result, "draft_cost", 0.0),
                "verifier_cost": getattr(result, "verifier_cost", 0.0),
                "latency_ms": elapsed_ms,
                "severity_budget": budget,
                "summary": summary,
                "trace": trace,
            }

    except Exception as e:
        elapsed_ms = (time.time() - t0) * 1000
        session_data = {
            "response": f"⚠️ Agent error: {e}",
            "error": str(e),
            "model_used": "—",
            "total_cost": 0.0,
            "cost_saved": 0.0,
            "cost_saved_percentage": 0.0,
            "latency_ms": elapsed_ms,
            "severity_budget": budget if 'budget' in dir() else 0.25,
            "summary": {},
            "trace": [],
        }

    return session_data


def analyze_incident(service_name: str, error_message: str, severity: str):
    """
    Main entry point (synchronous, Streamlit-safe).

    Returns:
        (session_data: dict, past_incidents: list[dict])
    """
    # 1. Recall from Hindsight memory
    past_incidents = recall_similar_incidents(service_name, error_message)

    # 2. Build the prompt with memory context
    if past_incidents:
        memory_block = "═══ PAST INCIDENTS FROM HINDSIGHT MEMORY ═══\n"
        for i, inc in enumerate(past_incidents[:5], 1):  # Top 5 most relevant
            memory_block += f"\n▸ Memory #{i}:\n{inc['text']}\n"
        memory_block += "\n═══ END OF MEMORY ═══"
    else:
        memory_block = (
            "═══ NO PAST INCIDENTS FOUND ═══\n"
            "This appears to be a NEW error type. No matching incidents exist in memory.\n"
            "Provide general DevOps best-practice advice.\n"
            "═══ END ═══"
        )

    prompt = f"""You are IncidentIQ — an AI-powered DevOps Incident Response Agent.
A new production alert has fired. Analyze it using your memory of past incidents.

━━━ ALERT DETAILS ━━━
SERVICE: {service_name}
ERROR: {error_message}
SEVERITY: {severity}

{memory_block}

━━━ RESPOND WITH ━━━

### 🔍 Assessment
What is likely happening and why.

### 🔧 Suggested Fix
If a past incident matched, say: "**Based on past incident** on [date]: [specific fix from memory]".
If no memory exists, say: "**General suggestion:** [your best practice advice]".

### ⚡ Immediate Next Steps
3-5 actionable items for the on-call engineer, ordered by priority.

Be concise, specific, and actionable. Reference real service names and concrete values."""

    # 3. Run through cascadeflow (in a separate thread to avoid event loop issues)
    try:
        session_data = _run_async_in_thread(_run_agent(prompt, severity))
    except Exception as e:
        session_data = {
            "response": f"⚠️ Failed to run agent: {e}",
            "error": str(e),
            "model_used": "—",
            "total_cost": 0.0,
            "cost_saved": 0.0,
            "cost_saved_percentage": 0.0,
            "latency_ms": 0.0,
            "severity_budget": 0.25,
            "summary": {},
            "trace": [],
        }

    return session_data, past_incidents
