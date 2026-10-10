# 50 end-to-end use cases

These are acceptance contracts for the headless API and its optional React client. Each scenario must demonstrate its terminal outcome, persisted records, permissions, side effects and failure behaviour using synthetic fixtures. Test-mode provider outcomes are not live financial or signature evidence.

## UC-01: New website RFQ

- Actor: Prospect
- Trigger: Submit a packaging request with company, contact, quantity and delivery date.
- Journey: Save an RFQ and provisional project; queue its acknowledgement; show a reference.
- Acceptance: RFQ, project and acknowledgement share one submission ID; UI confirms receipt.
- Implementation lane: customer

## UC-02: Retried RFQ submission

- Actor: Prospect
- Trigger: Submit the same RFQ again with the original idempotency key.
- Journey: Return the original response without creating another project or email.
- Acceptance: One RFQ, one project, one acknowledgement operation.
- Implementation lane: customer

## UC-03: Invalid or abusive RFQ

- Actor: Prospect
- Trigger: Submit missing contact data, invalid quantities or excessive repeated requests.
- Journey: Validate input and enforce public intake limits before any workflow side effect.
- Acceptance: Clear field errors or rate-limit response; no orphan records or mail.
- Implementation lane: customer

## UC-04: Existing customer enquiry

- Actor: Customer
- Trigger: Submit a new RFQ while signed into an invited company account.
- Journey: Link trusted membership to a new project without changing another company's contacts.
- Acceptance: New enquiry appears in that company's portal and owner's queue.
- Implementation lane: customer

## UC-05: RFQ triage

- Actor: Staff
- Trigger: Open an incoming RFQ and assign its owner, stage and next action.
- Journey: Update the project and audit the transition; retain original submitted requirements.
- Acceptance: Assigned project appears on the owner's work list with its next action.
- Implementation lane: foundation

## UC-06: RFQ acknowledgement recovery

- Actor: Staff
- Trigger: Mail provider fails after the RFQ is saved.
- Journey: Retry the durable outbox job with the original send key; expose delivery state.
- Acceptance: RFQ remains usable; one accepted send is recorded or actionable failure appears.
- Implementation lane: ai

## UC-07: Business card capture

- Actor: Staff
- Trigger: Upload a clear business-card photo from a phone.
- Journey: Register its document-service input; run multimodal extraction into nullable draft fields.
- Acceptance: Source preview and editable contact draft appear; no approved contact or welcome yet.
- Implementation lane: ai

## UC-08: Unclear card extraction

- Actor: Staff
- Trigger: Upload a blurry card or one with unreadable email text.
- Journey: Preserve unknowns; display source and review issues; permit correction or replacement.
- Acceptance: Uncertain values are not invented and welcome remains blocked.
- Implementation lane: ai

## UC-09: Verified new contact

- Actor: Staff
- Trigger: Correct the extracted card fields and confirm verification.
- Journey: Approve the contact and queue welcome in the same transaction.
- Acceptance: Approved contact appears in its organisation; welcome has one durable send ID.
- Implementation lane: ai

## UC-10: Repeated contact verification

- Actor: Staff
- Trigger: Double-click verification or retry its API request.
- Journey: Reuse the approval operation and its welcome event.
- Acceptance: One approved contact and one welcome operation.
- Implementation lane: ai

## UC-11: Possible duplicate contact

- Actor: Staff
- Trigger: Verify a card whose email matches an existing contact.
- Journey: Show the existing record and require explicit merge/update choice.
- Acceptance: No silent destructive merge; history and chosen source are preserved.
- Implementation lane: ai

## UC-12: Contact correction

- Actor: Staff
- Trigger: Change a verified contact's details.
- Journey: Save an audited revision without granting portal access or resending welcome implicitly.
- Acceptance: Updated contact appears everywhere authorised; membership remains independently controlled.
- Implementation lane: foundation

## UC-13: Customer specification form

- Actor: Owner
- Trigger: Command the app to send the specification form for a project.
- Journey: Resolve saved project and recipient; confirm; create a scoped link and queue email.
- Acceptance: One request links recipient, project and form version; delivery state is visible.
- Implementation lane: ai

## UC-14: Factory quotation form

- Actor: Owner
- Trigger: Request a quotation from a selected factory.
- Journey: Confirm recipient and customer-safe specifications; send a unique form.
- Acceptance: Factory receives only its permitted project fields, never competitors' quotes.
- Implementation lane: customer

## UC-15: Recipient email verification

- Actor: Recipient
- Trigger: Open a valid form link.
- Journey: Verify the invited mailbox; authorise only that form's project and allowed fields.
- Acceptance: Recipient can submit the form without receiving company-wide portal membership.
- Implementation lane: customer

## UC-16: Forwarded form link

- Actor: Other recipient
- Trigger: Open someone else's valid form link and verify a different email.
- Journey: Reject email/scope mismatch before loading private form data.
- Acceptance: No project disclosure or submission privilege.
- Implementation lane: customer

## UC-17: Expired or revoked request

