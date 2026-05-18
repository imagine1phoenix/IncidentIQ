import json
import os
import requests
from dotenv import load_dotenv

load_dotenv()

HINDSIGHT_API_URL = os.environ.get("HINDSIGHT_API_URL", "https://api.hindsight.vectorize.io")
HINDSIGHT_API_KEY = os.environ.get("HINDSIGHT_API_KEY", "")
BANK_ID = os.environ.get("HINDSIGHT_BANK_ID", "incident-iq-memory")

def seed_incidents():
    with open("data/seed_incidents.json", "r") as f:
        incidents = json.load(f)

    print(f"Loaded {len(incidents)} incidents from seed data.")
    
    headers = {
        "Authorization": f"Bearer {HINDSIGHT_API_KEY}",
        "Content-Type": "application/json"
    }
    
    # Step 1: Create bank (PUT /v1/default/banks/{bank_id})
    print("Creating memory bank...")
    res = requests.put(
        f"{HINDSIGHT_API_URL}/v1/default/banks/{BANK_ID}",
        headers=headers,
        json={
            "name": "IncidentIQ Memory Bank",
            "mission": "You are a DevOps Incident Response AI. You remember past production incidents, their root causes, and the fixes that resolved them.",
            "disposition": {"skepticism": 2, "literalism": 4, "empathy": 2}
        }
    )
    print(f"Bank creation: {res.status_code} — {res.text[:200]}")
    
    # Step 2: Retain incidents (POST /v1/default/banks/{bank_id}/memories)
    print("Seeding incidents into Hindsight memory...")
    items = []
    for inc in incidents:
        content = (
            f"Incident {inc['incident_id']} ({inc['timestamp']}): "
            f"{inc['error_message']} on service {inc['service_name']} "
            f"(Severity: {inc['severity']}). "
            f"Root Cause: {inc['root_cause']}. "
            f"Fix Applied: {inc['fix_applied']}. "
            f"Resolved by: {inc['resolved_by']} in {inc['resolution_time_minutes']} minutes."
        )
        items.append({
            "content": content,
            "context": "past production incident resolution",
            "document_id": inc["incident_id"],
            "timestamp": inc["timestamp"],
            "metadata": {
                "service": inc["service_name"],
                "severity": inc["severity"],
                "resolved_by": inc["resolved_by"]
            }
        })
    
    # Batch in groups of 5 to be safe
    batch_size = 5
    for i in range(0, len(items), batch_size):
        batch = items[i:i+batch_size]
        res = requests.post(
            f"{HINDSIGHT_API_URL}/v1/default/banks/{BANK_ID}/memories",
            headers=headers,
            json={"items": batch, "async": False}
        )
        print(f"  Batch {i//batch_size + 1}: {res.status_code} — {res.text[:150]}")
    
    print(f"\nDone! Seeded {len(items)} incidents into bank '{BANK_ID}'.")

if __name__ == "__main__":
    seed_incidents()
