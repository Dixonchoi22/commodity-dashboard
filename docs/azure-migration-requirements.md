# Azure Infrastructure Requirements — PMO EU Procurement

**Project:** PMO EU Procurement — Commodity Intelligence Dashboard
**Prepared for:** Business IT — Azure Resource Group provisioning
**Date:** September 2026
**Status:** Draft for IT review

---

## 0. What the application is (this drives every answer below)

Before the line-item answers, the single most important fact about this
workload:

> **It is a static website plus an offline batch build. There is no
> server-side application, no database, no runtime API and no user-generated
> data.**

Concretely, as it stands today:

| Attribute | Value |
| --- | --- |
| Deployed payload | **1.5 MB** of static HTML/JS/CSS (7 files) |
| Server-side code | **None** — no Flask/FastAPI/Django, no REST API, no ORM |
| Database | **None** — content ships as versioned JSON in the repository |
| Runtime network calls from the browser | **None** — all data is inlined into `app-data.js` at build time |
| Content volume | 113 commodity rows per quarter × 9 languages, 2 quarters live |
| Publication cadence | **Quarterly (4×/year)** |
| Concurrent users | Low tens — internal procurement / PMO audience |
| Authentication today | None (published on public GitHub Pages) |
| Secrets / credentials | **None** in the codebase |

The build pipeline (`scripts/*.py`) is a **local, offline, operator-triggered
job** that runs roughly four times a year. It reads source files (Expana PDF,
Mintec xlsx, Destatis zip), pulls Eurostat open data over anonymous HTTPS, and
emits static HTML. It is not a service, has no endpoint and does not need to
be online.

**Implication for sizing:** this workload needs a fraction of the standard
project footprint. Provisioning Function Apps, App Service Plans and a SQL
Database for it would create cost and patching obligations against resources
that would sit idle. The requirements below are deliberately minimal, with the
trigger conditions stated for each thing we are *not* asking for.

---

## 1. Environments

**Request: 2 environments — DEV and PROD.**

| Environment | Purpose | Notes |
| --- | --- | --- |
| **DEV** | Build verification, layout/translation changes, next-quarter dry runs | Free/lowest tier throughout |
| **PROD** | The published dashboard consumed by the business | Standard tier, SSO, custom domain |

**Why not DEV / TEST / UAT / PROD:** the deliverable is a quarterly document,
not a transactional system. There is no integration surface to test and no
data migration to rehearse. Content review (the only real "UAT" step) is
handled by **per-pull-request preview environments**, which Azure Static Web
Apps provides at no extra cost — each content change gets its own temporary URL
that reviewers approve before it merges to PROD. That covers the UAT need
without a standing environment.

If corporate policy mandates a four-tier landing zone regardless, TEST and UAT
can be added on Free-tier Static Web Apps at roughly €0/month each — please
confirm whether the policy requires it.

---

## 2. Function Apps

**Request: 0.**

| Question | Answer |
| --- | --- |
| Number of Function Apps | **None required** |
| Hosting plan / SKU | N/A |
| Expected workload | N/A |

There is no event-driven, HTTP-triggered or timer-triggered compute in this
solution. The build is an operator-run batch job, not a function.

**Note if the build is later moved into Azure:** a Consumption Function App
would be the wrong target — the extraction step shells out to **`pdftotext`
(Poppler)**, a native Linux binary that cannot be installed on a Consumption
plan. The correct Azure-native host would be a **Container Apps Job** (see
§5.5). Our preference is to leave the build in CI/CD, which costs nothing and
needs no Azure resource.

**What would change this:** if we later add a live data feed (e.g. a nightly
Eurostat refresh that updates the dashboard between quarters), that would be
one timer-triggered Function on a **Flex Consumption** plan.

---

## 3. App Services

**Request: 0 App Services — 2 × Azure Static Web Apps instead.**

| Environment | Resource | SKU | Indicative list price |
| --- | --- | --- | --- |
| PROD | Azure Static Web App | **Standard** | ~€9 / month |
| DEV | Azure Static Web App | **Free** | €0 |

**Why Static Web Apps rather than an App Service Plan:**

- The payload is 1.5 MB of static files. An App Service Plan provisions a
  dedicated VM to serve them — we would pay for and patch a compute instance
  that never executes code.
- Static Web Apps includes, at Standard tier: global CDN distribution,
  free managed TLS certificates, custom domains, **Entra ID authentication
  with role-based access**, per-PR preview environments, and a 99.95% SLA.
- Built-in CI/CD integration deploys straight from the repository on merge.

**Fallback if Azure Static Web Apps is not in the approved service catalogue:**

| Environment | Resource | SKU | Indicative list price |
| --- | --- | --- | --- |
| PROD | App Service (Linux) | **S1** | ~€65 / month |
| DEV | App Service (Linux) | **B1** | ~€12 / month |

