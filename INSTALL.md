The service preserves the repaired POC at source commit
26316599be8a48e4b62163d1e29ed7f680a39f1b. Original compose/addons/adapter/scripts
and reports remain unchanged. Use compose.service.yaml, never the original
compose or its runtime/volumes. Pinned fork sources and licences are in
UPSTREAMS.json, NOTICE and LICENSE. The public source offer must include the exact
deployed commit; this implementation has not been pushed or publicly deployed.

TEST installation (Docker Compose 2.24.4+, Python venv, Node and pdftotext):

```sh
bash service/fetch.sh
python3 -m venv runtime-test-venv
runtime-test-venv/bin/pip install -r service/requirements.txt requests
npm ci
runtime-test-venv/bin/python service/prepare.py
python3 service/manage.py init
runtime-test-venv/bin/python tests/http_service.py
runtime-test-venv/bin/python tests/fresh-concurrency.py
python3 service/register_tenant.py --tenant synthetic-wide --operator operator-wide@example.test --tenant-wide --credential-file service-runtime/tenant-wide.token
runtime-test-venv/bin/python tests/privacy-scope.py
runtime-test-venv/bin/python tests/prepare-ui.py
node tests/otp-ui.mjs
runtime-test-venv/bin/python tests/artifacts.py
runtime-test-venv/bin/python tests/sealer-boundary.py
runtime-test-venv/bin/python tests/callback.py
python3 service/manage.py shell service/tamper-http.py
runtime-test-venv/bin/python tests/otp-negatives.py
runtime-test-venv/bin/python tests/outbox.py
```

Initialize only a new empty service DB. UI/negative tests consume challenges and
signatures: run each journey once on a fresh DB. Stable provider operations replay
unchanged inputs, while changed inputs conflict. The original development TEST
volumes were retained separately; final safe templates use the independent
agentfleet-document-service-test-final compose project. All test ports bind only
127.0.0.1:18079; Odoo/Postgres/sealer/callback sink publish no host ports.

Generated secrets and private fake mailbox captures stay mode 600 beneath
service-runtime/. Never display credentials, captures, codes, cookies, signing
URLs or worker logs. No dotenv file is used. Set SERVICE_UID/SERVICE_GID to the
runtime file owner's IDs if defaults 1000/1001 differ. The small isolated compose
runs Odoo as root to read mode-600 injected config; it mounts no sealing key or
Docker socket and publishes no port. A non-root secret ownership arrangement is
an optional deployment hardening follow-up, not a tested claim.

REST and authenticated download transport

Every /v1 route requires an individually registered `Authorization: Bearer`
credential scoped to a tenant/operator and either explicit projects or an
explicit tenant-wide grant. Tenant-wide grants allow future project IDs and
no-project organisation statements, never another tenant. Revoke a credential by
setting document.credential.active=false in private Odoo tooling. POST bodies are
`{context,input}`; context uses tenantId, documentId, operationId, optional
projectId/localDocumentId/actorId. Reads require tenantId. A saved unique project
can be inferred for GET routes; ambiguous projects require projectId. No-project
versions return projectId=null and remain distinct from project-associated ones.

| Method | Route | Input/result |
|---|---|---|
| POST | /v1/uploads | filename, contentType, contentBase64; version |
| GET | /v1/templates/:id/versions/:version | authenticated metadata |
| POST | /v1/documents | templateId, templateVersion, snapshot; version |
| GET | /v1/documents/:documentId/versions?tenantId=... | versions |
| POST | /v1/signature-requests | versionId, one/two distinct signers |
| POST | /v1/signature-requests/:requestId/status | versionId; pending/partial/completed |
| GET | /v1/documents/:documentId/versions/:versionId/artifacts?tenantId=... | metadata |
| GET | /v1/documents/:documentId/versions/:versionId/image?tenantId=...&actorId=...&localDocumentId=... | associated image |
| GET | /v1/documents/:documentId/versions/:versionId/download/:kind?tenantId=... | authenticated binary bytes |

Metadata is {kind,url,versionId,tenantId,documentId,projectId,fixture,
localDocumentId?}. Artifact URLs use https://documents.agentfleet.services/v1/
without embedded credentials. Packaging's authenticated API proxy fetches bytes
with service Authorization. Kinds are document, signed_document, evidence. Final
artifacts are unavailable before verified sealed completion. Wrong scope is 403,
unavailable artifact 404, integrity/conflict/prerequisite failure 409. Uploads
support PDF and validated PNG/JPEG/WebP; image identity additionally binds saved
actorId/localDocumentId. adapter/HttpDocumentService.ts preserves the supplied
reference interface/route shapes; the REST contract also accepts Packaging's
updated optional project association. Service credentials stay in trusted server
code, never recipient browsers. HTTPS certificate verification remains enabled.

