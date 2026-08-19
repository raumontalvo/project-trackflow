# Backend Architecture Proposal — TrackFlow

## 1. Introduction

TrackFlow is a last-mile delivery and warehouse management company operating in the United States and Spain. The company serves e-commerce brands by managing inventory storage, order fulfillment, carrier coordination, delivery tracking, and returns.

The current technical situation is fragmented: the two warehouses use different systems, carrier management is mostly manual, returns are reviewed case by case, customer support depends heavily on human agents, and executive reporting is assembled manually.

The purpose of this backend architecture proposal is to define how TrackFlow should organize its future FastAPI backend before implementation begins.

---

## 2. Chosen Architectural Pattern

The recommended pattern is a **layered, domain-oriented modular monolith** using FastAPI.

This means the backend should be one deployable application, but internally organized by clear business domains such as inventory, warehouse operations, carriers, returns, customer experience, CRM, reporting, and telemetry.

This is a better fit than a generic MVC structure because TrackFlow's system is not just a website backend. It is an operational logistics platform with many business areas that need shared data and consistent rules.

This is also a better fit than microservices at this stage because TrackFlow's engineering team is small, the backend is just beginning, and many domains still depend on shared operational data. A modular monolith keeps deployment and maintenance simpler while still creating clean boundaries that could later become separate services if needed.

---

## 3. Why This Pattern Fits TrackFlow

TrackFlow has several real business characteristics that influence the architecture:

- It operates across two countries.
- It manages two warehouses with different systems.
- It works with multiple carriers.
- It needs centralized inventory visibility.
- It handles returns, customer support, reporting, and commercial workflows.
- It already has multiple frontend applications in the monorepo.
- It needs future support for telemetry, RAG, agents, workflows, and real-time dashboards.

A layered modular monolith supports these needs because it separates API routing, business logic, data access, integrations, and shared configuration.

The architecture should prioritize clarity, maintainability, and domain separation before adding distributed-system complexity.

---

## 4. Proposed Monorepo Placement

The backend should live inside the existing monorepo as another application.