S1 is the lowest tier that carries a production SLA, deployment slots and VNet
integration. B1 is adequate for DEV. Both would run as static file hosts with
**Easy Auth / Entra ID** enabled. One App Service Plan per environment; the
two environments should not share a plan.

We would prefer the Static Web Apps option — it is roughly **85% cheaper** and
a better fit for the workload — but will accept App Service if that is the
standard.

---

## 4. SQL Database

**Request: 0.**

| Question | Answer |
| --- | --- |
| Number of SQL Databases | **None required** |
| Estimated size | N/A |
| Performance tier | N/A |

The dashboard's content is 113 commodity rows per quarter plus commentary and
translations — a few hundred KB of JSON per quarter, version-controlled in the
repository. Git provides the history, diffing and rollback that a database
would otherwise provide, and the data is written once per quarter by one
operator. There is no query workload, no concurrent write, and no relational
integrity requirement.

**What would change this:** if the roadmap adds cross-quarter time-series
analysis, an API for other systems to query commodity prices, or user-entered
data (saved views, annotations, alerts). At that point the right starting
point would be **Azure SQL Database, Basic tier (5 DTU, 2 GB, ~€5/month)** —
still the smallest SKU available. We do not need it provisioned now.

---

## 5. Storage Accounts

**Request: 1 per environment — 2 total.** Your one-per-project/environment
default is exactly right; we have no need for additional accounts.

| Setting | Value |
| --- | --- |
| Performance / redundancy | Standard, **LRS** (GRS not required — source files are reproducible) |
| Access tier | **Hot** |
| Current size | < 5 GB |
| Growth | ~5 MB per quarter (~20 MB/year) |
| Services used | **Blob only** — no Files, Queues or Tables |

**Intended usage:**

1. **Source-document archive** — the original Expana/Mintec PDFs, forecast
   xlsx and Destatis zips for each quarter. These are currently committed to
   git (~1–3 MB per quarter) and are better held in blob storage with
   versioning and soft-delete enabled, keeping the repository lean.
2. **Build artefact retention** — the generated HTML bundle for each quarter,
   so a prior quarter's published output can be restored without re-running
   the pipeline.

Please enable **blob soft-delete (30 days)** and **blob versioning**. These are
the only copies of some vendor-supplied source documents.

---

## 6. Other Azure Resources

### 6.1 Key Vault — **1 per environment (2 total). Standard tier.**

No secrets exist in the solution today. We are requesting it as the standard
landing-zone component so that credentials have a home when they arrive —
specifically a Mintec/Expana data-vendor API key if we automate source
ingestion, and the deployment service principal. Cost is negligible
(~€0.03 per 10,000 operations).

### 6.2 Application Insights + Log Analytics workspace — **1 per environment.**

We currently have **no visibility into whether the dashboard is being used** —
GitHub Pages provides no analytics. This is genuinely valuable: it tells us
which commodity categories and which language versions the business actually
opens, which informs what we build next quarter. Expected telemetry volume is
well inside the **5 GB/month free grant**; effective cost ≈ €0.

### 6.3 Microsoft Entra ID app registration — **1 per environment.**

**This is the single most important item on the list, and the main reason for
the migration.** The dashboard contains internal EU procurement intelligence
and commercially licensed commodity price data, and it is currently served
from a **public** GitHub Pages URL with no access control. Moving to Azure with
**Entra ID SSO** restricts it to authenticated employees.

Please confirm the intended access model:

- **(A) Internal only** — Entra ID SSO, optionally restricted to a security
  group (e.g. `PMO-EU-Procurement-Readers`). **This is our recommendation.**
- **(B) Public** — no authentication, as today.

The tier choices above assume **(A)**.

### 6.4 Custom domain + DNS + TLS — **1 hostname for PROD.**

Something along the lines of `procurement-intel.<company>.com`. Managed
certificate issued by the platform; we need a CNAME record created and a
domain name confirmed by IT.

### 6.5 Container Apps — **0 requested, 1 conditional.**

Only required if policy states that the quarterly build must execute inside
Azure rather than in CI/CD. In that case the correct shape is a **Container
Apps Job** (manual/scheduled trigger, not a always-on Container App), because
the build needs the native `pdftotext` binary in the image. At four runs per
year the consumption cost rounds to zero. **Our preference is to keep the
build in the CI/CD pipeline and provision nothing.**

### 6.6 Not required

