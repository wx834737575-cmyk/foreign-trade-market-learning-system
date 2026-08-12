# Contributing

Contributions are welcome for parser tests, provenance checks, documentation,
accessibility, and reproducible local setup.

Please keep pull requests focused and include:

- the problem or use case;
- tests for parser or metric changes;
- source, unit, period, and quality-status handling for new indicators;
- a note about any source terms or redistribution limits;
- confirmation that no private data, credentials, customer records, or raw
  evidence were added.

Do not add live credentials or private business exports. New ingestion code
must validate the expected official host and must not silently treat failed or
unverified retrievals as verified data.
