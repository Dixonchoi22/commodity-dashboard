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

**One structural note.** PMO EU Procurement is the **first individual project
under the PMO EU Procurement programme**, not a standalone system — further projects will
follow in the same subscription. Section 7 covers what that means for resource
group layout, naming and shared components, and section 8 sets out what we are
asking for now versus what we will request against a stated trigger later.
Several items in section 7 are effectively irreversible once resources are
created, so they are worth settling before provisioning begins.

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
§6.5). Our preference is to leave the build in CI/CD, which costs nothing and
needs no Azure resource.

**What is planned.** We expect to add a live data feed — a scheduled pull from
external commodity and index APIs to refresh the dashboard between quarters.
That is one timer-triggered Function on a **Flex Consumption** plan, which bills
close to zero when idle. Not requested now, but worth confirming Flex
Consumption is available in the catalogue (§11.2).

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

**Request: 0 today. Planned, but not to be provisioned yet.**

| Question | Answer |
| --- | --- |
| Number of SQL Databases | **None required today** |
| Estimated size | N/A |
| Performance tier | N/A |
| Planned | A small PostgreSQL database once we hold cross-quarter time series |

The dashboard's content is 113 commodity rows per quarter plus commentary and
translations — a few hundred KB of JSON per quarter, version-controlled in the
repository. Git provides the history, diffing and rollback that a database
would otherwise provide, and the data is written once per quarter by one
operator. There is no query workload, no concurrent write, and no relational
integrity requirement.

**What is planned.** We do expect this project to gain two things: a **live
data feed** — a scheduled pull from external commodity and index APIs, which
belongs on a Flex Consumption Function App (§2) — and a **small database** for
cross-quarter time series. Neither should be provisioned now. Flex Consumption
bills close to zero when idle and can be added in minutes; an idle database
bills every month.

**The cheapest route when the database is needed** is a second database on the
same **PostgreSQL Flexible Server** as EU Indirect Supplier Finder. One server
hosts several databases at no additional server cost, so the dashboard's future
database is effectively free if the programme standardises on Postgres. Stood up
alone it would be roughly €13/month per environment on a `B1ms` burstable tier.

**This is the practical reason to set PostgreSQL rather than Azure SQL as the
programme database standard** — not just that the Supplier Finder's schema is
Postgres via Prisma, but that one engine lets the two projects share a server.

What we need from IT now is that **PostgreSQL Flexible Server is approved**, not
that anything is provisioned.

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

### 6.2 Application Insights — **1 per environment**, on a shared workspace.

We currently have **no visibility into whether the dashboard is being used** —
GitHub Pages provides no analytics. This is genuinely valuable: it tells us
which commodity categories and which language versions the business actually
opens, which informs what we build next quarter. Expected telemetry volume is
well inside the **5 GB/month free grant**; effective cost ≈ €0.

The Application Insights *instance* should be per project, but it should write
into a **Log Analytics workspace shared across the PMO EU Procurement programme** rather than
one we own — see §7.3. If no such workspace exists yet, this project is a
sensible place to create it, in a shared resource group rather than ours.

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

## 7. Programme structure, naming and shared resources

PMO EU Procurement is the first of several individual projects that will sit
under the **PMO EU Procurement** programme. Three things follow from that, and two of them
cannot be changed after provisioning without recreating resources.

### 7.1 One Resource Group per project per environment — not one for the programme

| Resource Group | Contents |
| --- | --- |
| `rg-pmoeu-dash-dev-weu` | Everything for this project, DEV |
| `rg-pmoeu-dash-prod-weu` | Everything for this project, PROD |

**Please do not place all PMO projects in one shared Resource Group.** The
Resource Group is the unit of four separate things, and sharing it couples all
of them across unrelated projects:

- **Lifecycle** — tearing down or rebuilding this project must not put a
  sibling project's resources at risk.
- **RBAC** — access is granted at Resource Group scope. A shared group means
  every project team can see and modify every other project's resources.
- **Deployment scope** — each CI/CD service principal should hold rights over
  exactly one Resource Group.
- **Cost** — Resource Group is a native dimension in Cost Analysis. A shared
  group forces cost attribution to depend entirely on tags being correct.

**Subscription:** one shared PMO subscription containing a Resource Group per
project per environment is the normal pattern at this size. If your standard is
separate DEV and PROD subscriptions, that works equally well and the naming
below is unchanged.

### 7.2 Fix the project short code before anything is created

Azure name limits differ by resource type, and one of them is binding:

| Resource | Length | Characters permitted | Scope of uniqueness |
| --- | --- | --- | --- |
| **Storage account** | **3–24** | **lowercase letters and digits only — no hyphens** | **Global** |
| Key Vault | 3–24 | alphanumeric and hyphen | Global |
| Static Web App | 40 | alphanumeric and hyphen | Resource group |
| Resource Group | 90 | broad | Subscription |

Spelling the project name out does not fit inside the storage account limit:

```
stpmoeuprocurementprodweu   = 25 characters  ->  rejected by Azure
```

So the programme needs an agreed **programme code** plus a **short project code
per project**, both fixed before creation, because renaming a storage account is
not an operation — it means creating a new account and copying the data. We
propose **`pmoeu`** for the programme and **`dash`** for this project
(**`sfind`** for EU Indirect Supplier Finder). Applying the Microsoft Cloud
Adoption Framework abbreviations:

| Resource | DEV | PROD | Length |
| --- | --- | --- | --- |
| Resource group | `rg-pmoeu-dash-dev-weu` | `rg-pmoeu-dash-prod-weu` | 22 |
| Static Web App | `stapp-pmoeu-dash-dev-weu` | `stapp-pmoeu-dash-prod-weu` | 25 |
| Storage account | `stpmoeudashdevweu` | `stpmoeudashprodweu` | **18** |
| Key Vault | `kv-pmoeu-dash-dev` | `kv-pmoeu-dash-prod` | **18** |
| Application Insights | `appi-pmoeu-dash-dev-weu` | `appi-pmoeu-dash-prod-weu` | 24 |

The same slots for the second project give `rg-pmoeu-sfind-prod-weu` (23) and
`stpmoeusfindprodweu` (19) — both comfortably inside the limits.

The pattern generalises: each future PMO project takes its own code of six
characters or fewer in the same slot, leaving room for the environment and
region suffixes. Storage account and Key Vault names are globally unique across
all of Azure, so availability should be confirmed at creation time.

**If you already have a naming standard, we will use yours** — we only ask that
a short code per project is part of it, for the reason above.

### 7.3 What should be shared across the programme, and what should not

| Component | Scope | Reasoning |
| --- | --- | --- |
| **Log Analytics workspace** | **Shared** — one per environment for all of PMO EU Procurement | Cross-project querying, one retention policy, one cost line. Centralising is Microsoft's own guidance. |
| Application Insights | Per project | Keeps each project's telemetry separately queryable while writing into the shared workspace. |
| Key Vault | Per project | Blast radius and RBAC isolation. It is nearly free, so sharing saves nothing and costs separation. |
| Storage Account | Per project per environment | As §5. |
| Entra ID app registration | Per project | Each application authenticates as itself. |
| **Security groups** | **Nested** — a programme-wide `PMO-EU-Procurement-Readers` group held as a member of each project's group | Lets a person be granted every PMO dashboard at once, or exactly one. |
| **VNet and private DNS zones** | **Shared** — only if private endpoints are ever mandated | One programme VNet with a subnet per project. Do not build a VNet per project. |
| Custom domain | Shared parent, subdomain per project | See §7.4. |

### 7.4 Reserve the parent domain now

With several PMO dashboards likely, allocate a parent and give each project a
subdomain, rather than issuing unrelated hostnames per project:

```
procurement.<company>.com                    <- programme landing page (later, optional)
eu-procurement.procurement.<company>.com     <- this project
```

Static Web Apps binds one hostname per app, so a subdomain per project is the
natural fit, and a shared index listing every PMO dashboard becomes trivial to
add later. Hostnames are hard to change once people have bookmarked them.

### 7.5 Tagging — this is how the programme bill gets split

With one subscription carrying several projects, tags are the mechanism for
cost attribution. Applied consistently to every resource:

| Tag | Value for this project |
| --- | --- |
| `programme` | `PMO EU Procurement` |
| `project` | `Commodity Dashboard` |
| `project-code` | `dash` |
| `environment` | `dev` / `prod` |
| `owner` | *(project owner / distribution list)* |
| `cost-centre` | *(supplied by IT)* |
| `data-classification` | `Internal — commercially licensed` |

### 7.6 Azure DevOps — one programme project, one repository per sub-project

If the "PMO EU Procurement" project already created is an **Azure DevOps project**, keep it as
the programme container and give each individual project its own **Git
repository inside it**:

```
PMO EU Procurement  (Azure DevOps project = the programme)
├── Repos
│   ├── commodity-dashboard           <- this project
│   ├── vendorpath                    <- EU Indirect Supplier Finder
│   └── <next project>
├── Pipelines   one per repository, deploying only to that project's RG
└── Boards      one backlog, an area path per project
```

Microsoft's guidance favours fewer, larger Azure DevOps projects. Creating one
ADO project per sub-project fragments boards, permissions, service connections
and pipeline templates, and the fragmentation cannot easily be undone later.

