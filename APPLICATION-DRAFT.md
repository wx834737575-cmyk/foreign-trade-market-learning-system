# Codex for Open Source application draft

This draft is based only on the public review copy. Replace bracketed identity
and repository fields before submitting. Do not put API keys, passwords,
cookies, private server details, customer data, or private business exports in
this file or in the application.

## Repository

- GitHub username: `[YOUR_GITHUB_USERNAME]`
- Public repository URL: `[PUBLIC_REPOSITORY_URL]`
- Role: Primary maintainer
- License: MIT
- Project name: Foreign Trade and Market Learning System

## Why does this repository qualify? (491 characters)

I am the primary maintainer of an evidence-led dashboard for trade and market observation. It ingests indicators from documented official sources, records source and update dates, validates data, and excludes unverified values from analysis. The project provides a reusable pattern for provenance-aware economic dashboards, with current connectors for exchange rates, shipping indices, macro indicators, and trade data. I am preparing reproducible sample data and ongoing public maintenance.

## How will you use API credits for your project? (369 characters)

I would use the credits for core open-source maintenance: automated data-quality checks, regression tests for official data connectors, issue and pull-request triage, documentation updates, security reviews, and release automation. The credits would support reproducible ingestion and maintenance workflows, not private customer data, advertising, or trading execution.

## Anything else we should know? (362 characters)

This is a local-first decision-support and research tool, not an autonomous trading system or investment adviser. Indicators include source, date, and verification status, and unverified data is excluded from judgments. I am separating reusable code from private business materials and will publish only public or synthetic example data with credentials removed.

## Selection

- Select project API credits.
- Select Codex Security only after the repository has a real security-review use case and the public repository boundary is confirmed.

## Evidence to keep ready

- The README explains the learning and review loop: find official sources, understand methodology, observe data, write a hypothesis, and review it later.
- `DATA-SOURCES.md` records public source entry points and redistribution boundaries.
- `SECURITY.md` documents the local-only deployment boundary and warns against public exposure without authentication.
- The backend test suite passes in the review environment: 24 tests passed.
- The frontend production build passes in the review environment.
