# Data sources and provenance

This repository contains reusable ingestion and validation code. It does not
publish the maintainer's private database, raw evidence archive, customer
records, business-channel exports, or unpublished notes.

## Source register

| Institution | Public entry point | Data used | Access boundary |
| --- | --- | --- | --- |
| People's Bank of China | <https://www.pbc.gov.cn/diaochatongjisi/116219/116319/index.html> | M0/M1/M2 balances and growth rates | Use the official publication and retain publication/version evidence. |
| National Bureau of Statistics of China | <https://www.stats.gov.cn/sj/zxfb/> | PMI, CPI, PPI, industrial value added and retail sales | Discover releases from the official publication directory and validate the released tables. |
| China Foreign Exchange Trade System / ChinaMoney | <https://www.chinamoney.com.cn/chinese/bkccpr/index.html?tab=2> | USD/CNY central parity | Restrict requests and validate the returned host and official payload. |
| Shanghai Shipping Exchange | <https://www.sse.net.cn/index/singleIndex?indexType=scfi> | SCFI and CCFI latest composite values | The current project treats these as local learning references; it does not publish a historical mirror. |
| General Administration of Customs | <https://stats.customs.gov.cn/> | Officially exported trade statistics | Import only a user-provided official export with its query conditions and SHA-256 evidence. |

## Provenance rules

Each production observation should retain, where available:

- the statistical period and publication time;
- the source URL and source institution;
- the acquisition time;
- the unit and methodology/version;
- the raw artifact fingerprint (SHA-256);
- a quality status such as `verified`, `pending`, `expired`, or `demo_unverified`.

Unverified or demonstration values must be visibly labelled and must not be
used as verified evidence for a decision. Release revisions are retained as
separate vintages instead of silently overwriting earlier values.

## Reuse and attribution

The code is released under the MIT License. The public websites and datasets
linked above remain subject to their own terms, notices, copyright, and access
policies. This repository does not grant rights to third-party logos, page
screenshots, raw files, or data beyond what the relevant source permits.

Before redistributing a source file or building a public mirror, check the
source's current terms and use the smallest necessary data extract.
