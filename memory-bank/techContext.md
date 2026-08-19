# Technical Context: TrackFlow Monorepo

## Repository Architecture

TrackFlow is maintained in one monorepo containing user interfaces, shared business logic, services, documentation, agent configuration, and future automation code.

Important directories:

- `uis/website`: Public Next.js corporate website.
- `uis/backoffice`: Internal Next.js operations dashboard.
- `uis/talent-pipeline-tracker`: Separate Next.js application from an earlier milestone.
- `src/types`: Shared TrackFlow TypeScript domain models.
- `src/utils`: Reusable TrackFlow business-logic functions.
- `services`: Backend APIs and service implementations.
- `packages/shared`: Shared package-level types and utilities.
- `memory-bank`: Persistent project context read by coding agents.
- `.agents/rules`: Repository development rules for coding agents.
- `.agents/skills`: Reusable agent workflows with acceptance criteria.
- `agents` and `skills`: Product code, separate from `.agents`.

## Public Website

The public application is located at `uis/website`.

Technology:

- Next.js 16
- React 19
- TypeScript
- App Router
- CSS Modules and global CSS

The homepage uses reusable components for Header, Hero, Services, Coverage, Why TrackFlow, FAQ, Contact, and Footer.

The website also contains supplier-management pages and UI-specific Next.js API route handlers.

## Backoffice

The internal application is located at `uis/backoffice`.

Technology:

- Next.js 16
- React 19
- TypeScript
- App Router
- CSS Modules

The backoffice has its own branded shell, navigation, metadata, dashboard entry view, operational metrics, inventory alerts, shipment information, carrier recommendations, and reliability rankings.

The integration module is:

`uis/backoffice/src/lib/trackflowDashboard.ts`

It imports and executes the original Milestone 2 utilities rather than copying their implementations.

## Milestone 2 Business Logic

The TrackFlow TypeScript business logic is stored in:

- `src/demo.ts`
- `src/types/models.ts`
- `src/utils/collections.ts`
- `src/utils/search.ts`
- `src/utils/transformations.ts`
- `src/utils/validations.ts`

These files provide reusable functions for filtering, sorting, searching, shipping-cost calculation, carrier scoring and selection, inventory calculations, shipment reporting, and validation.

Applications must import these functions from their original location.

## API Placement

New backend APIs and service implementations belong under `services`.

UI-specific Next.js route handlers may remain inside an application's `src/app/api` directory when directly tied to that application.

## Agent Infrastructure

Agent instructions are defined in:

- `AGENTS.md`
- `.agents/rules/`
- `.agents/skills/`

Before modifying code, an agent must read `CONTEXT.md`, relevant memory-bank files, root and scoped `AGENTS.md` files, and applicable rules or skills.

Before creating a directory, the agent must review the README in the relevant parent directory.

## Development Commands

Website:

```bash
cd uis/website
npm install
npm run dev
npm run lint
npm run build