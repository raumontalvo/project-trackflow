# TrackFlow — AI Engineering Company Project

TrackFlow is an AI Engineering company project built as part of the 4Geeks Academy AI Engineering Career Program.

This repository contains the TrackFlow application stack, including backend services, inventory management, RAG knowledge retrieval, LangGraph support-agent workflows, and an OAuth-protected MCP server for reusable company tools.

---

## Project Structure

```text
project-3/
├── agents/
├── apps/
├── data/
├── docs/
├── mcps/
│   └── trackflow/
│       ├── __init__.py
│       ├── client.py
│       ├── config.py
│       └── server.py
├── packages/
├── scripts/
│   └── setup_mcp_auth.sh
├── services/
│   ├── agent/
│   └── api/
├── shared/
├── skills/
├── tests/
├── uis/
├── workflows/
├── docker-compose.yml
├── pyproject.toml
└── README.md
```

---

## TrackFlow MCP Server

TrackFlow exposes company operational tools through an independent MCP server located in:

```text
mcps/trackflow/
```

The MCP server allows authorized MCP clients to interact with the existing TrackFlow Incidents Manager and query inventory data without coupling clients directly to the backend implementation.

---

## Transport

The MCP server uses **Streamable HTTP**.

Streamable HTTP was selected instead of stdio because the server is intended to be reusable by multiple clients, including remote agents and external MCP-compatible applications.

A stdio transport would be appropriate for a single local client process, while Streamable HTTP provides a reusable network service that can be protected with OAuth.

The default MCP endpoint is:

```text
http://localhost:8001/mcp
```

---

## OAuth and Authentication

The MCP server is protected using **OAuth/OIDC**.

The implementation uses:

- **MCP Auth** for bearer JWT validation and MCP authentication integration.
- **Keycloak** as the local OAuth/OIDC authorization server.
- OAuth scopes for least-privilege authorization.

The local Keycloak authorization server runs through Docker Compose.

The TrackFlow issuer is:

```text
http://localhost:9000/realms/trackflow
```

The MCP resource audience is:

```text
http://localhost:8001
```

Unauthenticated requests to the MCP endpoint are rejected with `401 Unauthorized`.

---

## OAuth Scopes

TrackFlow uses three MCP authorization scopes:

```text
incidents:read
incidents:write
inventory:read
```

### `incidents:read`

Allows clients to:

- Get an incident.
- List incidents.
- Query incident summaries.

### `incidents:write`

Allows clients to:

- Create incidents.
- Change incident status.

### `inventory:read`

Allows clients to:

- List inventory products.
- Get an inventory product.
- Read inventory movement history.

Inventory write access is intentionally not granted.

---

## Read-Only Inventory

Inventory access through MCP is **read-only by design**.

The underlying TrackFlow backend contains inventory write operations, but MCP clients are not permitted to use them.

Attempts to perform inventory mutations are explicitly rejected by the MCP server.

This prevents MCP clients from:

- Creating inventory products.
- Creating inbound orders.
- Creating outbound orders.
- Updating inventory.
- Deleting inventory.

This enforces the principle of least privilege at the MCP service boundary.

---

## Incident Lifecycle

Incident status changes use the existing TrackFlow Incidents Manager lifecycle endpoint:

```text
PATCH /api/incidents/{id}/status
```

The MCP server does not perform a generic PATCH against an incident resource.

This preserves the existing TrackFlow lifecycle validation and prevents invalid status transitions.

For example, an invalid transition such as:

```text
in_progress -> open
```

is rejected by the existing Incidents Manager validation logic.

---

## MCP Tool Discovery

External MCP clients can discover the server's tools, descriptions, and input schemas without requiring additional human context.

The server exposes the following tools:

```text
get_incident
list_incidents
get_incident_summary
create_incident
update_incident_status
list_inventory_products
get_inventory_product
list_inventory_movements
inventory_write_attempt
```

Tool descriptions explain whether an operation is read-only or modifies data and identify the OAuth permission required to use it.

---

## LangGraph Agent Migration

The TrackFlow support agent previously called the Incidents Manager directly.

That direct integration has been removed.

The agent now consumes incident functionality through the MCP server using:

```text
langchain-mcp-adapters
```

The ticket workflow is now:

```text
User
  ↓
TrackFlow Agent API
  ↓
LangGraph
  ↓
ticket_lookup_node
  ↓
langchain-mcp-adapters
  ↓
OAuth-protected TrackFlow MCP Server
  ↓
Incidents Manager
```

The agent obtains a least-privilege OAuth token with:

```text
incidents:read
```

before connecting to the MCP server.

The agent no longer contains a direct `/api/incidents` HTTP call.

