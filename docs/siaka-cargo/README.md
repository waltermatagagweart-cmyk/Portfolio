# 🚢 Siaka Cargo — Logistics Intelligence Platform

A multi-tenant logistics SaaS platform for the **East African freight corridor** —
real-time shipment tracking, AI-powered risk scoring, automated invoice auditing, and
port-congestion forecasting, with M-Pesa and Stripe payments and Kenyan tax compliance
built in.

**Author:** Walter Matagagwe · **Status:** In active development (2025–present) ·
**Type:** Private commercial project — this is an architecture case study; the source is
not public.

---

## The problem

Freight along the East African corridor (Mombasa port → inland Kenya, Uganda, Rwanda,
South Sudan) runs on fragmented tools: shipment status lives in emails and spreadsheets,
customs invoices are audited by hand, currency and tax rules shift, and forwarders have
no early warning when a port is about to congest. Siaka Cargo pulls all of that into one
tenant-isolated platform where a freight company sees its shipments, money, risk and
paperwork in real time.

---

## Architecture at a glance

| Layer | Technology |
|---|---|
| **API / backend** | Python **FastAPI** (fully async), served by Uvicorn |
| **Database** | **PostgreSQL** (Supabase), async access pool |
| **Frontend** | **React**, deployed on Cloudflare Pages |
| **Workflow automation** | **n8n** orchestration |
| **Document AI** | **Azure** Document Intelligence (OCR) |
| **Payments** | **M-Pesa** (Daraja API) and **Stripe** |
| **Deployment** | **Kubernetes** (config via ConfigMaps), structured JSON logging |

The backend is organised into focused routers and background services — shipments,
billing, notifications, payments, AI decisions, forecasting, audit logs, data
protection, and tenant provisioning — each mounted onto one async FastAPI app.

---

## Engineering highlights

These are the parts I'm most proud of, and what each one demonstrates.

### Multi-tenancy done at the edge
Every request carries an `X-Tenant-ID` header; a **per-tenant rate-limiting middleware**
throttles noisy tenants without affecting others, and an admin provisioning flow spins up
new tenants. Tenant isolation runs all the way down to row-level separation in Postgres —
one company can never see another's shipments.

### Real-time tracking over authenticated WebSockets
Shipment updates stream to the browser over a `/ws` WebSocket. Because browsers can't set
auth headers on a WebSocket handshake, I used a **short-lived ticket** pattern: the client
redeems a JWT for a one-time WS ticket (`consume_ws_ticket`) and connects with that — so
the live channel is authenticated without leaking a long-lived token in a URL.

### AI risk scoring that keeps itself honest
Shipments get an AI-generated risk score, exposed through an `ai_decisions` router that
records **why** each decision was made (explainability for audit). A background
**model-calibration loop** re-tunes the model every 24 hours so scores don't drift as new
data arrives — the model is maintained, not fire-and-forget.

### Automated invoice auditing with Azure OCR
Customs and freight invoices are pushed through **Azure Document Intelligence**, which
extracts the fields so they can be checked automatically instead of line-by-line by a
human — the `azure_document_service` router.

### Port-congestion forecasting
A `predictive_analytics` service forecasts congestion so forwarders get an early warning
and can re-route or re-time, rather than discovering a jam on arrival.

### Money, correctly — payments + Kenyan compliance
Payments run through **M-Pesa (Daraja)** and **Stripe**. A **KRA exchange-rate service**
refreshes official Kenya Revenue Authority rates on a weekly loop so dual-currency
invoices are computed on compliant rates — tax correctness treated as a first-class
feature, not an afterthought.

### Compliance and auditability by design
An **immutable audit-log** router records actions for traceability, a **data-protection**
module supports Kenya's Data Protection Act / CMCA 2018 obligations, and a
**credential-health** background loop continuously checks that integration credentials
(payments, Azure, etc.) are valid before they fail in production.

### Production hardening (the unglamorous, important part)
The service is built to survive real deployment: it **starts even if Postgres isn't ready
yet** (the pool retries on first request instead of crashing the container), **CORS is an
explicit allow-list** with a startup assertion that refuses to boot if the production
origin is missing from the Kubernetes ConfigMap, and logs are **structured JSON** for
ingestion by log tooling. These came from real debugging — each guard exists because
something failed once and shouldn't again.

---

## What this project taught me

- Designing a **multi-tenant** system where isolation is a security boundary, not a filter.
- Authenticating **real-time** channels (WebSockets) safely.
- Treating an ML model as a **maintained service** (calibration, decision logging), not a
  one-off script.
- Integrating hard external systems — **payments, OCR, tax rates** — and handling their
  failure modes gracefully.
- Operating a service on **Kubernetes** with health checks, structured logging, and
  configuration that fails loudly when it's wrong.

---

## Tech stack

`Python` · `FastAPI` · `async / asyncio` · `PostgreSQL (Supabase)` · `React` ·
`WebSockets` · `JWT auth` · `Azure Document Intelligence` · `M-Pesa (Daraja)` · `Stripe` ·
`n8n` · `Kubernetes` · `Cloudflare Pages`

> This case study describes a private, in-development commercial platform. A public code
> sample or live demo can be shared on request.