| Service | Why not |
| --- | --- |
| **Service Bus** | No asynchronous messaging or inter-service communication |
| **API Management** | No APIs are published or consumed at runtime |
| **Azure OpenAI** | No LLM inference in the product |
| **Azure AI Services** | PDF extraction is deterministic text parsing (`pdftotext` + regex), not OCR or Document Intelligence |
| **Azure Front Door / CDN** | Static Web Apps includes global distribution; a separate Front Door (~€35/month) would be redundant |
| **Redis / Cache** | Nothing to cache — the payload *is* the cache |
| **Azure Data Factory** | Four operator-run builds a year is not an orchestration problem |

### 6.7 VNet integration & Private Endpoints — **conditional on policy**

Not required for the application to function, and it carries a real usability
cost: putting a **private endpoint on a Static Web App disables its public
endpoint entirely**, meaning users can only reach the dashboard from the
corporate network or over VPN/ExpressRoute. For a dashboard read by
procurement staff who may be travelling, Entra ID SSO over the public endpoint
gives equivalent security with better reach.

**Please advise whether policy mandates private endpoints for internal
web applications.** If yes, we will need:
- 1 × private endpoint per environment (~€7/month each)
- VNet + subnet delegation
- Private DNS zone integration
- Confirmation that VPN/ExpressRoute coverage is acceptable for all users

---

## 7. Region and data residency

**Requested region: West Europe (Netherlands)**, with Germany West Central as
an acceptable alternative.

The dashboard carries EU procurement data with a German (Destatis) deep-dive
and an EU-27 audience across nine languages. Both environments should be in
the same region.

---

## 8. Summary — what we are asking for

| # | Resource | DEV | PROD |
| --- | --- | --- | --- |
| 1 | Azure Static Web App | Free | **Standard** |
| 2 | Storage Account (Standard LRS, Hot, Blob) | 1 | 1 |
| 3 | Key Vault (Standard) | 1 | 1 |
| 4 | Application Insights + Log Analytics | 1 | 1 |
| 5 | Entra ID app registration | 1 | 1 |
| 6 | Custom domain + managed TLS | — | 1 |
| — | Function Apps | 0 | 0 |
| — | App Services | 0 | 0 |
| — | SQL Databases | 0 | 0 |
| — | Service Bus / APIM / OpenAI / AI Services | 0 | 0 |

**Indicative monthly cost — recommended design**

| Item | DEV | PROD |
| --- | --- | --- |
| Static Web App | €0 (Free) | ~€9 (Standard) |
| Storage Account | < €1 | < €1 |
| Key Vault | ~€0 | ~€0 |
| App Insights / Log Analytics | €0 (free grant) | €0 (free grant) |
| **Total** | **~€1** | **~€10** |

**≈ €11 / month combined (~€130 / year).**

For comparison, the App Service fallback (§3) would be **≈ €77/month
(~€930/year)** for the same functionality.

*All figures are indicative list prices for West Europe and exclude any
Enterprise Agreement discount — please confirm against the Azure pricing
calculator.*

---

## 9. Questions back to IT

These do not block the Resource Group creation, but the answers may adjust the
sizing above:

1. **Access model** — internal-only via Entra ID SSO, or public? (We recommend
   internal-only; §6.3.)
2. **Is Azure Static Web Apps in the approved service catalogue?** If not, we
   fall back to App Service B1/S1 (§3) and the cost rises to ~€77/month.
3. **Does network policy permit public CDNs?** The dashboard currently loads
   Chart.js from jsDelivr and web fonts from Google Fonts. If egress to public
   CDNs is blocked, or if a strict Content-Security-Policy applies, we will
   bundle those assets into the deployment instead — a small development task
   we would rather identify now than discover after go-live. **This is the one
   change that could break the application on a locked-down network.**
4. **Source control** — does the repository stay on GitHub, or move to Azure
   DevOps? This determines how the CI/CD deployment is wired.
5. **Private endpoints** — mandated by policy, or optional? (§6.7)
6. **Custom domain** — what hostname should be reserved? (§6.4)
7. **Environment count** — is DEV + PROD acceptable, or does the landing-zone
   standard require four tiers? (§1)
8. **Naming convention & tagging** — please share the standard so we can
   pre-populate resource names, cost-centre and owner tags.

---

## 10. Migration approach

| Phase | Work | Owner |
| --- | --- | --- |
| 1 | Resource Group + resources provisioned per §8 | IT |
| 2 | Entra ID app registration, security group, access model confirmed | IT |
| 3 | CI/CD pipeline wired from repository to Static Web App | Project |
| 4 | Vendor CDN assets locally if required by §9.3 | Project |
| 5 | Deploy to DEV, validate all 9 languages and both quarters | Project |
| 6 | Custom domain + TLS on PROD, SSO smoke test | IT + Project |
| 7 | Cut over, retire the public GitHub Pages site | Project |

**No data migration is required** — the entire application state is the
repository. Cutover is a deployment, not a migration, and is reversible by
re-enabling GitHub Pages.
