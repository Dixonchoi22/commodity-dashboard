# PMO Programme — Azure Landing Zone Plan

**Programme:** PMO EU Procurement
**Known projects:** Commodity Dashboard · EU Indirect Supplier Finder (repo: `vendorpath`)
**Date:** September 2026
**Status:** Draft — read alongside `azure-migration-requirements.md`

---

## Why this document exists

Business IT asked us to size the programme's first project and offered to create
a Resource Group for it. Answering only that question would produce a landing zone
sized for a 1.5 MB static website.

The programme's second project, **EU Indirect Supplier Finder** (repo `vendorpath`), is a supplier onboarding and
procurement ERP: server-rendered Next.js, a fourteen-model PostgreSQL schema,
supplier PII and bank details, an **externally facing supplier portal**, and
integrations into Entra ID, SAP, D365 and n8n. It does not fit the same shape.

**The risk is not cost — it is that the shape gets fixed before the larger
workload is on the table.** Subscription layout, network design, the identity
model, the database engine standard and the naming scheme are all decided once,
early, based on what IT understands the programme to be. Retrofitting them means
recreating resources and re-pointing pipelines. Retrofitting a VNet or an
external-identity tenant around a live ERP is considerably worse.

So this document puts both projects in front of IT at the same time.

---

## 1. The two known projects, side by side

| | Commodity Dashboard | EU Indirect Supplier Finder |
| --- | --- | --- |
| **Type** | Quarterly commodity intelligence dashboard | Supplier onboarding + procurement ERP |
| **Stack** | Pre-built static HTML; offline Python build | Next.js 14 App Router (SSR), Prisma, PostgreSQL |
| **Runtime compute** | **None** | **Always-on** server-side rendering + server actions |
| **Data** | 113 commodity rows per quarter, in git | 14 relational models: suppliers, products, POs, invoices, requisitions, budgets, approvals, bank-change requests, event log |
| **Sensitivity** | Commercially licensed market data | **Supplier PII, bank account changes, sanctions status, invoice and budget data** |
| **Users** | Internal, read-only, low tens | Internal buyers **plus external suppliers via a public portal** |
| **Integrations** | None at runtime | Entra ID SSO, SAP, D365, n8n automation |
| **Deployed today** | GitHub Pages (public) | Vercel + Neon Postgres |
| **Indicative PROD cost** | ~€10 / month | **~€180–250 / month** |

The dashboard is the easy one. Everything that follows is driven by VendorPath.

---

## 2. The actual requirement: keep the ability to build

Before the resource lists, the requirement that matters most to us.

**We are not asking Azure to be cheaper or bigger. We are asking it not to be
slower.** The current setup — deploy on git push, create a database in under a
minute, call an external API by adding an environment variable — is why these
two projects exist at all. A landing zone that turns each of those into a ticket
does not just cost time; it stops the exploratory work that produced them.

### 2.1 What we would be trading

| Today | In a default corporate landing zone |
| --- | --- |
| `git push` → deployed in ~90 seconds | A release process, possibly change-controlled |
| Create a database in under a minute | A ticket, a SKU approval, a lead time |
| Call any external API by adding an env var | Egress via a firewall allowlist — a rule request per endpoint |
| A preview environment per branch | One shared DEV environment |
| Try something, delete it, no trace | Every resource enters patching, scanning and access review |

**Not all of that is worth defending.** Some of the governance is genuinely
needed here: VendorPath holds supplier bank details and PII on a personal Vercel
and Neon account today, and the dashboard publishes internal procurement data to
a public URL. Those are real problems that a governed tenant fixes, and we are
not arguing against them.

**But velocity in DEV is worth defending, and it is almost always free to
grant.** The controls that matter belong in PROD.

### 2.2 The five asks that preserve most of it

1. **Contributor RBAC on our own resource groups, inside an agreed budget.** The
   single highest-value item in either document. With it, adding a database or a
   container app to our own resource group takes minutes. Without it, every
   resource is a ticket, and that is what actually slows programmes down — not
   provisioning time.

2. **A DEV resource group, or a sandbox subscription, with relaxed Azure Policy.**
   Many organisations already run an innovation or sandbox subscription for
   exactly this. If one exists, we would rather build there first and promote into
   the governed landing zone than start against production policy.

