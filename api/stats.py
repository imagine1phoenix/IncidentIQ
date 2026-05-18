"""
GET /api/stats — Get Hindsight memory bank statistics.
"""

import json
import os
from http.server import BaseHTTPRequestHandler
import requests as http_requests

HINDSIGHT_API_URL = os.environ.get("HINDSIGHT_API_URL", "https://api.hindsight.vectorize.io")
HINDSIGHT_API_KEY = os.environ.get("HINDSIGHT_API_KEY", "")
BANK_ID = os.environ.get("HINDSIGHT_BANK_ID", "incident-iq-memory")


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        try:
            r = http_requests.get(
                f"{HINDSIGHT_API_URL}/v1/default/banks/{BANK_ID}/stats",
                headers={"Authorization": f"Bearer {HINDSIGHT_API_KEY}", "Content-Type": "application/json"},
                timeout=10,
            )
            data = r.json() if r.status_code == 200 else {}
        except Exception:
            data = {}

        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(json.dumps(data).encode())
