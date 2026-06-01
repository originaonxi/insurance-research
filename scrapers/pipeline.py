"""
Full pipeline runner.
Step 1: Find PDF links for all insurers  (pdf_finder.py)
Step 2: Parse PDFs with Claude            (claude_parser.py)
Step 3: Push to Airtable                 (this file)

Usage:
  python3 scrapers/pipeline.py --step 1          # find PDFs only
  python3 scrapers/pipeline.py --step 2          # parse PDFs (needs step 1 output)
  python3 scrapers/pipeline.py --step 3          # push to Airtable (needs step 2 output)
  python3 scrapers/pipeline.py --all             # run all steps
  python3 scrapers/pipeline.py --step 2 --limit 5  # parse first 5 only (test)
"""
import argparse, json, os, sys
import requests
from datetime import datetime, timezone
from dotenv import load_dotenv

load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), '..', '.env'))

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from scrapers.pdf_finder import run as run_pdf_finder
from parsers.claude_parser import run_batch


def push_to_airtable(parsed_path: str = None):
    base_id = os.environ.get('AIRTABLE_BASE_ID')
    if not base_id:
        print("✗ AIRTABLE_BASE_ID not set in .env. Run: python3 data/airtable_setup.py")
        return

    if not parsed_path:
        parsed_path = os.path.join(os.path.dirname(__file__), '..', 'data', 'parsed_policies.json')

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

        tc_json = {k: v for k, v in p.items() if k not in ['pdf_url', 'buy_url', 'plain_summary', 'insurer_id', 'insurer_name', 'parsed']}

        fields = {
            "Product Name": p.get('product_name', 'Unknown'),
            "Insurer": p.get('insurer_name', ''),
            "Category": p.get('category', 'health'),
            "PDF URL": p.get('pdf_url', ''),
            "Buy Now URL": p.get('buy_url', '') or '',
            "Plain Summary": p.get('plain_summary', ''),
            "What Is Covered": '\n'.join(p.get('what_is_covered', [])) if isinstance(p.get('what_is_covered'), list) else str(p.get('what_is_covered', '')),
            "What Is NOT Covered": '\n'.join(p.get('what_is_not_covered', p.get('exclusions', []))) if isinstance(p.get('what_is_not_covered', p.get('exclusions')), list) else '',
            "Claim Process": str(p.get('claim_process', '')),
            "Full TC JSON": json.dumps(tc_json, ensure_ascii=False)[:100000],
            "Status": "parsed",
            "Last Updated": datetime.now(timezone.utc).isoformat()
        }
        records.append({"fields": fields})

    for i in range(0, len(records), 10):
        batch = records[i:i+10]
        resp = requests.post(url, headers=headers, json={"records": batch})
        if resp.status_code in (200, 201):
            pushed += len(batch)
            print(f"  ✓ Pushed {pushed}/{len(records)} policies")
        else:
            print(f"  ✗ Batch error: {resp.status_code} {resp.text[:200]}")

    print(f"\n✓ {pushed} policies pushed to Airtable base {base_id}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--step', type=int, choices=[1, 2, 3])
    parser.add_argument('--all', action='store_true')
    parser.add_argument('--limit', type=int, help='Limit number of PDFs to parse (for testing)')
    args = parser.parse_args()

    if args.all or args.step == 1:
        print("=" * 50)
        print("STEP 1: Finding policy PDFs for all insurers")
        print("=" * 50)
        run_pdf_finder()

    if args.all or args.step == 2:
        print("\n" + "=" * 50)
        print("STEP 2: Parsing PDFs with Claude AI")
        print("=" * 50)
        run_batch(limit=args.limit)

    if args.all or args.step == 3:
        print("\n" + "=" * 50)
        print("STEP 3: Pushing to Airtable")
        print("=" * 50)
        push_to_airtable()


if __name__ == '__main__':
    main()