- Actor: Recipient
- Trigger: Open an expired or owner-revoked form link.
- Journey: Reject access; let owner issue a replacement through the confirmed-send action.
- Acceptance: Old link cannot be used; replacement has its own request and audit entry.
- Implementation lane: customer

## UC-18: Specification response

- Actor: Customer
- Trigger: Submit the project specification form.
- Journey: Store an immutable response; validate fields; apply approved business updates.
- Acceptance: Owner sees response, provenance and updated specification; no unrelated fields change.
- Implementation lane: customer

## UC-19: Factory delivery confirmation

- Actor: Factory
- Trigger: Submit available shipping options and a confirmed delivery date.
- Journey: Save response and update that supplier's project delivery information.
- Acceptance: Project shows factory-specific dates and options, with response history.
- Implementation lane: customer

## UC-20: Multiple suppliers

- Actor: Staff
- Trigger: Add two factories and compare their quotations on a project.
- Journey: Maintain separate supplier links, quotations and POs.
- Acceptance: Owner can compare costs and dates without overwriting one supplier with another.
- Implementation lane: foundation

## UC-21: Project workspace

- Actor: Owner
- Trigger: Open an active project.
- Journey: Load linked customer, specifications, quotes, orders, invoices, payments, factories and shipping.
- Acceptance: One navigable screen links every record and shows next action and balance.
- Implementation lane: owner

## UC-22: Project activity and history

- Actor: Staff
- Trigger: Inspect the project after edits, sends and payment events.
- Journey: Page through audit events with actor, source and timestamp.
- Acceptance: History is complete, ordered and bounded; raw secrets never appear.
- Implementation lane: owner

## UC-23: Approved customer quote

- Actor: Owner
- Trigger: Prepare a quote from saved specifications and pricing.
- Journey: Calculate values deterministically; confirm terms; request its document through DMS.
- Acceptance: Approved quote and exact document snapshot/version are linked to the project.
- Implementation lane: foundation

## UC-24: Order from approved information

- Actor: Owner
- Trigger: Record customer acceptance and create an order.
- Journey: Create order from the approved quote/specification snapshot with audit.
- Acceptance: Order retains agreed values even when a later draft changes.
- Implementation lane: foundation

## UC-25: Factory purchase order

- Actor: Owner
- Trigger: Create a PO for one project supplier.
- Journey: Confirm quantities, prices and terms; call DMS using the saved snapshot.
- Acceptance: PO links factory, project, line items and immutable external document version.
- Implementation lane: integrations

## UC-26: Packing list

- Actor: Staff
- Trigger: Prepare a shipment's packing list.
- Journey: Select saved shipment/order items and send snapshot to DMS.
- Acceptance: Packing-list reference links to correct shipment and project; no rendering is duplicated here.
- Implementation lane: integrations

## UC-27: Customer invoice

- Actor: Owner
- Trigger: Issue an invoice using saved order lines and configured taxes.
- Journey: Compute decimal prices and tax; confirm; obtain accepted DMS version before live issue.
- Acceptance: Issued totals and document version are immutable and portal-visible.
- Implementation lane: integrations

## UC-28: Ledger statement

- Actor: Owner
- Trigger: Request a customer or factory statement for a date range.
- Journey: Build a bounded statement from receipts, allocations and adjustments; request DMS artifact.
- Acceptance: Statement reconciles to operational balances and preserves its snapshot.
- Implementation lane: integrations

## UC-29: Contract preparation

- Actor: Owner
- Trigger: Create a project contract using saved parties and approved terms.
- Journey: Confirm commitments and ask DMS for the configured template/version.
- Acceptance: Draft contract references its exact business snapshot; no generic contract engine is built.
- Implementation lane: integrations

## UC-30: Unavailable document service

- Actor: Owner
- Trigger: Request generation when DMS is unavailable or only test fixtures are configured.
- Journey: Persist pending/error state and show an actionable integration message.
- Acceptance: Production issuance/signing is blocked; fixture documents are visibly labelled.
- Implementation lane: integrations

## UC-31: Signature request

- Actor: Owner
- Trigger: Send an approved contract version for signature.
- Journey: Confirm signers; call DMS; track its request with version and project association.
- Acceptance: Signing invitation targets the correct parties and exact approved version.
- Implementation lane: integrations

## UC-32: Signed evidence completion

- Actor: Owner
- Trigger: DMS reports completion and makes signed artifact/evidence available.
- Journey: Authenticate the update; retrieve/archive references; verify project/version association.
- Acceptance: Signed status requires retrievable signed document and supporting evidence.
- Implementation lane: integrations

## UC-33: Replayed or forged signature update

- Actor: External caller
- Trigger: Replay a completion update or submit an invalid authenticated callback.
- Journey: Verify authentication, replay identity and document association.
- Acceptance: No duplicate completion or false signed status; rejection is audited.
- Implementation lane: integrations

## UC-34: Customer invitation

- Actor: Owner
- Trigger: Invite a contact to their customer organisation.
- Journey: Issue an owner-approved invitation; verify email; activate organisation membership.
- Acceptance: Customer can access only that organisation's portal records.
- Implementation lane: customer

