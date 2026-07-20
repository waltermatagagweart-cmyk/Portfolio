# Portfolio Documentation

Full write-ups, design docs, and architecture notes for each project. See the main [Portfolio](https://github.com/waltermatagagweart-cmyk/Portfolio) page for live demos and code.

---

## 🚀 Projects

### Aircraft Maintenance Database
Real-world database design for aviation maintenance tracking — 3NF schema, triggers, partial unique indexes, and airworthiness standards.
- **[README](aircraft-maintenance-db/README.md)** — Project overview
- **[DESIGN.md](aircraft-maintenance-db/DESIGN.md)** — Deep dive: schema design decisions, referential integrity, modern SQL patterns (1,200+ lines)
- **Code:** [PostgreSQL schema + queries](../projects/aircraft-maintenance-db/)

### Aircraft Maintenance API
Async REST API (FastAPI + SQLAlchemy 2.0 + asyncpg) serving the maintenance database above as a real running service — validation, report endpoints, Docker Compose, idempotent test suite.
- **[README](aircraft-maintenance-api/README.md)** — Endpoints, running it, testing, design notes
- **Code:** [FastAPI + SQLAlchemy + Docker](../projects/aircraft-maintenance-api/)

### Flight Telemetry Dashboard
Interactive glass-cockpit dashboard built with HTML/CSS/Canvas. Real-time charts, navigation display, system annunciators, and telemetry log.
- **[README](flight-telemetry-dashboard/README.md)** — Feature overview, Canvas rendering, data simulation
- **Live demo:** [flight-telemetry-dashboard](https://waltermatagagweart-cmyk.github.io/Portfolio/projects/flight-telemetry-dashboard/)
- **Code:** [Self-contained HTML + CSS + JS](../projects/flight-telemetry-dashboard/)

### Rocket Ascent Simulator
Python numerical-methods project. Physics-based simulation of vertical rocket ascent with variable mass, altitude-dependent gravity, and atmospheric drag.
- **[README](rocket-ascent-sim/README.md)** — Physics model, integration method, test suite, sample ascent profile
- **Code:** [Python + SciPy + tests](../projects/rocket-ascent-sim/)

### Siaka Cargo (Case Study)
Architecture write-up for a multi-tenant logistics SaaS platform serving the East African freight corridor (Mombasa → inland Kenya/Uganda/Rwanda/South Sudan).
- **[README](siaka-cargo/README.md)** — System architecture, security patterns, real-world integrations (FastAPI, PostgreSQL, Kubernetes, M-Pesa, Stripe, Azure OCR)
- **Code:** Proprietary — architecture and design only

---

## How to use

- **To understand a project's design:** Start with the README in each folder
- **For deep technical details:** Read DESIGN.md (where available)
- **To see and run the code:** Follow the "Code" links to the actual project folders
- **For live demos:** Click the demo links above

All documentation is written to be self-contained — you don't need to jump between files.
