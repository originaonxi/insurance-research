#!/usr/bin/env /opt/homebrew/opt/python@3.11/bin/python3.11
"""
Full pipeline: find PDFs -> parse with regex -> push to Airtable.
Usage:
  python3 scrapers/pipeline.py --step 1           # find PDFs (Playwright)
  python3 scrapers/pipeline.py --step 2           # parse PDFs (OG regex parser)
  python3 scrapers/pipeline.py --step 3           # push to Airtable
  python3 scrapers/pipeline.py --all              # run everything
  python3 scrapers/pipeline.py --step 2 --limit 5 # parse first 5 only
"""
import argparse, json, os, sys, requests
from datetime import datetime, timezone

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from dotenv import load_dotenv
load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), '..', '.env'))

DATA_DIR = os.path.join(os.path.dirname(__file__), '..', 'data')


def step1_find_pdfs(limit=None):
    from scrapers.playwright_finder import run
    run(limit=limit)


def step2_parse_pdfs(limit=None):
    from parsers.policy_parser import parse_policy
    found_path = os.path.join(DATA_DIR, 'policies_found.json')
    if not os.path.exists(found_path):
        print("No policies_found.json — run step 1 first.")
        return

    with open(found_path) as f:
        insurers = json.load(f)

    results = []
    count = 0
    for insurer in insurers:
        cat = insurer.get('category', 'health')
        if cat == 'general':
            cat = 'health'
        for pdf_info in insurer.get('pdfs', []):
            if limit and count >= limit:
                break
            r = parse_policy(pdf_info['pdf_url'], category=cat)
            r['insurer_id'] = insurer['id']
            r['insurer_name'] = insurer['name']
            results.append(r)
            count += 1

    out = os.path.join(DATA_DIR, 'parsed_policies.json')
    with open(out, 'w') as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    print(f"\nParsed {count} policies -> data/parsed_policies.json")


def step3_push_airtable():
    base_id = os.environ.get('AIRTABLE_BASE_ID')
    if not base_id:
        print("Set AIRTABLE_BASE_ID in .env first (run data/airtable_setup.py)")
        return

    parsed_path = os.path.join(DATA_DIR, 'parsed_policies.json')
    with open(parsed_path) as f:
        policies = json.load(f)

    key = os.environ['AIRTABLE_API_KEY']
    headers = {'Authorization': f'Bearer {key}', 'Content-Type': 'application/json'}
    url = f"https://api.airtable.com/v0/{base_id}/Policies"
    pushed = 0

    records = []
    for p in policies:
        if p.get('error'):
            continue
        excl = p.get('exclusions', [])
        covered = p.get('what_is_covered', [])
        fields = {
            "Product Name": p.get('product_name', 'Unknown')[:255],
            "Insurer": p.get('insurer_name', '')[:255],
            "Category": p.get('category', 'health'),
            "PDF URL": p.get('pdf_url', ''),
            "What Is Covered": '\n'.join(covered) if isinstance(covered, list) else str(covered),
            "What Is NOT Covered": '\n'.join(excl) if isinstance(excl, list) else str(excl),
            "Full TC JSON": json.dumps({k: v for k, v in p.items() if k not in ['pdf_url', 'insurer_id', 'insurer_name']}, ensure_ascii=False)[:100000],
            "Status": "parsed",
            "Last Updated": datetime.now(timezone.utc).isoformat()
        }
        records.append({"fields": fields})

    for i in range(0, len(records), 10):
        batch = records[i:i + 10]
        resp = requests.post(url, headers=headers, json={"records": batch})
        if resp.status_code in (200, 201):
            pushed += len(batch)
            print(f"  Pushed {pushed}/{len(records)}")
        else:
            print(f"  Error: {resp.status_code} {resp.text[:200]}")

    print(f"Done. {pushed} policies in Airtable.")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--step', type=int, choices=[1, 2, 3])
    parser.add_argument('--all', action='store_true')
    parser.add_argument('--limit', type=int)
    args = parser.parse_args()

    if args.all or args.step == 1:
        print("=== STEP 1: Finding PDFs ===")
        step1_find_pdfs(args.limit)
    if args.all or args.step == 2:
        print("\n=== STEP 2: Parsing PDFs (OG regex, no API) ===")
        step2_parse_pdfs(args.limit)
    if args.all or args.step == 3:
        print("\n=== STEP 3: Pushing to Airtable ===")
        step3_push_airtable()


if __name__ == '__main__':
    main()