3. **Confirmed outbound internet egress — and this is the quiet one.** VendorPath
   calls n8n, SAP and D365; the dashboard build pulls Eurostat and Destatis; both
   pull public package registries at build time. If the landing zone routes egress
   through a firewall with a destination allowlist, every one of those becomes a
   separate rule request. **The first symptom is a timeout nobody can explain**,
   usually weeks after the design was signed off. We need to know the egress model
   before we design against it, and ideally an allowlist we can extend ourselves in
   DEV.

4. **Deploy on push.** A pipeline with a service principal scoped to our own
   resource group, triggered by a merge — not a manual release request. This is
   also the safer option: it makes deployments reproducible and auditable, which
   is what change control is actually trying to achieve.

5. **DEV exempt from change control.** Whatever approval PROD requires, DEV should
   not need it.

### 2.3 The honest summary

We will not get Vercel-grade flexibility inside a governed corporate tenant, and
for a system holding supplier bank details we should not expect to. But with
those five, we keep most of it where it matters, and PROD keeps the controls it
ought to have. **The trade we are proposing is: accept real governance in PROD,
in exchange for staying fast in DEV.**

If IT can only grant one of the five, make it the first.

---

## 3. What VendorPath needs — indicative sizing

This is a forward estimate for planning and budget purposes, not a provisioning
request. VendorPath is not ready to migrate; it currently has no database
attached (see §6).

| Component | DEV | PROD | Notes |
| --- | --- | --- | --- |
| **Container Apps Environment** | 1 | 1 | Hosts the Next.js app and the n8n runtime side by side. Scale-to-zero in DEV. |
| ├ VendorPath app | 0.5 vCPU / 1 GB, scale 0–1 | 0.5–1 vCPU / 2 GB, min 1 replica | Next.js SSR. Fallback: App Service Linux B1 / P1v3. |
| └ n8n | 0.5 vCPU / 1 GB | 0.5 vCPU / 1 GB | Automation backend — emails, reminders, SAP/D365 sync. Needs its own database. |
| **PostgreSQL Flexible Server** | `B1ms`, 32 GB | `B2s`, 64 GB, PITR 7–35 days | **Not Azure SQL** — the Prisma schema is Postgres. Two databases on one server: `vendorpath` and `n8n`. Burstable scales up in place. |
| **Storage Account** | 1 | 1 | Supplier onboarding documents — certificates, insurance, bank letters. Private access, soft-delete, versioning. |
| **Key Vault** | 1 | 1 | Genuinely required here: `AUTH_SECRET`, `N8N_SHARED_SECRET`, `N8N_API_KEY`, SAP credentials, DB connection strings, Entra client secret. Accessed by managed identity. |
| **Application Insights** | 1 | 1 | Onto the shared programme workspace. |
| **Entra ID app registration** | 1 | 1 | Internal staff SSO. |
| **External identity** | — | 1 tenant | **Suppliers are external users.** See §3.1. |
| **VNet + subnets** | shared | shared | One programme VNet, subnet per project. |
| **Private endpoints** | — | 3–4 | Postgres, Key Vault, Storage. Justified here by PII and bank data. |
| **Front Door Standard + WAF** | — | 1 | The supplier portal is internet-facing and accepts bank-detail changes. See §3.5. |
| **Service Bus** | — | later | For reliable SAP / D365 sync with retry and dead-lettering. Not day one. |

**Indicative monthly totals** — West Europe list prices, no EA discount:

| | DEV | PROD |
| --- | --- | --- |
| VendorPath | ~€40–70 | ~€180–250 |
| Commodity Dashboard | ~€1 | ~€10 |
| **Programme** | **~€45–70** | **~€190–260** |

Roughly **€250–330/month for the programme**, against €11/month if only the
dashboard is declared. That gap is the reason to have this conversation now
rather than in six months.

---

## 4. Verdict on IT's "other Azure resources" list

IT listed nine services and invited us to add others. Assessed across **both**
projects rather than the dashboard alone:

| Service | Dashboard | VendorPath | Verdict |
| --- | --- | --- | --- |
| **Key Vault** | placeholder | **required** | **Yes, day one.** VendorPath cannot run without it — auth signing secret, n8n shared secret and API key, SAP credentials, database connection strings, Entra client secret. Accessed by managed identity, not secrets in config. |
| **Application Insights** | yes | yes | **Yes, day one.** One instance per project per environment, all writing into one shared programme workspace. |
| **Container Apps** | no | **yes** | **Yes, when VendorPath moves.** This is the programme's primary compute — the Next.js app and the n8n runtime in one environment, scale-to-zero in DEV. Needs a Container Registry alongside it (§4.1). |
| **Service Bus** | no | **yes, phase 2** | **Yes, when SAP / D365 sync goes live.** Today VendorPath fires a webhook at n8n and hopes. For purchase orders and invoices that is too fragile — a sync that fails at 02:00 should land in a dead-letter queue, not vanish. Basic tier costs cents. |
| **API Management** | no | not yet | **No.** Nothing publishes an API to multiple consumers. Container Apps plus Front Door already covers ingress; APIM is for third-party API lifecycle, keys and quotas. Revisit when a second system consumes a VendorPath API. Developer tier is ~€45/month with no SLA; Basic ~€135. |
| **Azure OpenAI** | plausible | plausible | **Request it as Microsoft Foundry instead** — see §4.2. Not provisioned day one, but the approval and regional quota started now, because that path is slow and entirely separate from provisioning. |
| **Azure AI Services** | no | **later — Document Intelligence** | **Folded into the same Foundry request** (§4.2). The dashboard's PDF parsing is deterministic text extraction and needs no AI. VendorPath collects supplier certificates, insurance documents and bank letters and processes invoices — extracting fields and expiry dates from those is precisely Document Intelligence's job. A realistic phase-three item. |
| **VNet integration** | no | **yes** | **Yes, when VendorPath moves — one programme VNet with a subnet per project.** Required for private Postgres, private Key Vault, private Storage and SAP reachability. Do not build a VNet per project. |
| **Private Endpoints** | no | **yes, data plane only** | **Yes — 3 or 4 in VendorPath PROD: Postgres, Key Vault, Storage. Explicitly not on the supplier portal**, which has to stay reachable by external companies, and not on the dashboard, for the reason given in the sizing response. |

### 4.1 Services the list did not mention that we will still need

| Service | Why |
| --- | --- |
| **Azure Database for PostgreSQL Flexible Server** | The largest omission — VendorPath's entire data layer. Not Azure SQL: the schema is Postgres via Prisma. |
| **Azure Container Registry** | Container Apps needs somewhere to pull images from. Basic tier ~€5/month. Easy to forget until the first deploy fails. |
| **Front Door + WAF** | The supplier portal is internet-facing and accepts bank-detail changes (§5.5). |
| **Microsoft Entra External ID** | Suppliers are not employees and will never exist in the corporate tenant (§5.1). |
| **Managed identities** | Free, but worth requesting explicitly as the pattern — app to Key Vault, app to Storage, app to Postgres, with no secret in configuration. |
| **Defender for Cloud** | Likely mandated by policy rather than chosen. Budget for it: roughly €15 per server per month across the database and container plans. |
| **Self-hosted CI runners** | Only if egress is restricted enough that hosted runners cannot reach the subscription — worth confirming alongside §2.2. |

### 4.2 Microsoft Foundry — the right vehicle for both AI line items

Microsoft Foundry (formerly Azure AI Foundry / Azure AI Studio) is the unified
platform over Azure OpenAI and Azure AI Services: model catalogue, deployments,
the agent service, evaluations, content safety and tracing in one place. If we
are going to do anything with AI, **it replaces the separate "Azure OpenAI" and
"Azure AI Services" line items on IT's list rather than adding to them.**

Our position is unchanged: not provisioned day one, but **the approval started
now**. What changes is what we ask for.

**Three things to ask IT:**

1. **Does a central Foundry or Azure OpenAI instance already exist?** Many
   organisations run one and grant projects access. Consuming a central instance
   is faster and cheaper than provisioning our own, and it is usually what the AI
   governance policy expects.
2. **Model quota in an EU region.** Tokens-per-minute quota is assigned per
   subscription per region, and it is the slow part of the request — not the
   resource itself.
3. **Whether AI use is permitted against our data classification** (§5.4). Azure
   OpenAI does not train on customer data and the EU Data Boundary applies to EU
   deployments, but with supplier PII and bank details in scope this needs to be
   written down rather than assumed.

**What it drags in.** A Foundry hub is not a single resource. Depending on the
project type it wants its own **Storage Account** and **Key Vault**, and
optionally a **Container Registry** and **Application Insights**. IT should size
for three to five resources, not one. The newer resource-based Foundry project is
lighter than the classic hub — worth asking which pattern their catalogue
supports.

**Cost shape.** The platform itself is close to free; spend is token-based
inference plus any content-safety and evaluation usage. That makes it one of the
few services genuinely safe to have provisioned before it is used, and a good fit
for the budget-envelope approach in §6.

