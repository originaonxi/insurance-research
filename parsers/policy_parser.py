#!/usr/bin/env /opt/homebrew/opt/python@3.11/bin/python3.11
"""
OG policy parser — pure regex + keyword extraction. No API calls, no cost.
"""
import re, os, json, tempfile, requests
import pdfplumber

HEADERS = {'User-Agent': 'Mozilla/5.0 Chrome/120.0.0.0'}


def download_pdf(url):
    resp = requests.get(url, headers=HEADERS, timeout=30, stream=True)
    resp.raise_for_status()
    with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as f:
        for chunk in resp.iter_content(8192):
            f.write(chunk)
        return f.name


def pdf_to_text(path, max_pages=60):
    pages = []
    with pdfplumber.open(path) as pdf:
        for page in pdf.pages[:max_pages]:
            t = page.extract_text()
            if t:
                pages.append(t)
    return '\n'.join(pages)


def split_sections(text):
    """Split on SECTION I / II / III ... or numbered headings."""
    pattern = re.compile(
        r'(?m)^(?:SECTION\s+[IVXLC\d]+[\.\s]|'
        r'\d+\.\s+(?=[A-Z]{4}))'
        r'[A-Z][A-Z\s\-/]{4,60}$'
    )
    positions = [(m.start(), m.group(0).strip()) for m in pattern.finditer(text)]
    sections = {}
    for i, (pos, title) in enumerate(positions):
        end = positions[i + 1][0] if i + 1 < len(positions) else len(text)
        sections[title.lower()] = text[pos:end]
    return sections


def find_section(sections, *keywords):
    for title, body in sections.items():
        if any(kw in title for kw in keywords):
            return body
    return ''


def after_keyword(text, kw, chars=600):
    idx = text.lower().find(kw.lower())
    return text[idx:idx + chars].replace('\n', ' ').strip() if idx != -1 else ''


def extract_money_amounts(text):
    hits = re.findall(
        r'(?:Rs\.?|INR|₹)\s*[\d,]+(?:\.\d+)?(?:\s*(?:Lakhs?|Crores?|L|Cr))?'
        r'|[\d,]+\s*(?:Lakhs?|Crores?)',
        text, re.IGNORECASE
    )
    return list(dict.fromkeys(hits))[:8]


def extract_numbered_list(text, start=0, max_items=15):
    """Pull numbered or lettered bullet lines from text."""
    items = re.findall(
        r'(?m)^[\s]*(?:\d+[\.\)]|[a-z][\.\)]|[\-\•])\s+(.+)',
        text[start:]
    )
    return [i.strip() for i in items[:max_items] if len(i.strip()) > 8]


def product_name_from_header(text):
    """Second non-empty line is usually the product name in Indian policy docs."""
    lines = [l.strip() for l in text[:800].split('\n') if l.strip()]
    for line in lines[1:5]:
        if re.search(r'policy|plan|insurance|cover', line, re.IGNORECASE):
            return re.sub(r'\s+', ' ', line)[:120]
    return lines[1] if len(lines) > 1 else 'Unknown'


# ─── Category Parsers ─────────────────────────────────────────────────────────

def parse_auto(text, sections):
    result = {'category': 'auto'}
    result['product_name'] = product_name_from_header(text)

    # Coverage type from product name / first section
    header = text[:500].lower()
    if 'comprehensive' in header or 'package policy' in header:
        result['coverage_type'] = 'comprehensive'
    elif 'liability only' in header or 'third party' in header or 'third-party' in header:
        result['coverage_type'] = 'third-party only'
    elif 'stand alone own damage' in header or 'saod' in header:
        result['coverage_type'] = 'own damage'
    else:
        result['coverage_type'] = 'comprehensive'

    # What IS covered — numbered list under Section I
    sec1 = find_section(sections, 'section i', 'loss of or damage', 'own damage') or text[:3000]
    result['what_is_covered'] = extract_numbered_list(sec1, max_items=12)

    # Exclusions — "Company shall not be liable" or Section of Exceptions
    excl_idx = text.lower().find('shall not be liable')
    if excl_idx == -1:
        excl_idx = text.lower().find('exclusion')
    excl_chunk = text[excl_idx:excl_idx + 2000] if excl_idx != -1 else ''
    result['exclusions'] = extract_numbered_list(excl_chunk, max_items=12)

    # NCB
    ncb_chunk = after_keyword(text, 'no claim bonus', 400) or after_keyword(text, 'ncb', 400)
    ncb_pcts = re.findall(r'(\d+(?:\.\d+)?)\s*%', ncb_chunk)
    result['ncb_scale'] = [p + '%' for p in ncb_pcts[:6]] or None

    # IDV
    idv_chunk = after_keyword(text, 'insured declared value', 500)
    result['idv_formula'] = idv_chunk[:300] if idv_chunk else None

    # Depreciation table
    dep = re.findall(r'(\d+(?:\.\d+)?)\s*%\s+[Dd]epreciation', text)
    result['depreciation_rates'] = dep[:6] or None

    # Claim process
    claim_sec = find_section(sections, 'condition', 'claim') or ''
    claim_kw = after_keyword(claim_sec or text, 'claim', 500)
    result['claim_process'] = claim_kw[:400] if claim_kw else None

    # Free look
    fl = re.search(r'free[\s\-]look[^\d]*(\d+)\s*days?', text, re.IGNORECASE)
    result['free_look_period'] = f"{fl.group(1)} days" if fl else None

    # Cancellation
    cancel = after_keyword(text, 'cancellation', 300)
    result['cancellation'] = cancel[:250] if cancel else None

    return result