## UC-35: Company portal overview

- Actor: Customer
- Trigger: Sign in with an active organisation membership.
- Journey: Load explicitly customer-safe RFQs, quotes, contacts, orders, history and invoices.
- Acceptance: No supplier costs, margins, internal factory details or other customers' data.
- Implementation lane: customer

## UC-36: Cross-company record request

- Actor: Customer
- Trigger: Request another company's project, invoice or document ID.
- Journey: Derive company scope from trusted membership and enforce it in API queries.
- Acceptance: Access denied even when a valid UUID or external document reference is known.
- Implementation lane: customer

## UC-37: Membership revocation

- Actor: Owner
- Trigger: Revoke a customer's organisation membership.
- Journey: Disable access immediately through backend membership checks.
- Acceptance: Previously signed-in user loses portal/document/payment-request access.
- Implementation lane: customer

## UC-38: Portal document access

- Actor: Customer
- Trigger: Download a customer-visible document.
- Journey: Authorise company and document visibility; retrieve access through DMS adapter.
- Acceptance: Only the approved external version is available; internal POs remain private.
- Implementation lane: customer

## UC-39: Owner-defined deposit schedule

- Actor: Owner
- Trigger: Define a deposit and later instalments for an issued CAD invoice.
- Journey: Validate amounts, round cents, set final remainder and approve payment requests.
- Acceptance: Requested totals do not exceed the invoice's collectible balance.
- Implementation lane: foundation

## UC-40: Deposit checkout

- Actor: Customer
- Trigger: Choose an approved outstanding deposit request.
- Journey: Calculate amount server-side; create/reuse its active Stripe Checkout attempt.
- Acceptance: Checkout amount, currency and invoice/request identity match authoritative records.
- Implementation lane: integrations

## UC-41: Confirmed online payment

- Actor: Customer
- Trigger: Finish Checkout and Stripe confirms payment.
- Journey: Verify and durably store webhook; create one receipt and allocation.
- Acceptance: Invoice and instalment balances update from the payment, not the return page.
- Implementation lane: integrations

## UC-42: Delayed or failed payment

- Actor: Customer
- Trigger: Return from Checkout before final success, or payment fails.
- Journey: Keep the request unpaid until a verified success event; show pending/failure state.
- Acceptance: Browser redirects and delayed events cannot falsely settle the invoice.
- Implementation lane: integrations

## UC-43: Duplicate/reordered payment events

- Actor: Stripe
- Trigger: Deliver the same event concurrently or send events out of order.
- Journey: Deduplicate events and payment identities; apply authoritative settlement transactionally.
- Acceptance: One receipt/allocation; stable balances regardless of delivery order.
- Implementation lane: integrations

## UC-44: Partial offline receipt

- Actor: Staff
- Trigger: Record an approved bank-transfer receipt against an invoice or instalment.
- Journey: Allocate the received amount and retain reference/evidence metadata.
- Acceptance: Remaining deposit/invoice balances are correct and portal-visible.
- Implementation lane: foundation

## UC-45: Concurrent/overpayment handling

- Actor: Customer and staff
- Trigger: An online payment completes while an offline receipt is recorded.
- Journey: Reconcile both actual receipts; cap invoice allocation and retain excess as customer credit.
- Acceptance: No lost funds or negative unpaid balance; owner sees unallocated credit.
- Implementation lane: foundation

## UC-46: Refund or dispute

- Actor: Stripe and owner
- Trigger: A settled payment is refunded, disputed or restored.
- Journey: Apply audited receipt adjustments and reconciliation events.
- Acceptance: Operational balances reflect confirmed outcomes without deleting payment history.
- Implementation lane: integrations

## UC-47: AI command versus button

- Actor: Owner
- Trigger: Perform the same confirmed action through AI and through its UI button.
- Journey: Use the same typed action service, permission checks and idempotency contract.
- Acceptance: Equivalent business results; AI cannot bypass confirmations or authorisation.
- Implementation lane: ai

## UC-48: Job crash and provider ambiguity

- Actor: System
- Trigger: Crash after database commit, task dispatch or provider acceptance.
- Journey: Recover dispatch, lease work, reconcile provider outcome and bound retries.
- Acceptance: No stranded workflow; ambiguous aged sends require reconciliation instead of blind resend.
- Implementation lane: foundation

## UC-49: Headless client operation

- Actor: API client
- Trigger: Complete RFQ → project → approved commercial records → payment without React.
- Journey: Use authenticated documented APIs and stable idempotency keys.
- Acceptance: Workflow is fully usable via HTTP; UI is optional and no hidden browser-only rules exist.
- Implementation lane: foundation

## UC-50: Portable export and release

- Actor: Owner and coordinator
- Trigger: Export representative records and deploy a reviewed revision.
- Journey: Reconcile counts, IDs, document references and balances; deploy matching API/frontend SHA.
- Acceptance: Export is auditable, revisions match, rollback exists and fixture/live provider modes are explicit.
- Implementation lane: integrations

