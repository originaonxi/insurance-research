#!/usr/bin/env /opt/homebrew/opt/python@3.11/bin/python3.11
"""
Poltruth server — serves static files + reviews API.
Run: python3.11 server.py
"""
import json, os, uuid, hashlib
from datetime import datetime
from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel
import uvicorn

BASE = os.path.dirname(os.path.abspath(__file__))
REVIEWS_FILE = os.path.join(BASE, 'data', 'reviews.json')

app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=['*'], allow_methods=['*'], allow_headers=['*'])

def load_reviews():
    if not os.path.exists(REVIEWS_FILE):
        return []
    with open(REVIEWS_FILE) as f:
        return json.load(f)

def save_reviews(reviews):
    with open(REVIEWS_FILE, 'w') as f:
        json.dump(reviews, f, indent=2)

class ReviewIn(BaseModel):
    policy_id: str
    insurer_id: str
    policy_name: str
    rating: int           # 1-5
    claim_happened: bool  # did they actually claim?
    review_text: str
    claim_outcome: str    # approved / partial / rejected / not_claimed_yet
    policy_number_hash: str  # sha256 of their policy number — proves ownership, keeps anonymous
    name: str = 'Anonymous'

@app.get('/api/reviews/{policy_id}')
def get_reviews(policy_id: str):
    reviews = load_reviews()
    pol = [r for r in reviews if r['policy_id'] == policy_id]
    pol.sort(key=lambda r: r['date'], reverse=True)
    return {'reviews': pol, 'count': len(pol), 'avg_rating': round(sum(r['rating'] for r in pol)/len(pol), 1) if pol else 0}

@app.get('/api/reviews')
def get_all_reviews():
    reviews = load_reviews()
    return {'reviews': reviews, 'count': len(reviews)}

@app.post('/api/reviews')
def post_review(r: ReviewIn):
    if not 1 <= r.rating <= 5:
        raise HTTPException(400, 'Rating must be 1-5')
    if len(r.review_text.strip()) < 30:
        raise HTTPException(400, 'Review must be at least 30 characters')
    if not r.policy_number_hash or len(r.policy_number_hash) < 8:
        raise HTTPException(400, 'Policy number hash required')

    reviews = load_reviews()
    review = {
        'id': str(uuid.uuid4())[:8],
        'policy_id': r.policy_id,
        'insurer_id': r.insurer_id,
        'policy_name': r.policy_name,
        'rating': r.rating,
        'claim_happened': r.claim_happened,
        'claim_outcome': r.claim_outcome,
        'review_text': r.review_text.strip()[:1000],
        'name': r.name or 'Anonymous',
        'policy_number_hash': r.policy_number_hash[:16],
        'verified': True,  # verified = has policy number
        'date': datetime.now().isoformat()[:10],
        'helpful': 0
    }
    reviews.append(review)
    save_reviews(reviews)
    return {'ok': True, 'id': review['id']}

@app.post('/api/reviews/{review_id}/helpful')
def mark_helpful(review_id: str):
    reviews = load_reviews()
    for r in reviews:
        if r['id'] == review_id:
            r['helpful'] = r.get('helpful', 0) + 1
            save_reviews(reviews)
            return {'ok': True}
    raise HTTPException(404, 'Review not found')

@app.get('/data/web_policies.json')
def policies():
    return FileResponse(os.path.join(BASE, 'data', 'web_policies.json'))

app.mount('/', StaticFiles(directory=BASE, html=True), name='static')

if __name__ == '__main__':
    print('Poltruth running at http://localhost:8080')
    uvicorn.run(app, host='0.0.0.0', port=8080, log_level='warning')
