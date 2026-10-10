The isolated TEST implementation passes the required service and integration gates. Production deployment is NOT TESTED and remains disabled pending coordinator configuration and acceptance. No live mail, callback, signing provider, cloud deployment or public listener was used. No push or review was opened.

The implementation extends the repaired POC at 26316599be8a48e4b62163d1e29ed7f680a39f1b on codex/production-document-service. Original POC compose, addons, adapter, scripts and reports remain unchanged. New runtime files and two independent TEST volume sets are ignored and preserved. The pinned user-owned OCA forks, pinned Odoo image, licences and source offer are recorded in UPSTREAMS.json, NOTICE and LICENSE. The matching implementation source must be published by the coordinator before public use.

Completed behavior:

- Authenticated REST routes and HttpDocumentService adapter reuse immutable Odoo QWeb/OCA DMS/OCA Sign operations. Individually registered tenant/operator credentials enforce project-limited or explicitly tenant-wide access. Organisation ledger versions preserve projectId=null; future projects remain within the registered tenant. Artifact URLs contain no credentials and binary downloads require service Authorization.
- Five frozen version-1 templates render explicit saved field whitelists and normalized parties: purchase_order, packing_list, invoice, ledger_statement, contract. Customer documents exclude internal notes, factory costs/margins and supplier metadata; packing lists omit commercial amounts. Saved CAD lines/totals, quantities, approved terms, type/status and canonical demonstration labels are rendered. Contracts accept approved saved orders with approvedBy/approvedAt/terms and reject draft/unapproved inputs. No business calculations, tax policy or commercial terms are invented.
- Request-specific emailed OTP verification gates the existing OCA signing UI and binary routes. OTP codes are salted/hashed, short-lived, single-use, rate/attempt bounded; scoped sessions are rotated and HttpOnly/Secure/SameSite. Portal-only recipients cannot use public password/admin/database/native attachment routes. Two distinct synthetic example.test recipients completed the actual OCA browser journey.
- The isolated sealer requires its own injected authentication and keeps its private key outside Odoo/DB. pyHanko seals the actual final PDF and cryptography signs frozen evidence. Verification pins a separate public certificate. HTTP mutation checks reject altered snapshots/templates/PDF/evidence and changed bytes plus DB hash anchors.
- Final OCA completion persists and verifies artifacts before atomically queueing the durable callback. The worker verifies again before claim, sends only after transaction commit, preserves stable event identity and the original signRequest context.operationId, and signs the exact payload with HMAC and a fresh timestamp. Fake sink failure/recovery, duplicate delivery and invalid/stale authentication pass. The same leased bounded outbox handles fake mail and the configured production Resend adapter.
- Full TEST restart retained identical artifact bytes and independent verification. Encrypted pg_dump restored into an isolated throwaway database with matching record counts, artifact anchors and actual binary attachment/DMS bytes; active DB remained intact. Runtime keys were excluded from exports.

Actual test evidence (nonsecret summaries remain in ignored artifacts; counts are assertions, not independent scenarios):

| Evidence | Result | Assertions |
|---|---|---:|
| http-tests.json | PASS | 30 |
| concurrency-tests.json | PASS, fresh final DB calls | 5 |
| privacy-scope-tests.json | PASS, all five actual PDF text outputs | 75 |
| otp-ui-tests.json | PASS, two actual OCA recipients after final template/sealer changes | 20 |
| artifact-tests.json | PASS | 18 |
| callback-tests.json | PASS, fake callback only | 8 |
| credential-tests.json | PASS | 5 |
| sealer-boundary-tests.json | PASS | 3 |
| tamper-http-tests.json | PASS, actual HTTP mutations/restoration | 9 |
| restart-tests.json | PASS, final full restart | 21 |
| backup-restore-tests.json | PASS, isolated restored DB | 5 |
| otp-negative-tests.json | PASS, reused unchanged-flow evidence | 13 |
| outbox-tests.json | PASS, reused unchanged mail/lease evidence | 6 |
| uploads-template-tests.json | PASS, reused unchanged upload/version evidence | 15 |

Python compilation, TypeScript type checking and production Compose configuration validation also passed. Only changed behavior and the required browser/artifact journey were rerun; previous passing unchanged-flow evidence was retained. No load benchmark or broad penetration project was undertaken.

NOT TESTED: public DNS/TLS, coordinator application wiring and download proxy, live Packaging callback, real Resend delivery, production injected secrets/certificate and production bootstrap/deployment. Production volumes remain empty/unstarted. INSTALL.md documents safe secret-file injection, credential registration, exact template identifiers, callback/download transport, Caddy/private networks, backup validation and stop commands.

The TEST seal certificate is self-signed and explicitly labelled TEST. No CA trust or trusted timestamp is claimed. The service seal is distinct from recipient signatures; mailbox verification does not establish legal human identity or legal signature suitability. Database archives contain confidential records, hashes and any queued mail bodies and require encryption/access control. Outbox attempts are bounded; exhausted delivery requires private operator requeue of the same stable operation. Odoo runs as root inside its isolated container to consume mode-600 config, with no public port, Docker socket or private seal key.

Concise follow-up list: coordinator publication/configuration/acceptance and app wiring; optional non-root secret ownership arrangement; optional visual polish through existing Odoo template tooling. No extra dashboard, quote template or app-side rendering/signing engine was added.

Final cleanup stops only this implementation's TEST containers and retains volumes. IMPLEMENTATION-SUMMARY state in artifacts/implementation-summary.json records the final cleanup result. Source/tests/docs and the two nonsecret summaries are committed; credentials, captures, PDFs, encrypted backups, vendor trees and coordinator-owned prompt files are excluded.

Coordinator compatibility acceptance: 21 additional HTTP/PDF assertions passed using actual Packaging decimal-unit-price lines, shipment items/dates/options, factory purchaseOrders/factoryPayments/factoryAdjustments, supplier party labels, configured tax labels, demo labels and customer-field exclusion. No-project descriptors omit projectId to match the TypeScript API contract. Fresh test template version 2 was registered without mutating version 1. Production starts on empty volumes with corrected version-1 templates. Generated unknown key text was removed from the unpublished commit and excluded from release source without inspecting its value. Public recipient pages offer the matching source repository.

Automatic-review acceptance: authenticated generic image downloads now reject image content while the bound image route remains usable. Historical public certificates are retained outside the database, new evidence records their fingerprint, and old actual HTTP signed-PDF/evidence downloads survived a different active sealer key/certificate. Standalone pin and untrusted-certificate negatives passed. Nine focused HTTP regressions cover image association, normalized signer retries, required ledger identity/privacy and optional project descriptors; four retained-pin assertions and two actual rotation HTTP assertions passed. TypeScript compilation passed. Optional fixture transport and future presentation-version freezing are tracked in GitHub issues #2 and #3.