**Service connections:** one per project per environment, each scoped to that
project's Resource Group alone — not a single programme-wide principal holding
subscription-level rights.

**One caveat on consolidating repositories.** Azure DevOps grants read access at
*project* level by default, so every member of the PMO project would be able to
read every repository in it. That is fine for the dashboard, whose content is
published anyway, but VendorPath contains supplier PII handling and its
repository is deliberately private. Before moving it in, set **repository-level
permissions** on it rather than relying on the project default — Azure DevOps
supports this, but it has to be configured deliberately. If that is awkward under
your governance model, VendorPath is the one repository worth keeping separate.

**A naming point worth being explicit about.** "PMO EU Procurement" is the *programme*;
Commodity Dashboard and EU Indirect Supplier Finder are *projects* within it. The two do not have to map one-to-one
across systems: one Azure DevOps project named `PMO` holding several
repositories, and a separate Azure Resource Group **per project per
environment**. Please avoid creating a single Resource Group named
for the programme and then using it as the container for every project inside it —
the name would be wrong for every subsequent project, and Resource Groups cannot
be renamed.

This sharpens §11.4: if the repository is expected to live in the PMO Azure
DevOps project, we will migrate it from GitHub during phase 3.

---

## 8. Forward roadmap — what to secure now, what to provision later

This project is the first under the programme, not the last, and later projects
will not all be static dashboards. **VendorPath** — a supplier onboarding and
procurement ERP built on Next.js with a PostgreSQL database, an externally
facing supplier portal and integrations into Entra ID, SAP and D365 — is already
in development as the programme's second project. It is a materially larger
workload than this one, and the landing-zone decisions in §7 need to accommodate
it rather than be sized to a static dashboard.

**A separate programme-level plan covering both projects is provided alongside
this response** (`docs/azure-programme-plan.md`). This section states only the
principle and the triggers that apply to this project.

**Our position: ask for headroom now, hardware later.**

The two have opposite cost profiles, which is what makes the split obvious:

| | Cost to hold unused | Cost to add later |
| --- | --- | --- |
| **Structure and permission** — naming, RG layout, RBAC, budget envelope, service-catalogue approval, Entra groups, DNS parent | **Zero** | **High** — retrofitting a naming scheme or splitting a shared Resource Group means recreating resources and re-pointing every pipeline |
| **Provisioned resources** — App Service Plans, SQL Databases, API Management, Premium Functions | **Real monthly spend**, plus patching, vulnerability-scanning, access-review and audit obligations on something nobody uses | **Low** — minutes, provided the structure and permissions above already exist |

So we request the first row generously and the second row against a trigger.

### 8.1 Requested now — free to hold, expensive to retrofit

1. **Contributor RBAC for the project team on our own Resource Groups.** This is
   the single highest-value item in this document after SSO. With it, adding a
   Function App or a database to our own Resource Group when a project genuinely
   needs one takes minutes. Without it, every individual resource becomes a
   ticket with a lead time, which is what actually slows programmes down.
2. **A programme budget with alert thresholds** — for example an Azure Budget on
   the subscription with notifications at 50/80/100%. Given an agreed ceiling we
   can add small resources beneath it without a fresh approval round each time,
   and IT keeps a hard signal if anything runs away.
3. **Clarity on the service catalogue** — which Azure services are pre-approved
   for this subscription, and what the request process and lead time look like
   for one that is not. Knowing this now is worth more than provisioning
   anything, because it tells us what to design around.
4. **The naming convention and reserved project codes** (§7.2).
5. **Resource Group and subscription layout** (§7.1).
6. **The shared Log Analytics workspace** (§7.3, §8.4).
7. **Nested Entra ID security groups** (§7.3).
8. **The parent DNS domain** (§7.4).
9. **The tagging schema** (§7.5).
10. **Azure OpenAI access approval — if AI features are plausible within twelve
    months.** This one is an exception to "provision later": the access request
    and regional quota assignment are slow, involve a separate approval path,
    and are entirely independent of provisioning anything. Securing the approval
    early costs nothing and removes a long lead time from a future project.

### 8.2 Provisioned later, against a trigger already written down

