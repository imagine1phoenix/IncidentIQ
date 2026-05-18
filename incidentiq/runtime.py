"""
runtime.py — cascadeflow runtime intelligence configuration.

Sets up the CascadeAgent with a cheap Groq drafter (8B) and a strong
verifier (70B). The agent tries the drafter first; if quality is
insufficient, it automatically escalates to the verifier.

All calls run inside budget-enforced sessions with full audit traces.
"""

import cascadeflow
from cascadeflow import CascadeAgent, ModelConfig

_initialized = False


def setup_runtime():
    """Initialize cascadeflow in enforce mode (idempotent)."""
    global _initialized
    if not _initialized:
        cascadeflow.init(mode="enforce")
        _initialized = True


def get_routing_agent() -> CascadeAgent:
    """
    CascadeAgent with two Groq models:
      • Drafter:  llama-3.1-8b-instant   (fast, cheap — handles ~70% of queries)
      • Verifier: llama-3.3-70b-versatile (strong — handles complex P1 incidents)
    """
    return CascadeAgent(
        models=[
            ModelConfig(
                name="llama-3.1-8b-instant",
                provider="groq",
                cost=0.00005,   # $0.05 / 1M tokens
            ),
            ModelConfig(
                name="llama-3.3-70b-versatile",
                provider="groq",
                cost=0.00059,   # $0.59 / 1M tokens — 11.8x more expensive
            ),
        ],
        quality={
            "confidence_thresholds": {"default": 0.7},
        },
    )
