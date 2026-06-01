#!/usr/bin/env /opt/homebrew/opt/python@3.11/bin/python3.11
"""
Crawls each IRDAI insurer website to find policy document PDF links.
Government mandate: every insurer must publish policy wordings publicly.
"""
import json, os, re, time, requests
from urllib.parse import urljoin, urlparse
from bs4 import BeautifulSoup
from dotenv import load_dotenv

load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), '..', '.env'))

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
}

PDF_KEYWORDS = ['policy', 'wording', 'document', 'brochure', 'terms', 'conditions', 'prospectus', 'schedule']
PDF_ANTI_KEYWORDS = ['claim', 'form', 'proposal', 'kyc', 'neft', 'mandate', 'annual-report', 'investor']

POLICY_PAGE_PATTERNS = [
    '/downloads', '/download', '/policy-document', '/policy-documents',
    '/policy-wording', '/policy-wordings', '/terms-and-conditions',
    '/products', '/insurance-plans', '/plans', '/our-products',
]


def is_relevant_pdf(url, text):
    url_lower = url.lower()
    text_lower = text.lower()
    combined = url_lower + ' ' + text_lower
    if not any(kw in combined for kw in PDF_KEYWORDS):
        return False
    if any(kw in url_lower for kw in PDF_ANTI_KEYWORDS):
        return False
    return True


def find_pdfs_on_page(url, session):
    found = []
    try:
        resp = session.get(url, headers=HEADERS, timeout=15)
        resp.raise_for_status()
    except Exception as e:
        print(f"  [skip] {url}: {e}")
        return found

    soup = BeautifulSoup(resp.text, 'html.parser')
    for a in soup.find_all('a', href=True):
        href = a['href']
        text = a.get_text(strip=True)
        full_url = urljoin(url, href)
        if full_url.lower().endswith('.pdf') and is_relevant_pdf(full_url, text):
            found.append({'pdf_url': full_url, 'link_text': text, 'found_on': url})
    return found


def find_policy_pages(base_url, policy_page, session):
    pages = [policy_page]
    try:
        resp = session.get(base_url, headers=HEADERS, timeout=15)
        soup = BeautifulSoup(resp.text, 'html.parser')
        for a in soup.find_all('a', href=True):
            href = a['href'].lower()
            if any(p in href for p in POLICY_PAGE_PATTERNS):
                full = urljoin(base_url, a['href'])
                if urlparse(full).netloc == urlparse(base_url).netloc:
                    pages.append(full)
    except Exception:
        pass
    return list(set(pages))[:5]


def scrape_insurer(insurer, session):
    name = insurer['name']
    print(f"\n[{insurer['category'].upper()}] {name}")
    all_pdfs = []

    pages = find_policy_pages(insurer['website'], insurer['policy_page'], session)
    for page in pages:
        print(f"  scanning: {page}")
        pdfs = find_pdfs_on_page(page, session)
        all_pdfs.extend(pdfs)
        time.sleep(1.5)

    unique = list({p['pdf_url']: p for p in all_pdfs}.values())
    print(f"  found {len(unique)} policy PDFs")
    return {**insurer, 'pdfs': unique}


def run():
    seed_path = os.path.join(os.path.dirname(__file__), '..', 'data', 'insurers_india.json')
    with open(seed_path) as f:
        insurers = json.load(f)

    session = requests.Session()
    results = []
    for insurer in insurers:
        result = scrape_insurer(insurer, session)
        results.append(result)

    out_path = os.path.join(os.path.dirname(__file__), '..', 'data', 'policies_found.json')
    with open(out_path, 'w') as f:
        json.dump(results, f, indent=2)

    total_pdfs = sum(len(r.get('pdfs', [])) for r in results)
    print(f"\nDone. {total_pdfs} policy PDFs found across {len(results)} insurers.")
    print(f"Saved to data/policies_found.json")


if __name__ == '__main__':
    run()