**Credible first uses, in priority order:**

| Use | Project | Why it is a good first move |
| --- | --- | --- |
| **Translating quarterly commentary into the eight non-English languages** | Dashboard | The strongest starting point. The SPA is already fully multilingual, but analyst prose ships in English with a "written in English" note because hand-translating it every quarter is not realistic. Bounded, reviewable, and the content is published market commentary with no sensitivity. |
| Drafting trend analysis from 113 commodity movements | Dashboard | The analyst reviews and edits; the model does the first pass. |
| Supplier document extraction — certificates, insurance, bank letters | VendorPath | Document Intelligence rather than a language model. Expiry dates already drive the app's auto-suspend logic. |
| Invoice and PO matching assistance | VendorPath | The three-way match exists; AI assists on exceptions only. |
| Natural-language questions over procurement data | VendorPath | Highest sensitivity — needs §5.4 signed off first. |

---

## 5. The five long-lead items — start these now

These are not provisioning tasks. Each one is an organisational decision or
approval that takes weeks of calendar time and is entirely independent of
spinning up a resource. **They are what will actually delay VendorPath**, not
the compute.

### 5.1 External identity for the supplier portal

VendorPath's suppliers log in to confirm receipts and maintain their own company
records. They are **not employees and will never exist in the corporate Entra ID
tenant.** Today the app authenticates them with an email and a bcrypt password
against its own `AppUser` table.

Three options, and the choice has to be made before the identity layer is built:

1. **Microsoft Entra External ID** — a separate tenant for external users. The
   Microsoft-native answer, and the one IT will most likely prefer, but it is a
   distinct resource with its own provisioning and governance path.
2. **Keep the application's own credential store** for suppliers, with Entra ID
   SSO for internal staff only. Fastest, and the app is already built this way —
   but it puts password handling and account recovery inside our application.
3. **Invite suppliers as Entra ID B2B guests.** Workable for a small, stable
   supplier base; painful at scale and it consumes directory objects.

**Ask IT now:** which of these is acceptable, and does a supplier-facing external
identity tenant already exist anywhere in the organisation?

### 5.2 SAP and D365 connectivity

`exportToSap` currently stamps a placeholder reference. Making it real requires
network reachability to SAP, which is almost certainly not on the public
internet. That means one of: VNet integration plus ExpressRoute or VPN to the
SAP landscape, an on-premises data gateway, or a middleware endpoint someone
else already operates.

**This is the single longest lead time in the programme.** It involves the SAP
basis team, the network team and probably a firewall change request.

**Ask IT now:** what is the sanctioned pattern for an Azure-hosted application to
reach SAP and D365, and who owns it?

### 5.3 PostgreSQL as the programme database standard

Many corporate Azure catalogues default to Azure SQL. VendorPath's schema is
PostgreSQL via Prisma — moving it to SQL Server would mean a schema and ORM
migration for no benefit.

**Ask IT now:** is **Azure Database for PostgreSQL Flexible Server** approved for
this subscription? If it is not, the approval path needs starting immediately,
and it is worth setting Postgres as the programme standard so both this and
future projects use one engine.

### 5.4 Data classification and security review

VendorPath holds supplier PII, sanctions status and — the item that will draw the
most attention — **supplier bank account change requests**. Fraudulent bank-detail
changes are one of the most common procurement attack vectors, so this system
will attract a security review whether or not we ask for one.

Getting the classification agreed early determines encryption, retention,
logging, network isolation and approval requirements. Discovering those
requirements after the architecture is built is the expensive path.

**Ask IT now:** what data classification applies, what does it mandate, and can
the security review be scheduled early rather than as a go-live gate?

### 5.5 Internet-facing policy and WAF

The supplier portal must be reachable by external companies, so it cannot sit
behind a private endpoint or a VPN. Most corporate policies require a WAF in
front of anything internet-facing that accepts authenticated writes.

**Ask IT now:** what is the standard for internet-facing applications — Front Door
with WAF, Application Gateway, or something already centrally operated that we
should publish through?

---

## 6. What to ask IT for now

Combining this with §8.1 of the dashboard response:

| Ask | Cost to hold | Why now |
| --- | --- | --- |
| **Subscription and Resource Group layout sized for both projects** | Zero | Splitting a shared RG later means recreating resources |
| **Contributor RBAC for the team on its own Resource Groups, under a budget** | Zero | The difference between building freely and raising a ticket per resource |
| **A programme budget with alerts** — propose €400/month ceiling | Zero | Lets small resources be added without a fresh approval each time |
| **Naming convention and reserved project codes** (`pmo`, `euproc`, `vendorpath`→`vpath`) | Zero | Storage account names are 24 characters and cannot be renamed |
| **Service catalogue confirmation** — PostgreSQL, Container Apps, Front Door, External ID | Zero | Tells us what to design against |
| **Shared Log Analytics workspace** | ~€0 | Telemetry not collected cannot be backfilled |
| **Programme VNet with a subnet per project** | Zero until used | Retrofitting a VNet around a live database is painful |
| **Parent DNS domain** | Zero | Hostnames are hard to change once bookmarked |
| **The five decisions in §5** | Zero | Weeks of calendar time each |

**And explicitly say there are two projects.** The single most valuable sentence
to send IT is that the programme contains both a static dashboard and a
procurement ERP with external users and SAP integration — because that one fact
changes how they design everything else.

---

## 7. What not to ask for yet

Consistent with the dashboard response: do not pre-provision compute or
databases. Specifically:

- **No App Service Plans or Container Apps until VendorPath is ready to move.**
  They bill continuously whether or not anything is deployed.
- **No PostgreSQL server until the database is actually needed.** Burstable tiers
  scale up in place, so there is no capacity to reserve.
- **No API Management.** Nothing publishes an API to multiple consumers yet, and
  the Developer tier alone is ~€45/month.
- **No Front Door until the supplier portal has a go-live date.**
- **No Azure OpenAI resource** — but do start the *access approval* if AI
  features are plausible within twelve months, since that path is slow and
  independent of provisioning.

Every idle resource enters the patching, vulnerability-scanning and access-review
cycle, and unused resources from a programme's first project make its next
request harder to defend.

---

## 8. Outstanding items in VendorPath itself

These are not Azure questions, but they block any migration and two of them are
security matters. Recorded here so they are not lost.

1. **The application has no database attached.** The connection was moved off the
   old Neon project on 25 August 2026 and the replacement was never connected, so
   the deployed app points at nothing. `MIGRATION-STATE.md` documents the single
   step that fixes it. Nothing is lost — 246 demo rows, reseeded by the build.
2. **Secrets that have been shared in chat need rotating** before any real
   rollout — the Neon password, `N8N_API_KEY` and `AUTH_SECRET`. `INTEGRATIONS.md`
   already flags this. Do it before, not after, moving to Azure, so the values
   that land in Key Vault are clean.
3. **Confirm the repository is private.** It holds supplier PII handling logic and
   the README states it must stay private.
4. **The `db push` deployment model needs revisiting before production.** The
   build runs `prisma db push` against the live database on every deploy, and the
   25 August incident — a migration dropping columns shipping alongside the code
   that stopped using them, returning 500s for the length of the build — is a
   direct consequence of that shape. A production ERP wants versioned migrations
   and a deploy that is safe against the previous revision still serving traffic.
5. **Decide where n8n runs.** It is a dependency of the core PO workflow, not an
   optional extra. If it stays on a personal or third-party instance it becomes a
   single point of failure outside IT's control; if it moves to Azure it is a
   Container App plus a database, sized in §3.

---

## 9. Suggested sequence

| Phase | Work | Blocked by |
| --- | --- | --- |
| **Now** | Declare both projects to IT. Settle subscription, RG layout, naming, RBAC, budget, tagging | — |
| **Now** | Raise the five §5 decisions — they run in parallel and cost nothing to start | — |
| **Next** | Migrate the Commodity Dashboard. Small, low risk, proves the landing zone and the CI/CD pattern end to end | RG + RBAC |
| **Then** | Fix VendorPath's database connection and rotate its secrets, still on Vercel | Nothing |
| **Then** | Replace `db push` with versioned migrations | Nothing |
| **Then** | Stand up VendorPath DEV in Azure — Container Apps, PostgreSQL, Key Vault | §5.3 approval |
| **Then** | Wire Entra ID SSO for internal staff, then external identity for suppliers | §5.1 decision |
| **Later** | SAP and D365 connectivity | §5.2 — start early, lands late |
| **Later** | PROD with WAF, private endpoints and the security review signed off | §5.4, §5.5 |

Migrating the dashboard first is deliberate. It is a genuinely low-risk workload
that exercises the whole path — resource group, naming, CI/CD, SSO, custom
domain, telemetry — before anything with supplier data depends on it working.
