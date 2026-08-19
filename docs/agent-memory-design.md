# TrackFlow Agent Memory — Design and Evidence

## Overview

This milestone extends the existing TrackFlow LangGraph support agent with persistent, user-authorized memory. It keeps the same agent that already uses RAG and MCP tools.

The memory flow is:

resolve pending proposal -> validate request -> recall approved memory -> normal RAG/MCP flow -> generate answer -> self-evaluate for memory

Memory is fail-closed. Nothing is persisted unless the proposal is allowed by TrackFlow policy and the user's decision is explicitly classified as approval or a valid edit.

## Memory Architecture

TrackFlow uses a structured persistent memory store.

Stored records contain:

- memory type
- content
- country
- carrier
- B2B client
- source proposal ID
- timestamps
- expiration
- active status

The allowed memory categories are:

1. corrected carrier assignment or coverage rules
2. recurring incident context
3. recurring B2B monthly-report preferences

### Why not use the existing VectorDB?

The RAG VectorDB is appropriate for the larger company knowledge base, but memory requires deterministic authorization, auditing, consolidation, expiration, correction, and deletion.

The amount of persistent memory is also small and structured.

### Why not use a knowledge graph?

This milestone does not require relationship traversal or graph reasoning. Carrier rules, recurring incident explanations, and B2B preferences can be represented directly with structured fields.

### Why not use fine-tuning?

Fine-tuning would make selective forgetting, authorization, correction, and auditing difficult. Persistent application memory can be changed without retraining the model.

## TrackFlow Memory Policy

### Worth remembering

- corrected carrier assignment or coverage rules
- context from known recurring incidents
- recurring B2B client monthly-report preferences

### Must never enter memory

- exact B2C end-customer addresses
- sensitive B2B location information
- internal warehouse routes or physical-security information
- isolated single-package incidents
- active commercial contract-negotiation information

The sensitive-location restriction explicitly applies to both B2B and B2C contexts.

User approval does not override these restrictions.

## Self-Evaluation

The existing agent generates the user-visible answer and memory self-evaluation together in one structured model call.

That structured output contains:

- whether memory should be proposed
- memory type
- proposed content
- country
- carrier
- B2B client
- reason

Malformed output fails closed and creates no proposal.

A proposed memory is then checked by deterministic TrackFlow memory policy.

If allowed, one proposal becomes pending for the conversation and the agent asks the user whether it should be remembered.

The proposal is also written immediately to the audit log with a PENDING outcome, including its originating message and timestamp.

A pending proposal is not persistent memory.

## Examples That Should Generate a Proposal

1. "Actually SEUR no longer covers that rural area of Zaragoza, we've had to use the local carrier since last month."
2. "Those delays reported in Los Angeles incidents this week are from the port strike, not something on our end — that's the third ticket about it already."
3. "The cosmetics client always wants their monthly report with the returns breakdown first, before shipment volume."

## Examples That Should Not Generate a Proposal

1. "Where's the package with tracking XJ4471?"
2. "Great, that's resolved."
3. "Translate this into English for the client."

## User Confirmation

Only one proposal may be pending per conversation.

The user's next response is explicitly classified as:

- APPROVE
- REJECT
- EDIT
- AMBIGUOUS
- UNRELATED

The implementation does not use simple keyword logic such as checking whether "yes" appears in the message.

The classifier returns a confidence score.

A confidence below 0.80 becomes AMBIGUOUS.

Malformed classifier output also becomes AMBIGUOUS.

Approval is never assumed from silence, vague language, or topic changes.

### APPROVE

The proposal is persisted and an APPROVED audit record is created.

### REJECT

The proposal is discarded and no persistent memory is written. A REJECTED audit record remains.

### EDIT

The corrected content is validated against TrackFlow policy again before persistence.

If allowed, the corrected version is stored.

If forbidden, the edit is blocked.

### AMBIGUOUS

The proposal is discarded by default and nothing is stored.

### UNRELATED

The proposal is discarded and audited, then the user's new request continues through the normal agent workflow.

If the user approves, rejects, or edits the proposal and also asks a separate question in the same message, the decision is resolved first and the follow-up question continues through the normal agent workflow in the same turn.

## Audit Log

Audit records contain:

- proposal ID
- conversation ID
- proposed memory
- originating message
- outcome
- user decision
- final saved memory when applicable
- proposal timestamp
- resolution timestamp

This provides a trace of what was proposed, what the user decided, and what was ultimately persisted.

## Recall

Only approved persistent records can be recalled.

Relevant active memory is retrieved before normal RAG/MCP routing and added to the generation context.

Pending, rejected, blocked, and discarded proposals cannot be recalled.

## Consolidation and Cleanup

Memory is not an unlimited append-only log.

### Carrier Rules

Carrier rules are consolidated by:

country + carrier

A newer approved correction replaces the older record in that scope.

### B2B Report Preferences

B2B report preferences are consolidated by client.

A newer approved preference replaces the previous preference for that client.

### Recurring Incidents

Recurring incident memories expire after 14 days.

Cleanup marks expired memories inactive, and inactive or expired records are excluded from recall.

## Pending Proposal Cleanup

A pending proposal never becomes approved because the user fails to answer.

An ambiguous response discards the proposal.

An unrelated next message also discards the proposal before normal processing continues.

## Memory Poisoning Protection

The implementation reduces memory poisoning risk through multiple controls:

1. proposals are limited to TrackFlow's approved memory categories
2. deterministic policy validation runs after LLM evaluation
3. sensitive locations, warehouse routes, contract negotiations, and one-off incidents are blocked
4. explicit user confirmation is required
5. edited content is validated again
6. malformed or low-confidence decisions fail closed
7. only approved persistent records participate in recall

Operational claims use an explicit trust hierarchy:

1. live MCP incident data is authoritative for current incident facts;
2. approved RAG knowledge-base context is authoritative for company policy;
3. approved TrackFlow memory is advisory context only.

If recalled memory conflicts with trusted MCP or RAG information, the conflicting memory is ignored. This prevents a malicious or mistaken approved memory from overriding authoritative operational data.

## Why Multi-Agent Architecture Is Not Required

This remains the same TrackFlow support agent.

Memory is implemented as additional single-responsibility LangGraph nodes:

resolve_pending_memory -> validate_question -> recall_memory -> normal RAG/MCP flow -> memory_evaluation

A second autonomous agent is unnecessary because the existing graph already provides explicit state, routing, tracing, and independently testable nodes.

## Evidence Cycle 1 — Approved and Recalled

Initial correction:

"Actually SEUR no longer covers rural Zaragoza."

The evaluator creates a carrier-rule proposal and holds it as pending.

User:

"Yes, remember that."

The classifier returns APPROVE. The memory is persisted and an APPROVED audit record is written.

Later:

"Does SEUR still cover rural Zaragoza?"

The approved memory is recalled:

"SEUR no longer covers rural Zaragoza."

Automated evidence:

test_full_approved_memory_cycle_recall

## Evidence Cycle 2 — Rejected and Not Recalled

The same carrier correction becomes a pending proposal.

User:

"No, do not remember that."

The classifier returns REJECT. No persistent memory is created and a REJECTED audit record remains.

Later:

"Does SEUR still cover rural Zaragoza?"

The rejected proposal cannot be recalled.

Automated evidence:

test_full_rejected_memory_cycle_not_recalled

## Automated Verification

Full repository test result:

56 passed