Saved snapshots and templates

Initial template IDs: purchase_order, packing_list, invoice, ledger_statement,
contract. All version="1". Configure these in existing Packaging Business settings.
Non-ledger snapshots are {source:{kind,id,revision,data},project?:Entity,
parties:{business?,customer?,factory?},demonstration}. Only whitelisted saved
party name/email/address, document number/status/date, line description/quantity,
saved prices/totals and approved terms are presented. Source/project records stay
frozen internally and are never rendered as dictionaries. Factory presentation
is limited to purchase orders and explicitly factory-scoped ledgers. Packing
lists omit all monetary columns/totals/terms. Customer PDFs omit factory metadata,
internal notes, factory costs and margins. Amount formatting converts saved cents
for display only; the service does not calculate tax, totals, balances or dates.

Contracts require source.kind=orders, data.status=approved, approvedBy,
approvedAt and saved nonempty terms; draft/unapproved orders fail clearly. No
termsApproved business field is required. Normalized saved business/customer
parties are required (business/factory for purchase orders). Ledger snapshots
require organisation, invoices, receipts, allocations, adjustments and may carry
dateFrom/dateTo, openingBalanceCents/balanceCents, parties and no projectId; they
have no source field. Entity ledger rows use their saved data fields. Demonstration
marks recognize root demonstration, project.data.demonstration and saved
fixture/evidence-mode flags. Use Odoo QWeb tooling and register new frozen template
versions for future edits; never mutate a version already used for records.

Recipient access, mail and completion callbacks

Invitation `/recipient/:requestId` is a non-secret locator. Recipient mailbox
verification uses a five-minute emailed OTP, salted PBKDF2 hashes, five attempts,
three issuances per recipient/request per fifteen minutes and single use. It binds
exact recipient name/email, signer/request and document version. Odoo rotates a
fresh HttpOnly Secure SameSite=Strict session with a twenty-minute scoped grant.
The exact-partner and verified-grant checks apply in TEST and production. Signer
principals are portal-only; generated passwords are never printed or emailed.
Public native password/database/admin/authentication/dataset and attachment
routes are blocked at ingress. Private issuer/admin Odoo tooling remains possible.

The existing small durable outbox handles mail and callbacks: stable operation,
transactional claim, sixty-second lease, five bounded attempts and delayed retry.
Delivery occurs after the claim transaction commits. Queued OTP mail bodies are
cleared after delivery; authentication challenges store salted hashes. Protect DB
and encrypted backup access. Fake capture files remain private. Production Resend
uses feroz@agentfleet.services and a stable Idempotency-Key; a finite provider
idempotency window is not an unlimited exactly-once delivery guarantee.

Final OCA signing automatically persists/verifies the service-sealed PDF/evidence
and queues a completion callback in the same transaction. The worker re-verifies
artifacts before claiming the callback. Payload is {eventId,tenantId,documentId,
versionId,signatureRequestId,status:completed}; signatureRequestId is the ORIGINAL
signRequest context.operationId, not provider requestId. The eventId stays stable
across retries. x-dms-timestamp is fresh Unix seconds; x-dms-signature is
HMAC-SHA256(timestamp + dot + exact JSON body), using an injected shared secret.
The production URL is
https://packaging-ops-261008.web.app/api/v1/webhooks/dms. The TEST-only private sink
independently verifies HMAC/five-minute freshness and deduplicates stable events.
No live callback was sent. Review exhausted outbox rows privately; do not print
sensitive bodies. Long outages may exhaust bounded retry and require operator
requeue of the SAME operation; never manufacture a new completion identity.

Sealing and independent verification

pyHanko cryptographically seals the actual final OCA PDF; cryptography signs the
canonical manifest of frozen snapshot/template hashes, associations, recipient
mailbox-verification/signing events and final bytes. Completion requires both
persisted artifacts. The sealer shares a dedicated private network with Odoo,
not the DB, requires a separate injected bearer credential and exclusively mounts
the private seal key. Odoo/DB/mail do not mount the key. Verification pins a public
certificate separately from DB anchors. Test certificates are clearly self-signed
TEST certificates, not CA trusted; there is no trusted timestamp. A service seal
is distinct from recipient signatures and mailbox verification is not proof of
legal human identity. No legal suitability claim is made.