| Service | Trigger | Documented in |
| --- | --- | --- |
| Function App (Flex Consumption) | A live or scheduled data refresh between quarters | §2 |
| App Service | A future project with genuine server-side code | §3 |
| Azure Database for PostgreSQL | Cross-quarter time series, a queryable API, or user-entered data. **Note:** the programme's database standard should be PostgreSQL Flexible Server rather than Azure SQL — VendorPath's schema is Postgres via Prisma, and one engine across the programme is cheaper to operate | §4 |
| Container Apps Job | A build that must run inside Azure, or any containerised workload | §6.5 |
| API Management | More than one consumer of a published API | §6.6 |
| Service Bus | Asynchronous work passing between two services | §6.6 |
| Azure OpenAI | Commentary drafting or natural-language Q&A over the reports | §6.6, §8.1 |
| Private endpoints + VNet | Policy mandate, or a project handling restricted data | §6.7, §7.3 |

Because sections 2 to 6 already state the condition for each of these, none of
them will arrive as a surprise. That is deliberate — it is far easier to get a
Function App approved in six months against a trigger IT has already read and
accepted than to justify one that appears without warning.

**One sizing note for the database case:** when a project does need a database,
start on a **burstable tier** (PostgreSQL Flexible Server `B1ms` or `B2s`) rather
than a provisioned general-purpose SKU. Burstable can be scaled up in place
without a migration, which removes most of the argument for pre-provisioning
capacity "just in case".

### 8.3 Why we are deliberately not over-requesting

Idle resources are not free, even on a cheap SKU:

- App Service Plans bill 24/7 regardless of traffic.
- Every provisioned resource enters the patching, vulnerability-scanning and
  access-review cycle, which is IT's cost rather than ours.
- Unused resources from a programme's first project make its *next* request
  harder to defend.

We would rather build a record of precise, justified requests. The trigger
conditions stated throughout this document are the mechanism for that, and they
are what make a fast "yes" possible later.

### 8.4 The one thing genuinely worth having from day one

If a shared Log Analytics workspace does not yet exist for the programme, **create it with
this project**. It is the one component that is materially better to have early:
telemetry not collected in month one cannot be backfilled in month six, every
later project attaches to it at no additional cost, and it is the foundation for
any programme-level view of how these tools are actually used.

---

## 9. Region and data residency

**Requested region: West Europe (Netherlands)**, with Germany West Central as
an acceptable alternative.

The dashboard carries EU procurement data with a German (Destatis) deep-dive
and an EU-27 audience across nine languages. Both environments should be in
the same region.

---

## 10. Summary — what we are asking for

| # | Resource | DEV | PROD |
| --- | --- | --- | --- |
| 1 | Azure Static Web App | Free | **Standard** |
| 2 | Storage Account (Standard LRS, Hot, Blob) | 1 | 1 |
| 3 | Key Vault (Standard) | 1 | 1 |
| 4 | Application Insights *(onto the shared PMO workspace, §7.3)* | 1 | 1 |
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

## 11. Questions back to IT

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
4. **Source control** — does the repository stay on GitHub, or move to a repo
   inside the PMO Azure DevOps project? This determines how CI/CD is wired
   (§7.6).
5. **Private endpoints** — mandated by policy, or optional? (§6.7)
6. **Custom domain** — can a parent domain be reserved for the programme, with
   a subdomain per project? (§7.4)
7. **Environment count** — is DEV + PROD acceptable, or does the landing-zone
   standard require four tiers? (§1)
8. **Naming convention & tagging** — please share the standard so we can
   pre-populate resource names, cost-centre and owner tags (§7.2, §7.5).
9. **Resource Group strategy** — one Resource Group per project per environment,
   or one shared across the PMO EU Procurement programme? We need the former, and this is
   difficult to change afterwards (§7.1).
10. **Project short code** — is `euproc` acceptable, and is `pmo` the programme
    code? This must be fixed before any storage account is created (§7.2).
11. **Team RBAC** — can the project team hold Contributor on its own Resource
    Groups, within an agreed budget? This determines whether future resources
    take minutes or a ticket (§8.1).
12. **Shared Log Analytics workspace** — does one already exist for the programme, or
    should this project create it? (§7.3, §8.4)
13. **Service catalogue** — which Azure services are pre-approved for this
    subscription, and what is the lead time to add one that is not? (§8.1)

---

## 12. Migration approach

| Phase | Work | Owner |
| --- | --- | --- |
| 1 | Resource Group + resources provisioned per §10 | IT |
| 2 | Entra ID app registration, security group, access model confirmed | IT |
| 3 | CI/CD pipeline wired from repository to Static Web App | Project |
| 4 | Vendor CDN assets locally if required by §11.3 | Project |
| 5 | Deploy to DEV, validate all 9 languages and both quarters | Project |
| 6 | Custom domain + TLS on PROD, SSO smoke test | IT + Project |
| 7 | Cut over, retire the public GitHub Pages site | Project |

**No data migration is required** — the entire application state is the
repository. Cutover is a deployment, not a migration, and is reversible by
re-enabling GitHub Pages.
