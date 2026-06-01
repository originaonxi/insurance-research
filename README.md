# Insurance Research

> Policy document is the new marketing.
> Compare every insurance policy by what actually happens — not what ads say.

## The Problem

- 500M+ Indians need health, life, and auto insurance
- Everyone buys based on ads, agents, and word of mouth
- Nobody reads the policy document — 80 pages of legalese
- When something happens (accident, illness, death), the fine print decides everything

## What We Build

Free AI-powered insurance comparison where the policy document is the only source of truth.

- Scrape every policy PDF from every IRDAI-registered insurer
- AI extracts the 10 things that actually matter in plain language
- Compare policies head-to-head: waiting periods, exclusions, claim limits
- Direct Buy Now links to official insurer websites — no broker, no middleman
- Real claim settlement ratios. Real exclusions. Real prices.

## Core Principles

1. Policy document only — if not in the PDF, it does not exist
2. Direct to insurer — every buy link goes to the official company website
3. Free for buyers — always
4. Plain language — an 18-year-old must understand it
5. No paid rankings — no sponsored listings ever

## Products

Health Insurance, Life Insurance, Auto Insurance, Accident Insurance

## What AI Extracts (per policy document)

1. What is covered
2. What is NOT covered (exclusions)
3. Waiting periods
4. Sub-limits (room rent caps, procedure limits)
5. How to actually file a claim
6. Claim settlement ratio (IRDAI official data)
7. Pre-existing disease clauses
8. Renewal and premium hike terms
9. Free-look period
10. Cashless network hospitals

## Data Pipeline

IRDAI Registry -> Apify Scraper -> PDF Download -> Claude AI Parser -> Airtable -> Comparison Engine -> Web/App

## Stack (Planned)

- Scraper: Apify
- AI: Claude API (PDF extraction + plain-language summaries)
- Database: Airtable (policy tracking) + PostgreSQL (structured data)
- Backend: FastAPI
- Frontend: Next.js + React Native
- Storage: Cloudflare R2 (PDF files)

## Business Model

- Free for buyers
- Listing fee from insurers (presence only, not ranking)
- Phase 1: India (all IRDAI insurers)
- Phase 2: Global

Status: Pre-build. Initialized 2026-06-01.