```text
apps/
└── backend/
    └── app/
````

The existing repository already contains multiple UI applications. The backend should not be mixed into those frontends. It should be an independent FastAPI service consumed through HTTP APIs.

A high-level monorepo structure would be:

```text
project-3/
├── apps/
│   └── backend/
├── uis/
│   ├── website/
│   ├── backoffice/
│   └── talent-pipeline-tracker/
├── packages/
│   └── shared/
├── docs/
│   └── ARCHITECTURE_PROPOSAL.md
└── memory-bank/
```

---

## 5. Proposed Backend Folder Structure

```text
apps/backend/
├── app/
│   ├── main.py
│   ├── api/
│   │   └── v1/
│   │       ├── routers/
│   │       │   ├── auth.py
│   │       │   ├── inventory.py
│   │       │   ├── warehouse.py
│   │       │   ├── carriers.py
│   │       │   ├── returns.py
│   │       │   ├── customers.py
│   │       │   ├── crm.py
│   │       │   ├── reporting.py
│   │       │   └── telemetry.py
│   │       └── api.py
│   ├── core/
│   │   ├── config.py
│   │   ├── security.py
│   │   ├── logging.py
│   │   └── dependencies.py
│   ├── domains/
│   │   ├── auth/
│   │   ├── inventory/
│   │   ├── warehouse/
│   │   ├── carriers/
│   │   ├── returns/
│   │   ├── customers/
│   │   ├── crm/
│   │   ├── reporting/
│   │   └── telemetry/
│   ├── integrations/
│   │   ├── warehouse_la/
│   │   ├── warehouse_zaragoza/
│   │   ├── legacy_erp/
│   │   ├── ups/
│   │   ├── fedex/
│   │   ├── dhl/
│   │   ├── mrw/
│   │   └── seur/
│   ├── database/
│   │   ├── models/
│   │   ├── repositories/
│   │   └── migrations/
│   └── tests/
└── requirements.txt
```

---

## 6. Layer Responsibilities

### API Layer

The API layer contains FastAPI routers and request/response handling.

Routers should remain thin. They should validate requests, call the correct service, and return responses. Business rules should not live directly inside route functions.

### Domain Layer

The domain layer contains business logic grouped by TrackFlow responsibility.

Each domain owns its own rules, services, and validation logic.

### Repository Layer

The repository layer manages database access.

This prevents SQL or database-specific logic from spreading across API routes and services.

### Integration Layer

The integration layer isolates communication with external systems, including warehouse systems, carrier APIs, and the legacy ERP.

This is especially important for TrackFlow because many current problems come from fragile and undocumented integrations.

### Core Layer

The core layer contains shared application configuration, security utilities, dependency injection, logging, and environment handling.

---

## 7. Domain Separation

### Auth Domain

Responsible for authentication, authorization, and user roles.

Suggested roles:

```text
admin
warehouse_manager
warehouse_operator
carrier_manager
customer_service
commercial
executive
```

This is necessary because TrackFlow has multiple departments with different access needs.

### Inventory Domain

Responsible for:

* SKU lookup
* Stock visibility
* Inventory by warehouse
* Low-stock alerts
* Synchronization with warehouse systems

### Warehouse Domain

Responsible for:

* Order ingestion
* Picking workflows
* Packing workflows
* Warehouse task tracking
* Operational status updates

### Carrier Domain

Responsible for:

* Carrier list
* Carrier assignment
* Unified tracking
* Delivery status updates
* Carrier performance metrics

### Returns Domain

Responsible for:

* Return requests
* Approval workflows
* Return labels
* Inspection status
* Return reason analysis

### Customer Experience Domain

Responsible for:

* Customer support tickets
* Tracking-related questions
* Return status questions
* Customer interaction history

### CRM Domain

Responsible for:

* Client profiles
* Account management
* Renewal risk data
* Commercial reporting

### Reporting Domain

Responsible for:

* Dashboard metrics
* Executive KPIs
* Weekly reports
* Country comparison views

### Telemetry Domain

Responsible for:

* Health checks
* Structured logs
* Integration failure tracking
* Operational alerts

Telemetry should be included early because TrackFlow currently discovers technical failures too late.

---

## 8. FastAPI Router Organization

FastAPI endpoints should be grouped by domain using `APIRouter`.

The API should be versioned under:

```text
/api/v1
```

Proposed routes:

```text
/api/v1/auth
/api/v1/inventory
/api/v1/warehouse
/api/v1/orders
/api/v1/carriers
/api/v1/tracking
/api/v1/returns
/api/v1/customers
/api/v1/tickets
/api/v1/crm
/api/v1/reports
/api/v1/dashboard
/api/v1/telemetry
```

### Inventory Routes

```text
GET /api/v1/inventory
GET /api/v1/inventory/{sku}
GET /api/v1/inventory/warehouse/{warehouse_id}
```

These routes support stock visibility across Los Angeles and Zaragoza.

### Warehouse Routes

```text
GET /api/v1/orders
POST /api/v1/orders
GET /api/v1/orders/{order_id}
GET /api/v1/warehouse/tasks
```

These routes support order processing and warehouse operations.

### Carrier Routes

```text
GET /api/v1/carriers
POST /api/v1/carriers/recommend
GET /api/v1/tracking/{tracking_number}
```

These routes support carrier selection and unified tracking.

### Returns Routes

```text
GET /api/v1/returns
POST /api/v1/returns
GET /api/v1/returns/{return_id}
POST /api/v1/returns/{return_id}/approval
```

These routes support reverse logistics and future automation.

### Customer Experience Routes

```text
GET /api/v1/tickets
POST /api/v1/tickets
GET /api/v1/customers/{customer_id}
```

These routes support support agents and future AI customer service tools.

### Reporting Routes

```text
GET /api/v1/dashboard
GET /api/v1/reports/weekly
GET /api/v1/reports/executive
```

These routes support operational dashboards and executive reporting.

### Telemetry Routes

```text
GET /api/v1/telemetry/health
GET /api/v1/telemetry/integrations
GET /api/v1/telemetry/incidents
```

These routes support monitoring and technical visibility.

---

## 9. FastAPI Conventions That Influence the Design

The proposed structure follows common FastAPI project conventions:

* Use `main.py` as the application entry point.
* Use `APIRouter` to separate routes by responsibility.
* Use a `core/` folder for configuration, security, logging, and dependencies.
* Keep Pydantic schemas separate from business logic.
* Keep routers thin and move business rules into services.
* Use dependency injection for shared dependencies.
* Group endpoints by domain instead of placing all routes in one file.
* Use environment variables for configuration.
* Use versioned API prefixes such as `/api/v1`.

These conventions make the backend easier to understand, test, and extend.

---

## 10. Frontend and Backend Separation

TrackFlow already has separate frontend applications, including a public website, a backoffice, and another application-style UI.

The backend should be a separate FastAPI service consumed by these frontends over HTTP.

A simple interaction model:

```text
User
  ↓
Next.js Frontend
  ↓
FastAPI Backend
  ↓
Domain Services
  ↓
