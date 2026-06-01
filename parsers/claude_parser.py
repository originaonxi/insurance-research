"""
Claude reads a policy PDF and extracts structured T&C in plain language.
Output: JSON with 10 fields every 18-year-old must know before buying.
"""
import anthropic, json, os, re, tempfile
import pdfplumber
import requests
from dotenv import load_dotenv

load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), '..', '.env'))

client = anthropic.Anthropic(api_key=os.environ['ANTHROPIC_API_KEY'])

EXTRACTION_PROMPT = {
    "health": """You are reading an Indian health insurance policy document. Extract ONLY facts stated in this document.
Return a JSON object with these exact keys. Use plain language a confused 18-year-old can understand.
If something is not mentioned in the document, use null.

{
  "product_name": "exact product name from document",
  "insurer_name": "insurance company name",
  "category": "health",
  "sum_insured_options": ["list of sum insured options in INR, e.g. 3L, 5L, 10L"],
  "what_is_covered": ["bullet list of what IS covered — hospitalization, day care, etc."],
  "what_is_not_covered": ["bullet list of KEY exclusions — what will NOT be paid. Be specific."],
  "waiting_periods": {
    "initial": "days before any claim (initial waiting period)",
    "pre_existing": "years before pre-existing diseases are covered",
    "specific_diseases": "list of specific diseases with their waiting periods"
  },
  "room_rent_limit": "any cap on hospital room rent per day, or 'No limit'",
  "pre_existing_disease_coverage": "exact terms — when covered, what conditions",
  "no_claim_bonus": "how NCB works — % increase per claim-free year",
  "claim_process": "step by step: what to do when hospitalized, documents needed, timeline",
  "cashless_vs_reimbursement": "which hospitals cashless, how reimbursement works",
  "renewal_terms": "is lifelong renewability guaranteed? premium hike conditions?",
  "free_look_period": "days to cancel and get full refund",
  "buy_url": null,
  "plain_summary": "3-sentence summary in plain English for an 18-year-old. Start with: This policy covers..."
}

Return ONLY the JSON. No explanation. No markdown. Just the JSON object.""",

    "life": """You are reading an Indian life insurance (term/endowment/ULIP) policy document. Extract ONLY facts stated in this document.
Return a JSON object. Use plain language a confused 18-year-old can understand.

{
  "product_name": "exact product name",
  "insurer_name": "insurance company name",
  "category": "life",
  "policy_type": "term / endowment / ULIP / whole life",
  "sum_assured_options": ["list of sum assured options"],
  "death_benefit": "what exactly is paid on death — lump sum, monthly, both?",
  "exclusions": ["when claim will be REJECTED — suicide clause, aviation, criminal activity, etc."],
  "policy_term_options": ["available policy terms in years"],
  "premium_payment_term": "how many years you pay premium vs policy term",
  "grace_period": "days after premium due date before policy lapses",
  "revival_conditions": "how to revive a lapsed policy",
  "riders_available": ["list of optional add-ons: accidental death, critical illness, etc."],
  "nominee_claim_process": "exactly what documents nominee needs to file a claim",
  "surrender_value": "when you can surrender and what you get back",
  "free_look_period": "days to cancel and get refund",
  "buy_url": null,
  "plain_summary": "3-sentence summary for an 18-year-old. Start with: This policy pays..."
}

Return ONLY the JSON. No markdown.""",

    "auto": """You are reading an Indian motor/auto insurance policy document. Extract ONLY facts stated in this document.
Return a JSON object. Plain language for an 18-year-old.

{
  "product_name": "exact product name",
  "insurer_name": "insurance company name",
  "category": "auto",
  "coverage_type": "comprehensive / third-party only / own damage",
  "what_is_covered": ["own damage from accident, theft, fire, flood, etc."],
  "what_is_not_covered": ["drunk driving, no license, mechanical breakdown, depreciation (if no zero dep), etc."],
  "third_party_liability": "what third party damage/injury is covered and limits",
  "zero_depreciation": "is zero dep available? what does it cover exactly?",
  "cashless_garage_network": "how many garages, how cashless works",
  "ncb_terms": "No Claim Bonus — % per year, max %, lost on claim",
  "idv_calculation": "how Insured Declared Value is set — important for theft/total loss",
  "claim_process": "step by step what to do after an accident",
  "add_ons_available": ["engine protect, roadside assistance, key replacement, etc."],
  "exclusions": ["key exclusions — when claim is rejected"],
  "free_look_period": "if applicable",
  "buy_url": null,
  "plain_summary": "3-sentence summary for an 18-year-old. Start with: This policy covers..."
}

Return ONLY the JSON. No markdown.""",

    "accident": """You are reading an Indian personal accident insurance policy document. Extract ONLY facts stated in this document.
Return a JSON object. Plain language.

{
  "product_name": "exact product name",
  "insurer_name": "insurance company name",
  "category": "accident",
  "what_is_covered": ["accidental death, permanent disability, temporary disability, hospitalization"],
  "payout_structure": "how much paid for death vs different disability types — exact %",
  "what_is_not_covered": ["self-inflicted, under influence, pre-existing, war, etc."],
  "cover_amount_options": ["available coverage amounts"],
  "daily_hospital_cash": "if covered — amount per day of hospitalization",
  "education_benefit": "if covered — child education support on death",
  "claim_process": "what documents needed, timeline",
  "exclusions": ["key exclusion list"],
  "buy_url": null,
  "plain_summary": "3-sentence summary for an 18-year-old. Start with: This policy pays..."
}

Return ONLY the JSON. No markdown."""
}


