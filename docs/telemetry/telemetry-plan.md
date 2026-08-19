# TrackFlow Telemetry Plan

## Overview

This document defines the telemetry strategy for TrackFlow's inventory management system. The objective is to capture meaningful operational events that support business decisions while respecting security, privacy, and system constraints.

The telemetry plan focuses on TrackFlow's inventory entities:

- SKU
- ReceivingOrder
- DispatchOrder

---

# Phase 1 – KPI Analysis

## KPI 1 – Order Fulfilment Rate

### Definition

Percentage of DispatchOrders successfully completed versus those rejected because of insufficient stock.

### Data Required

- Successful DispatchOrders
- Failed DispatchOrders
- Warehouse
- SKU
- Timestamp
- Client ID

### Data Sources

- DispatchOrder creation endpoint
- DispatchOrder validation layer

### Business Decision

Identify products or warehouses suffering repeated stock shortages and proactively replenish inventory.

---

## KPI 2 – Stock Discrepancy Frequency

### Definition

Number of rejected attempts to modify stock directly.

### Data Required

- Rejected direct stock edits
- Warehouse
- User
- SKU
- Timestamp

### Data Sources

Inventory API validation layer.

### Business Decision

Identify warehouses where operators repeatedly attempt prohibited manual edits and trigger operational audits.

---

## KPI 3 – Receiving-to-Dispatch Cycle Time

### Definition

Average time between a ReceivingOrder and the first DispatchOrder consuming inventory from that SKU.

### Data Required

- ReceivingOrder timestamp
- First DispatchOrder timestamp
- Warehouse
- SKU

### Data Sources

ReceivingOrder creation

DispatchOrder creation

### Business Decision

Measure warehouse processing efficiency and detect bottlenecks.

---

# Inventory Flow

1. User authenticates.
2. User selects warehouse.
3. User opens SKU inventory.
4. User creates ReceivingOrder.
5. Stock increases.
6. User creates DispatchOrder.
7. Stock validation occurs.
8. Order succeeds or fails.
9. Stock threshold check executes.
10. API blocks any direct stock modification.

---

# Instrumentation Points

| Event | Hypothesis | Business Decision |
|--------|------------|------------------|
| receiving_order_created | Receiving activity predicts future dispatch capacity | Forecast inventory availability |
| dispatch_order_created | Successful shipments measure fulfilment | Measure warehouse performance |
| dispatch_order_failed | Stock shortages reduce fulfilment | Trigger replenishment |
| stock_threshold_triggered | Low inventory predicts future shortages | Reorder inventory |
| direct_stock_edit_rejected | Users attempt manual workarounds | Audit warehouse processes |
| user_login_failed | Authentication failures may indicate operational issues | Investigate security or training |
| dispatch_form_abandoned | Users abandon dispatch workflow | Improve UX or process |

---

# Golden Rule Justification

We capture **receiving_order_created**
because we need to know incoming inventory trends,
which allows us to forecast future stock.

We capture **dispatch_order_created**
because we need to know successful fulfilment,
which allows us to calculate fulfilment rate.

We capture **dispatch_order_failed**
because we need to know stock shortages,
which allows us to prioritize replenishment.

We capture **stock_threshold_triggered**
because we need to know when inventory becomes critical,
which allows us to reorder before stockouts occur.

We capture **direct_stock_edit_rejected**
because we need to know whether operators bypass business rules,
which allows us to audit warehouse procedures.

We capture **user_login_failed**
because we need to know authentication issues,
which allows us to improve security.

We capture **dispatch_form_abandoned**
because we need to know where users leave workflows,
which allows us to improve usability.

---

# Standard Event Envelope

Every event contains:

| Field | Description |
|-------|-------------|
| eventId | UUID |
| timestamp | ISO-8601 |
| sessionId | Session identifier |
| userId | TinyDB UUID |
| event_type | entity_action |
| schemaVersion | Schema version |
| requestId | Request correlation ID |
| properties | Event payload |

---

# Stream vs Batch

| Event | Processing | Justification |
|---------|-----------|--------------|
| receiving_order_created | Batch | Used for reporting and warehouse trends. |
| dispatch_order_created | Stream | Required for real-time fulfilment dashboards. |
| dispatch_order_failed | Stream | Immediate action required for SLA-sensitive US deliveries. |
| stock_threshold_triggered | Stream | Immediate replenishment decisions. |
| direct_stock_edit_rejected | Batch | Operational audits can be periodic. |
| user_login_failed | Stream | Security events require fast visibility. |
| dispatch_form_abandoned | Batch | UX analytics are not urgent. |

---

# Throttle Strategy

No throttling is required for inventory events.

Navigation events such as warehouse_filter_applied may be aggregated every 60 seconds before transmission.

---

# Privacy

- created_by stored only as TinyDB UUID
- client_id stored only as opaque identifier
- No emails
- No names
- No phone numbers
- No addresses

---

# Risks & Exclusions

Excluded events

- Every SKU list refresh
- Mouse clicks
- Keyboard input
- Search keystrokes

Reason

These produce high telemetry volume without supporting business decisions.

---

# Dual Warehouse Support

Every warehouse event includes

- warehouse

Allowed values

- los_angeles
- zaragoza

---

# Client Isolation

client_id always uses opaque identifiers.

Brand names are never emitted.

---

# Quality Checklist

✅ Supports all three TrackFlow KPIs

✅ Uses SKU, ReceivingOrder and DispatchOrder

✅ Uses entity_action naming

✅ Contains property allowlists

✅ Separates stream and batch processing

✅ Documents risks and exclusions

✅ Prevents PII leakage