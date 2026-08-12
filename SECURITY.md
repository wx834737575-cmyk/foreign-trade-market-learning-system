# Security and deployment boundary

This project is local-first. The reference launcher binds the FastAPI service
to `127.0.0.1` and is intended for one user's Windows computer.

## Do not publish

- `.env` files, API keys, access tokens, cookies, passwords, certificates, or private keys;
- SQLite databases, raw evidence, logs, backups, or customer and business exports;
- private hostnames, server configuration, or deployment credentials;
- unpublished product, order, quotation, or account information.

## Public deployment warning

The current sample API has write endpoints for local notes and update checks.
It is not a multi-user or internet-facing service and does not provide
authentication. Do not expose it directly to the public internet. A public
deployment would require authentication, authorization, rate limiting, safe
secret handling, audit logging, and a separate review of data-source terms.

## Reporting a vulnerability

Please do not include credentials or private data in a public issue. For a
security report, open a minimal issue that only describes the affected area
and request a private contact channel from the maintainer.