```sh
runtime-test-venv/bin/python service/verify.py artifacts/final-signed_document.pdf artifacts/final-evidence.json artifacts/verification-public.crt
```

Retain public verification certificates independently and historically on rotation.
Never trust only a certificate embedded in an untrusted document/database.

Coordinator-only production preparation (NOT executed)

Use a separate empty runtime directory, database and production volumes. Inject
secret files using these environment variable NAMES: SERVICE_RUNTIME_DIR,
SERVICE_DB_NAME, DB_PASSWORD_FILE, ODOO_MASTER_PASSWORD_FILE,
SERVICE_CREDENTIAL_FILE, MAIL_WORKER_CREDENTIAL_FILE, SEAL_PRIVATE_KEY_FILE,
SEAL_CERTIFICATE_FILE, SEAL_AUTH_TOKEN_FILE, RESEND_API_KEY_FILE,
DMS_CALLBACK_SECRET_FILE. configure_production.py consumes them without printing
values, creates mode-600 files and rejects TEST seal certificates. Provide a
separately pinnable real service certificate/key. Production mode additionally
requires explicit PRODUCTION_ACCEPTED=yes; the implementation leaves it disabled.
PUBLIC_ORIGIN is https://documents.agentfleet.services. Coordinator handles DNS,
HTTPS, app integration, acceptance and public source publication.

```sh
runtime-test-venv/bin/python service/configure_production.py
export PRODUCTION_RUNTIME_DIR="$SERVICE_RUNTIME_DIR"
docker compose --env-file /dev/null -f compose.service.yaml -f compose.production.yaml build sealer
docker compose --env-file /dev/null -f compose.service.yaml -f compose.production.yaml up -d db
docker compose --env-file /dev/null -f compose.service.yaml -f compose.production.yaml run --rm odoo --config=/run/config/odoo.conf --stop-after-init -i document_service --without-demo=all
docker compose --env-file /dev/null -f compose.service.yaml -f compose.production.yaml run --rm -T odoo shell --config=/run/config/odoo.conf --no-http < service/bootstrap_production.py
docker compose --env-file /dev/null -f compose.service.yaml -f compose.production.yaml up -d odoo
python3 service/register_tenant.py --tenant "$TENANT_ID" --operator "$OPERATOR_LOGIN" --tenant-wide --credential-file "$SERVICE_CREDENTIAL_FILE" --production-runtime-dir "$PRODUCTION_RUNTIME_DIR"
```

PRODUCTION_RUNTIME_DIR refers to that separate runtime directory. For limited
credentials replace --tenant-wide with one/more --project arguments. Existing
operators cannot move tenants and existing credential scopes cannot silently
change; rotate with a new credential file and revoke the old row. Only after
coordinator acceptance start the remaining production services. The TEST callback
sink uses a test profile and is never part of production startup. The production
sealer image installs dependencies at build time; pinned core Odoo is unchanged.
Caddy alone publishes 80/443; Odoo/DB/ingress remain private. No firewall changes
or public deployment occurred during implementation.

Encrypted backup/restore and stopping

Attachments/DMS bytes use database storage. The backup script refuses DB-only
backup if filesystem attachment pointers exist. pg_dump archives are encrypted;
no runtime secret files, private seal keys or injected provider credentials are
exported. The encrypted database archive still contains confidential documents,
recipient records, credential hashes and any queued mail bodies. Treat it as sensitive. Provision a separate mode-600 backup.key and keep it outside data/exports.

```sh
runtime-test-venv/bin/python service/backup.py backup artifacts/final-database.dump.encrypted
runtime-test-venv/bin/python service/backup.py validate artifacts/final-database.dump.encrypted
python3 service/manage.py restart
runtime-test-venv/bin/python tests/artifacts.py restart
python3 service/manage.py stop
```

Validation decrypts in memory, restores a random throwaway DB, compares records,
anchors and actual binary payloads, preserves the active DB, then drops only the
throwaway DB. Production selection uses SERVICE_BACKUP_DB,
SERVICE_BACKUP_RUNTIME_DIR and SERVICE_BACKUP_PRODUCTION_RUNTIME_DIR. A deliberate
recovery stops traffic, restores into a NEW DB, retains separate seal keys/public
certificates, verifies artifacts, and changes Odoo DB configuration only after
review. This helper never overwrites the active DB or switches traffic. Stop only
this TEST compose; retain volumes and never run down -v to preserve records.
