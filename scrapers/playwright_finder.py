#!/usr/bin/env /opt/homebrew/opt/python@3.11/bin/python3.11
"""
Playwright-based PDF finder. Handles JS-heavy insurer websites.
Navigates like a real user, finds policy document PDF links.
"""
import json, os, time, sys
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout
from dotenv import load_dotenv

load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), '..', '.env'))

PDF_KEYWORDS = ['policy', 'wording', 'document', 'terms', 'conditions', 'brochure', 'schedule', 'prospectus']
PDF_ANTI = ['claim-form', 'proposal-form', 'kyc', 'neft', 'mandate', 'annual-report']

SEARCH_PATTERNS = [
    'a[href$=".pdf"]',
    'a[href*="policy"]',
    'a[href*="wording"]',
    'a[href*="document"]',
]

PRODUCT_NAV_TEXTS = [
    'health insurance', 'term insurance', 'car insurance', 'motor insurance',
    'two wheeler', 'travel insurance', 'personal accident',
    'policy document', 'policy wording', 'download', 'brochure',
]


def is_relevant_pdf(url, text=''):
    url_lower = url.lower()
    combined = url_lower + ' ' + text.lower()
    if not url_lower.endswith('.pdf'):
        return False
    if not any(kw in combined for kw in PDF_KEYWORDS):
        return False
    if any(kw in url_lower for kw in PDF_ANTI):
        return False
    return True


def scrape_with_playwright(insurer, browser):
    name = insurer['short_name']
    base = insurer['website']
    policy_page = insurer['policy_page']
    print(f"\n[{insurer['category'].upper()}] {name} — {base}")
    found_pdfs = {}

    page = browser.new_page()
    page.set_extra_http_headers({'Accept-Language': 'en-US,en;q=0.9'})

    urls_to_check = [policy_page, base]

    for url in urls_to_check:
        try:
            page.goto(url, wait_until='domcontentloaded', timeout=20000)
            page.wait_for_timeout(2000)

            # Find all links with PDF or policy-related hrefs
            links = page.eval_on_selector_all('a[href]', '''
                links => links.map(a => ({
                    href: a.href,
                    text: a.textContent.trim().substring(0, 100)
                }))
            ''')

            for link in links:
                href = link.get('href', '')
                text = link.get('text', '')
                if href and is_relevant_pdf(href, text):
                    found_pdfs[href] = {'pdf_url': href, 'link_text': text, 'found_on': url}

            # Also look for links to product/download sub-pages
            nav_links = page.eval_on_selector_all('a[href]', '''
                links => links.map(a => ({href: a.href, text: a.textContent.trim().toLowerCase()}))
                    .filter(l => l.text.includes("download") || l.text.includes("policy document") || l.text.includes("wording"))
            ''')

            for nav in nav_links[:5]:
                sub_url = nav.get('href', '')
                if sub_url and sub_url != url and base in sub_url:
                    try:
                        page.goto(sub_url, wait_until='domcontentloaded', timeout=15000)
                        page.wait_for_timeout(1500)
                        sub_links = page.eval_on_selector_all('a[href]', '''
                            links => links.map(a => ({href: a.href, text: a.textContent.trim().substring(0, 100)}))
                        ''')
                        for link in sub_links:
                            href = link.get('href', '')
                            text = link.get('text', '')
                            if href and is_relevant_pdf(href, text):
                                found_pdfs[href] = {'pdf_url': href, 'link_text': text, 'found_on': sub_url}
                    except PlaywrightTimeout:
                        pass

        except PlaywrightTimeout:
            print(f"  [timeout] {url}")
        except Exception as e:
            print(f"  [error] {url}: {e}")

    page.close()
    result = list(found_pdfs.values())
    print(f"  Found {len(result)} PDFs")
    for r in result[:5]:
        print(f"    - {r['link_text'][:40]:40} {r['pdf_url'][:70]}")
    return result


def run(insurer_ids=None, limit=None):
    seed_path = os.path.join(os.path.dirname(__file__), '..', 'data', 'insurers_india.json')
    with open(seed_path) as f:
        insurers = json.load(f)

    if insurer_ids:
        insurers = [i for i in insurers if i['id'] in insurer_ids]
    if limit:
        insurers = insurers[:limit]

    all_results = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=['--no-sandbox'])
        for insurer in insurers:
            pdfs = scrape_with_playwright(insurer, browser)
            all_results.append({**insurer, 'pdfs': pdfs})
        browser.close()

    out_path = os.path.join(os.path.dirname(__file__), '..', 'data', 'policies_found.json')
    existing = []
    if os.path.exists(out_path):
        with open(out_path) as f:
            existing = json.load(f)
        existing_ids = {r['id'] for r in existing}
        all_results = [r for r in all_results if r['id'] not in existing_ids] + \
                      [r for r in existing if r['id'] not in {r['id'] for r in all_results}]

    with open(out_path, 'w') as f:
        json.dump(all_results, f, indent=2)

    total = sum(len(r.get('pdfs', [])) for r in all_results)
    print(f"\nDone. {total} PDFs found across {len(all_results)} insurers -> data/policies_found.json")
    return all_results


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--ids', nargs='+', help='Specific insurer IDs to scrape')
    parser.add_argument('--limit', type=int, help='Max insurers to scrape')
    args = parser.parse_args()
    run(insurer_ids=args.ids, limit=args.limit)