Database / External Integrations
```

The frontend should not directly access the database, carrier systems, warehouse systems, or ERP. All operational logic should pass through the backend API.

---

## 11. API Communication

Frontend applications should communicate with the backend using REST endpoints.

The base API URL should be configured through environment variables.

Example:

```text
NEXT_PUBLIC_API_URL=https://api.trackflow.com/api/v1
```

This allows local, staging, and production environments to use different backend URLs without changing application code.

---

## 12. CORS Considerations

Because the frontend and backend may run on different domains, the backend must configure CORS carefully.

Possible frontend origins:

```text
https://trackflow.com
https://backoffice.trackflow.com
https://talent.trackflow.com
```

The backend should only allow approved origins.

CORS should not be set to allow every origin in production because TrackFlow will handle operational and client data.

---

## 13. Environment Variables

The backend should use environment variables for configuration and secrets.

Examples:

```text
DATABASE_URL
JWT_SECRET
ENVIRONMENT
ALLOWED_ORIGINS
UPS_API_KEY
FEDEX_API_KEY
DHL_API_KEY
MRW_API_KEY
SEUR_API_KEY
LEGACY_ERP_URL
WAREHOUSE_LA_API_URL
WAREHOUSE_ZARAGOZA_API_URL
```

Secrets must not be hardcoded in source files.

---

## 14. Database Strategy

PostgreSQL is recommended as the primary database because TrackFlow's core data is relational.

Examples of relational data:

* Clients
* Warehouses
* SKUs
* Orders
* Shipments
* Returns
* Carriers
* Tickets
* Reports
* Users and roles

A relational database supports consistency and structured reporting, both of which are important for TrackFlow's operational dashboards and executive views.

---

## 15. Shared Types and Business Logic

The monorepo should avoid duplicating business logic or shared definitions.

Shared types and constants should live in a shared package when they are needed by multiple applications.

Example:

```text
packages/shared/
├── types/
├── schemas/
└── constants/
```

Possible shared definitions:

```text
ShipmentStatus
ReturnStatus
InventoryItem
Carrier
Warehouse
Client
TicketStatus
UserRole
```

This prevents the website, backoffice, and backend from defining conflicting versions of the same business concepts.

---

## 16. Example Request Flow

Example: a customer checks shipment tracking.

```text
Customer opens tracking page
        ↓
Frontend calls /api/v1/tracking/{tracking_number}
        ↓
Carrier router receives request
        ↓
Carrier service validates tracking number
        ↓
Integration layer checks the correct carrier
        ↓
Tracking result is normalized
        ↓
Response is returned to frontend
```

This flow keeps carrier-specific logic out of the frontend and centralizes it in the backend.

---

## 17. MVP Implementation Phases

### Phase 1: Core Backend Foundation

* Authentication
* Inventory API
* Orders API
* Carrier tracking API
* Basic reporting
* Health checks

### Phase 2: Operational Expansion

* Returns workflows
* Ticketing
* CRM/client profiles
* Carrier performance metrics
* Low-stock alerts

### Phase 3: AI and Automation Readiness

* RAG knowledge base support
* Customer service agent integration
* Carrier recommendation engine
* Automated weekly executive reports
* Real-time telemetry and alerts

This phased approach avoids overbuilding while keeping the architecture ready for future milestones.

---

## 18. Risks and Points of Attention

### Risk 1: Business Logic Inside Routers

If business rules are written directly inside FastAPI routes, the backend will become difficult to test and maintain.

Mitigation:

* Keep routers thin.
* Move business rules into domain services.
* Use repositories for database access.

### Risk 2: Weak Domain Boundaries

Inventory, warehouse, carrier, and returns data are related. If boundaries are not clear, developers may duplicate logic or modify the wrong module.

Mitigation:

* Define domain ownership clearly.
* Group files by business responsibility.
* Document each domain's purpose.

### Risk 3: Integration Logic Mixed With Business Logic

TrackFlow depends on carrier APIs, warehouse systems, and a legacy ERP. If integration code is mixed into domain logic, vendor changes will become expensive and risky.

Mitigation:

* Keep all external system communication inside `integrations/`.
* Normalize external responses before they reach domain services.

### Risk 4: Premature Microservices

Microservices could make the system harder to deploy, test, and monitor before the team has enough scale to justify them.

Mitigation:

* Start with a modular monolith.
* Split domains into services later only if real scaling or team-ownership needs appear.

### Risk 5: Poor Environment and CORS Management

If environment variables and CORS are not handled carefully, frontend applications may break across environments or expose the API to unauthorized origins.

Mitigation:

* Use environment-specific configuration.
* Restrict CORS to approved frontend domains.
* Never hardcode secrets.

### Risk 6: Lack of Telemetry

If the backend does not include logging and health checks from the beginning, TrackFlow may repeat its current problem of discovering failures through informal messages.

Mitigation:

* Add structured logs.
* Add health-check endpoints.
* Track integration failures.

---

## 19. Conclusion

TrackFlow should use a FastAPI backend designed as a layered, domain-oriented modular monolith.

This architecture fits the company's current reality: multiple operational domains, fragmented legacy systems, multiple frontend applications, and a need for centralized APIs.

The proposed structure separates routers, services, repositories, integrations, configuration, and telemetry. It supports the immediate backend milestone while preparing the project for future work in dashboards, telemetry, RAG, agents, workflows, and real-time systems.

The goal is not to create the most complex architecture. The goal is to create a clear, maintainable backend foundation that TrackFlow's engineering team can understand, extend, and operate.

```
```
