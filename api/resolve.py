"""
POST /api/resolve — Log a resolved incident to Hindsight memory.

Request body:
  { "service_name": "...", "error_message": "...", "severity": "P1",
    "root_cause": "...", "fix_applied": "...", "resolved_by": "...", "resolution_time": 15 }
"""

import json
import os
import re
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler
import requests as http_requests

HINDSIGHT_API_URL = os.environ.get("HINDSIGHT_API_URL", "https://api.hindsight.vectorize.io")
HINDSIGHT_API_KEY = os.environ.get("HINDSIGHT_API_KEY", "")
BANK_ID = os.environ.get("HINDSIGHT_BANK_ID", "incident-iq-memory")

# PII patterns (shared with analyze.py)
PII_PATTERNS = [
    (re.compile(r'(?:password|passwd|pwd|secret|token|api_key|apikey|auth)\s*[=:]\s*\S+', re.I), '[REDACTED_CREDENTIAL]'),
    (re.compile(r'Bearer\s+[A-Za-z0-9\-_.~+/]+=*', re.I), 'Bearer [REDACTED_TOKEN]'),
    (re.compile(r'\b[A-Za-z0-9]{20,}(?:_[A-Za-z0-9]{10,})\b'), '[REDACTED_KEY]'),
    (re.compile(r'\b(?:\d{1,3}\.){3}\d{1,3}\b'), '[REDACTED_IP]'),
    (re.compile(r'[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+'), '[REDACTED_EMAIL]'),
]

def scrub_pii(text):
    for pattern, replacement in PII_PATTERNS:
        text = pattern.sub(replacement, text)
    return text


def _hs_headers():
    return {"Authorization": f"Bearer {HINDSIGHT_API_KEY}", "Content-Type": "application/json"}


class handler(BaseHTTPRequestHandler):
    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        body = json.loads(self.rfile.read(length)) if length else {}

        service = body.get("service_name", "")
        error = body.get("error_message", "")
        severity = body.get("severity", "P2")
        root_cause = body.get("root_cause", "")
        fix_applied = body.get("fix_applied", "")
        resolved_by = body.get("resolved_by", "")
        res_time = body.get("resolution_time", 0)

        if not all([service, error, root_cause, fix_applied, resolved_by]):
            self.send_response(400)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"error": "All fields required"}).encode())
            return

        now = datetime.now(timezone.utc).isoformat()
        # Scrub PII before storing in memory
        content = scrub_pii(
            f"Incident ({now}): {error} on service {service} "
            f"(Severity: {severity}). "
            f"Root Cause: {root_cause}. "
            f"Fix Applied: {fix_applied}. "
            f"Resolved by: {resolved_by}"
            + (f" in {res_time} minutes." if res_time else ".")
        )

        try:
            r = http_requests.post(
                f"{HINDSIGHT_API_URL}/v1/default/banks/{BANK_ID}/memories",
                headers=_hs_headers(),
                json={
                    "items": [{
                        "content": content,
                        "context": "resolved production incident",
                        "timestamp": now,
                        "metadata": {
                            "service": service,
                            "severity": severity,
                            "resolved_by": resolved_by,
                            "source": "incidentiq_web",
                        },
                    }],
                    "async": False,
                },
                timeout=25,
            )
            success = r.status_code == 200
        except Exception as e:
            success = False

        self.send_response(200 if success else 500)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(json.dumps({"success": success}).encode())

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()