def extract_text_from_pdf(pdf_path: str, max_pages: int = 40) -> str:
    text_parts = []
    with pdfplumber.open(pdf_path) as pdf:
        for i, page in enumerate(pdf.pages[:max_pages]):
            text = page.extract_text()
            if text:
                text_parts.append(text)
    return '\n\n'.join(text_parts)


def download_pdf(url: str) -> str:
    headers = {'User-Agent': 'Mozilla/5.0 Chrome/120.0.0.0'}
    resp = requests.get(url, headers=headers, timeout=30, stream=True)
    resp.raise_for_status()
    with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as f:
        for chunk in resp.iter_content(chunk_size=8192):
            f.write(chunk)
        return f.name


def parse_policy(pdf_url: str, category: str = 'health', local_path: str = None) -> dict:
    print(f"  Parsing: {pdf_url[:80]}...")

    if local_path:
        pdf_path = local_path
        cleanup = False
    else:
        print(f"  Downloading PDF...")
        pdf_path = download_pdf(pdf_url)
        cleanup = True

    try:
        print(f"  Extracting text...")
        text = extract_text_from_pdf(pdf_path)
        if len(text) < 200:
            return {'error': 'PDF too short or text extraction failed', 'pdf_url': pdf_url}

        prompt = EXTRACTION_PROMPT.get(category, EXTRACTION_PROMPT['health'])
        print(f"  Sending to Claude ({len(text):,} chars)...")

        response = client.messages.create(
            model='claude-sonnet-4-6',
            max_tokens=4096,
            system="You are an insurance policy analyst. Extract structured data from policy documents accurately.",
            messages=[{
                'role': 'user',
                'content': f"{prompt}\n\n--- POLICY DOCUMENT ---\n{text[:80000]}"
            }]
        )

        raw = response.content[0].text.strip()
        raw = re.sub(r'^```json\s*', '', raw)
        raw = re.sub(r'\s*```$', '', raw)

        result = json.loads(raw)
        result['pdf_url'] = pdf_url
        result['parsed'] = True
        print(f"  ✓ Parsed: {result.get('product_name', 'unknown')}")
        return result

    except json.JSONDecodeError as e:
        return {'error': f'JSON parse failed: {e}', 'pdf_url': pdf_url, 'raw': raw[:500]}
    except Exception as e:
        return {'error': str(e), 'pdf_url': pdf_url}
    finally:
        if cleanup and os.path.exists(pdf_path):
            os.unlink(pdf_path)


def run_batch(policies_found_path: str = None, limit: int = None):
    if not policies_found_path:
        policies_found_path = os.path.join(os.path.dirname(__file__), '..', 'data', 'policies_found.json')

    with open(policies_found_path) as f:
        insurers = json.load(f)

    results = []
    count = 0

    for insurer in insurers:
        category = insurer['category']
        if category == 'general':
            category = 'health'  # general insurers sell health + auto, default to health

        for pdf_info in insurer.get('pdfs', []):
            if limit and count >= limit:
                break
            result = parse_policy(pdf_info['pdf_url'], category)
            result['insurer_id'] = insurer['id']
            result['insurer_name'] = insurer['name']
            results.append(result)
            count += 1

    out_path = os.path.join(os.path.dirname(__file__), '..', 'data', 'parsed_policies.json')
    with open(out_path, 'w') as f:
        json.dump(results, f, indent=2)

    print(f"\n✓ Parsed {count} policies. Saved to data/parsed_policies.json")
    return results


if __name__ == '__main__':
    import sys
    limit = int(sys.argv[1]) if len(sys.argv) > 1 else None
    run_batch(limit=limit)