---

## Existing RAG Routing

The MCP migration preserves the existing LangGraph routing.

The agent supports three paths:

### RAG-only

```text
Question
  ↓
LangGraph
  ↓
Knowledge retrieval
  ↓
RAG answer
```

### Ticket-only

```text
Ticket question
  ↓
LangGraph
  ↓
MCP
  ↓
Incidents Manager
```

### Combined Ticket + RAG

```text
Combined question
  ↓
MCP incident lookup
  ↓
Knowledge retrieval
  ↓
Combined answer
```

The existing RAG functionality remains intact after the MCP migration.

---

## Local OAuth Setup

Start Keycloak:

```bash
docker compose up -d keycloak
```

Configure the TrackFlow realm, OAuth client, scopes, and MCP audience:

```bash
./scripts/setup_mcp_auth.sh
```

The setup script creates or configures:

- `trackflow` Keycloak realm.
- `trackflow-mcp-client` OAuth client.
- `incidents:read` scope.
- `incidents:write` scope.
- `inventory:read` scope.
- MCP resource audience.

The script is designed to be safe to run more than once.

For security, the OAuth client secret is intentionally **not printed** by the setup script.

Retrieve the client secret locally with Keycloak and store it only in your ignored `.env` file.

---

## MCP Environment Configuration

Example local configuration:

```text
TRACKFLOW_API_BASE_URL=http://localhost:8000

MCP_HOST=0.0.0.0
MCP_PORT=8001
MCP_RESOURCE_URL=http://localhost:8001

MCP_AUTH_ISSUER=http://localhost:9000/realms/trackflow

MCP_SERVER_URL=http://localhost:8001/mcp

MCP_OAUTH_TOKEN_URL=http://localhost:9000/realms/trackflow/protocol/openid-connect/token
MCP_OAUTH_CLIENT_ID=trackflow-mcp-client
MCP_OAUTH_CLIENT_SECRET=<your-local-secret>
```

Secrets must remain in `.env`.

The `.env` file is ignored by Git and must not be committed.

---

## Running TrackFlow Locally

### 1. Start Keycloak

```bash
docker compose up -d keycloak
```

### 2. Configure OAuth

```bash
./scripts/setup_mcp_auth.sh
```

### 3. Start the TrackFlow API

```bash
uv run uvicorn services.api.main:app --host 0.0.0.0 --port 8000
```

The API is available at:

```text
http://localhost:8000
```

### 4. Start the MCP Server

```bash
uv run uvicorn mcps.trackflow.server:app --host 0.0.0.0 --port 8001
```

The MCP endpoint is available at:

```text
http://localhost:8001/mcp
```

---

## Security Validation

The MCP implementation has been validated for the following behaviors:

| Test | Expected behavior |
|---|---|
| MCP request without token | `401 Unauthorized` |
| Valid OAuth token | MCP initialization succeeds |
| MCP discovery | Tools and schemas are returned |
| `incidents:read` | Incident reads allowed |
| `incidents:read` calling incident write | Rejected |
| `incidents:write` | Incident creation allowed |
| Valid incident status transition | Allowed |
| Invalid incident status transition | Rejected |
| `inventory:read` | Inventory reads allowed |
| Inventory mutation attempt | Explicitly rejected |
| LangGraph ticket question | Uses MCP |
| RAG-only question | Existing RAG route works |
| Combined ticket + RAG question | Both sources work |

---

## Automated Tests

The project includes automated tests covering the LangGraph workflow and MCP integration.

Run the complete test suite:

```bash
uv run pytest -q
```

Current validated result:

```text
25 passed
```

The MCP-specific tests verify:

- MCP tool discovery.
- Explicit inventory write rejection.
- The agent no longer contains a direct Incidents Manager API call.

---

## Key MCP Dependencies

The project uses:

```text
fastmcp
mcpauth
langchain-mcp-adapters
pytest-asyncio
```

Dependencies are managed with `uv`.

Install dependencies using:

```bash
uv sync
```

Do not use `pip install` directly for this monorepo.

---

## Milestones

| Milestone | Focus |
|---|---|
| 0 | Prework |
| 1 | Web |
| 2 | Programming |
| 3 | AI-driven UI |
| 4 | Next.js |
| 5 | Backend |
| 6 | Telemetry |
| 7 | RAG & Knowledge Base |
| 8 | Agents |
| Current | MCP Server & External Tools |

---

## 4Geeks Academy

This project is part of the 4Geeks Academy AI Engineering Career Program.

The repository builds progressively on the TrackFlow company project, including backend services, inventory management, RAG, LangGraph agents, and MCP-based external tool integration.