def parse_health(text, sections):
    result = {'category': 'health'}
    result['product_name'] = product_name_from_header(text)

    # Sum insured
    si_sec = find_section(sections, 'sum insured', 'coverage', 'benefit', 'hospitalisation') or text[:5000]
    result['sum_insured_options'] = extract_money_amounts(si_sec) or extract_money_amounts(text[:8000])

    # Waiting periods
    wp_chunk = after_keyword(text, 'waiting period', 600) or after_keyword(text, 'initial waiting', 400)
    initial = re.search(r'initial\s+waiting\s+period[^\d]*(\d+)\s*(days?|months?)', text, re.IGNORECASE)
    ped = re.search(r'pre.?existing[^\d]*(\d+)\s*(months?|years?)', text, re.IGNORECASE)
    spec = re.findall(r'(\d+)\s*(months?|years?)[^.]*(?:specific|named|listed)\s+disease', text, re.IGNORECASE)
    result['waiting_periods'] = {
        'initial': f"{initial.group(1)} {initial.group(2)}" if initial else None,
        'pre_existing_disease': f"{ped.group(1)} {ped.group(2)}" if ped else None,
        'specific_diseases': f"{spec[0][0]} {spec[0][1]}" if spec else None,
    }

    # Room rent
    rr = re.search(
        r'room\s+(?:rent|charges?)[^.\n]{0,200}',
        text, re.IGNORECASE
    )
    result['room_rent_limit'] = rr.group(0).strip()[:150] if rr else 'No sub-limit stated'

    # Exclusions
    excl_idx = text.lower().find('exclusion')
    excl_chunk = text[excl_idx:excl_idx + 3000] if excl_idx != -1 else ''
    result['exclusions'] = extract_numbered_list(excl_chunk, max_items=15)

    # Pre-existing disease
    ped_chunk = after_keyword(text, 'pre-existing', 500) or after_keyword(text, 'pre existing', 500)
    result['pre_existing_disease'] = ped_chunk[:300] if ped_chunk else None

    # NCB
    ncb = re.search(r'no\s+claim\s+bonus[^\d]*(\d+)\s*%', text, re.IGNORECASE)
    result['no_claim_bonus'] = f"{ncb.group(1)}% per claim-free year" if ncb else None

    # Network hospitals
    net = after_keyword(text, 'network hospital', 300) or after_keyword(text, 'cashless', 300)
    result['network_hospitals'] = net[:250] if net else None

    # Claim process
    claim_sec = find_section(sections, 'claim', 'intimation') or ''
    result['claim_process'] = after_keyword(claim_sec or text, 'claim', 500)[:400]

    # Renewal
    ren = after_keyword(text, 'renewal', 400)
    result['renewal_terms'] = ren[:300] if ren else None

    # Free look
    fl = re.search(r'free[\s\-]look[^\d]*(\d+)\s*days?', text, re.IGNORECASE)
    result['free_look_period'] = f"{fl.group(1)} days" if fl else None

    return result


def parse_life(text, sections):
    result = {'category': 'life'}
    result['product_name'] = product_name_from_header(text)

    sa_sec = find_section(sections, 'sum assured', 'death benefit', 'benefit') or text[:4000]
    result['sum_assured'] = extract_money_amounts(sa_sec) or extract_money_amounts(text[:8000])

    excl_idx = text.lower().find('exclusion')
    excl_chunk = text[excl_idx:excl_idx + 2000] if excl_idx != -1 else ''
    result['exclusions'] = extract_numbered_list(excl_chunk, max_items=10)

    suicide = re.search(r'suicide[^.]{0,250}', text, re.IGNORECASE)
    result['suicide_clause'] = suicide.group(0).strip()[:200] if suicide else None

    grace = re.search(r'grace\s+period[^\d]*(\d+)\s*(days?|months?)', text, re.IGNORECASE)
    result['grace_period'] = f"{grace.group(1)} {grace.group(2)}" if grace else None

    fl = re.search(r'free[\s\-]look[^\d]*(\d+)\s*days?', text, re.IGNORECASE)
    result['free_look_period'] = f"{fl.group(1)} days" if fl else None

    claim_sec = find_section(sections, 'claim', 'nominee', 'settlement') or ''
    result['claim_process'] = after_keyword(claim_sec or text, 'claim', 500)[:400]

    revival = after_keyword(text, 'revival', 300) or after_keyword(text, 'reinstate', 300)
    result['revival_conditions'] = revival[:250] if revival else None

    return result


# ─── Main ─────────────────────────────────────────────────────────────────────

def parse_policy(pdf_url, category='health', local_path=None):
    print(f"  [{category}] {pdf_url[:80]}")
    path, cleanup = (local_path, False) if local_path else (download_pdf(pdf_url), True)
    try:
        text = pdf_to_text(path)
        if len(text) < 100:
            return {'error': 'text extraction failed', 'pdf_url': pdf_url}
        sections = split_sections(text)
        print(f"  {len(text):,} chars · {len(sections)} sections: {list(sections.keys())[:4]}")
        parsers = {'auto': parse_auto, 'life': parse_life, 'health': parse_health}
        result = parsers.get(category, parse_health)(text, sections)
        result.update({'pdf_url': pdf_url, 'char_count': len(text)})
        return result
    finally:
        if cleanup and os.path.exists(path):
            os.unlink(path)


if __name__ == '__main__':
    import sys
    url = sys.argv[1] if len(sys.argv) > 1 else \
        'https://www.godigit.com/content/dam/godigit/directportal/en/downloads/car/policy-wording-digit-private-car-policy.pdf'
    cat = sys.argv[2] if len(sys.argv) > 2 else 'auto'
    print(json.dumps(parse_policy(url, cat), indent=2, ensure_ascii=False))
