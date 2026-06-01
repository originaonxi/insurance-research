"""
Creates the Airtable base for the insurance research platform.
Run once to set up: python3 data/airtable_setup.py
"""
import os, json
import requests
from dotenv import load_dotenv

load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), '..', '.env'))

AIRTABLE_KEY = os.environ['AIRTABLE_API_KEY']
HEADERS = {'Authorization': f'Bearer {AIRTABLE_KEY}', 'Content-Type': 'application/json'}

BASE_NAME = "Insurance Research — India"


def create_base(workspace_id: str = None) -> str:
    url = "https://api.airtable.com/v0/meta/bases"
    tables = [
        {
            "name": "Insurers",
            "description": "All IRDAI-registered insurance companies",
            "fields": [
                {"name": "Name", "type": "singleLineText"},
                {"name": "Short Name", "type": "singleLineText"},
                {"name": "Category", "type": "singleSelect", "options": {"choices": [
                    {"name": "life"}, {"name": "health"}, {"name": "general"}, {"name": "accident"}
                ]}},
                {"name": "Website", "type": "url"},
                {"name": "Policy Page", "type": "url"},
                {"name": "IRDAI Reg No", "type": "singleLineText"},
                {"name": "Founded", "type": "number", "options": {"precision": 0}},
                {"name": "Type", "type": "singleSelect", "options": {"choices": [
                    {"name": "public"}, {"name": "private"}
                ]}},
                {"name": "Claim Settlement Ratio", "type": "percent", "options": {"precision": 1}},
                {"name": "Status", "type": "singleSelect", "options": {"choices": [
                    {"name": "pending"}, {"name": "scraped"}, {"name": "live"}
                ]}},
            ]
        },
        {
            "name": "Policies",
            "description": "Every policy with its PDF link and parsed T&C",
            "fields": [
                {"name": "Product Name", "type": "singleLineText"},
                {"name": "Insurer", "type": "singleLineText"},
                {"name": "Category", "type": "singleSelect", "options": {"choices": [
                    {"name": "health"}, {"name": "life"}, {"name": "auto"}, {"name": "accident"}
                ]}},
                {"name": "PDF URL", "type": "url"},
                {"name": "Buy Now URL", "type": "url"},
                {"name": "Plain Summary", "type": "multilineText"},
                {"name": "What Is Covered", "type": "multilineText"},
                {"name": "What Is NOT Covered", "type": "multilineText"},
                {"name": "Waiting Periods", "type": "multilineText"},
                {"name": "Claim Process", "type": "multilineText"},
                {"name": "Full TC JSON", "type": "multilineText"},
                {"name": "Status", "type": "singleSelect", "options": {"choices": [
                    {"name": "pdf_found"}, {"name": "parsed"}, {"name": "reviewed"}, {"name": "live"}
                ]}},
                {"name": "Last Updated", "type": "dateTime", "options": {
                    "dateFormat": {"name": "iso"}, "timeFormat": {"name": "24hour"}, "timeZone": "Asia/Kolkata"
                }},
            ]
        }
    ]
    payload = {"name": BASE_NAME, "tables": tables}
    if workspace_id:
        payload["workspaceId"] = workspace_id

    resp = requests.post(url, headers=HEADERS, json=payload)
    if resp.status_code in (200, 201):
        base_id = resp.json()['id']
        print(f"✓ Base created: {BASE_NAME} (ID: {base_id})")
        env_path = os.path.join(os.path.dirname(__file__), '..', '.env')
        with open(env_path, 'a') as f:
            f.write(f"\nAIRTABLE_BASE_ID={base_id}\n")
        print(f"✓ AIRTABLE_BASE_ID written to .env")
        return base_id
    else:
        print(f"✗ Error: {resp.status_code} {resp.text}")
        return None


def seed_insurers(base_id: str):
    seed_path = os.path.join(os.path.dirname(__file__), 'insurers_india.json')
    with open(seed_path) as f:
        insurers = json.load(f)

    url = f"https://api.airtable.com/v0/{base_id}/Insurers"
    records = [{"fields": {
        "Name": ins["name"],
        "Short Name": ins["short_name"],
        "Category": ins["category"],
        "Website": ins["website"],
        "Policy Page": ins["policy_page"],
        "IRDAI Reg No": ins.get("irdai_reg_no", ""),
        "Founded": ins.get("founded", 0),
        "Type": ins.get("type", "private"),
        "Status": "pending"
    }} for ins in insurers]

    # Airtable batch limit: 10 records
    for i in range(0, len(records), 10):
        batch = records[i:i+10]
        resp = requests.post(url, headers=HEADERS, json={"records": batch})
        if resp.status_code in (200, 201):
            print(f"  ✓ Seeded {len(batch)} insurers (batch {i//10 + 1})")
        else:
            print(f"  ✗ Batch failed: {resp.status_code} {resp.text[:200]}")

    print(f"✓ {len(insurers)} insurers seeded to Airtable")


if __name__ == '__main__':
    import sys
    workspace_id = sys.argv[1] if len(sys.argv) > 1 else None
    print(f"Creating Airtable base: {BASE_NAME}")
    base_id = create_base(workspace_id)
    if base_id:
        print(f"Seeding insurer data...")
        seed_insurers(base_id)
        print(f"\nDone. Open: https://airtable.com/{base_id}")
