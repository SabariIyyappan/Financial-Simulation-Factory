# API Guardian — project rules

Three surfaces, one repo, no-conflict ownership (`MASTER_PLAN.md` §6):

| Surface | Owner | Stack | Paths |
|---|---|---|---|
| App under repair + mock providers | Person A | TypeScript | `apps/`, `services/`, `packages/domain-contracts`, `packages/provider-clients`, `scripts/` |
| Telemetry, SigNoz, fitness evaluator | Person B | TypeScript | `packages/telemetry/`, `observability/` |
| Port, Bright Data, orchestration | Person C | Python | `port/`, `integrations/`, `provider-docs-site/`, `orchestration/`, `demo/` |

**Do not edit another surface.** Consume its outputs. If something there is broken,
report it rather than patching across the boundary — a silent cross-boundary fix
diverges branches right before a demo.

Mixed TS/Python is deliberate and fine: the Python orchestrator drives the TypeScript
services over HTTP. Do not rewrite either side to match the other.

---

## Person C — Bright Data & provider docs (authoritative)

## Provider documentation retrieval

**Bright Data Scraper Studio is the approved method for retrieving external
provider documentation and changelogs.** Everything the factory believes about a
provider's schema migration must come through it.

### The collector

| | |
|---|---|
| Collector ID | `c_mt4xbkwsrxt8czehu` (`BRIGHTDATA_COLLECTOR_ID`) |
| Name | `api-guardian-pricing-docs` |
| Target | `$DOCS_PUBLIC_URL/api/docs/pricing` |
| Web Unlocker zone | `api_guardian_docs` (`BRIGHTDATA_ZONE`) |
| Output fields | `provider_name`, `api_version`, `migration_guidance`, `changelog_date`, `field_mappings[{old_field,new_field}]` |
| IDE | https://brightdata.com/cp/scrapers/c_mt4xbkwsrxt8czehu |

Self-healing preserves the collector id, so **never create a replacement
collector when this one breaks** — heal it. A new id would orphan every
reference to it.

### Terminal commands

Everything runs through the `bdata` CLI; no dashboard visit is needed.

```bash
# health / extract / full break-heal-recover demo
python demo/scripts/run_scraper_pipeline.py --status
python demo/scripts/run_scraper_pipeline.py --switch v2
python demo/scripts/run_scraper_pipeline.py

# the underlying CLI
npx -y -p @brightdata/cli bdata scraper run  <collector_id> <url> --pretty -k $BRIGHTDATA_API_TOKEN
npx -y -p @brightdata/cli bdata scraper create <url> "<description>" --name <name>
```

Rebuild the collector from scratch only if it is lost entirely:
`python demo/scripts/run_scraper_pipeline.py --create`

### Healing must go through the API, not `bdata scraper heal`

`bdata scraper heal --auto-approve` **reports success without saving the fix.**
The AI rewrites the code correctly and it passes validation, but the automation
stops at a `pending_answer` approval step that the CLI does not answer, so the
collector keeps its old selectors and the next run still fails.

`ScraperStudioClient.heal()` drives the REST API instead and polls for that
window:

1. `POST /dca/collectors/{id}/refactor_template` with `{"prompt": "<what broke>"}`
2. poll `GET /dca/collectors/{id}/refactor_template/progress`
3. when `status == "pending_answer"`, `POST /dca/collectors/{id}/resume_automation_job`
   with `{"message": true, "auto_save": true}` — **this is what commits the code**
4. re-run and revalidate

Do not switch this back to the CLI heal command.

### Writing heal prompts

Describe the **symptom**, not the fix. Say which fields came back null or empty
and that the same information is still on the page under different markup; let
Bright Data's AI inspect the live page and derive the selectors. Passing our own
CSS selectors produced a worse result. Keep prompts under 1000 characters, and
make sure the page is serving the new markup when healing runs — the AI reads it
live.

### Do not substitute another retrieval method

Do not replace Bright Data with `requests.get` + ad-hoc parsing, Playwright,
Selenium, an LLM asked to recall the provider's docs, or a hard-coded fixture —
**including when the scraper is failing.** A failing scraper is a signal to
repair the scraper, not to route around it. Silently swapping in a different
fetch path produces evidence that no longer reflects what the provider actually
published, which is the failure mode this system exists to catch.

If extraction cannot be repaired, the correct outcome is *no evidence* and a
visible failure — not substitute evidence from another source.

### Required output schema

The collector returns these fields. All five are required — a record missing any
of them means the collector has gone stale and must be healed:

| Collector field | Meaning |
|---|---|
| `provider_name` | Provider name |
| `api_version` | Current API version |
| `migration_guidance` | How to migrate |
| `changelog_date` | Date of the change (ISO 8601) |
| `field_mappings` | List of `{old_field, new_field}` path moves |

`ScraperStudioClient.to_migration_evidence()` reshapes that record into the
factory's contract, naming the price and currency moves explicitly and carrying
`selectors_used: "scraper-studio:<collector_id>"` for provenance.

### Validation is mandatory

`check_health()` enforces the required-field contract on every run, and
`extract_with_self_healing()` revalidates after a heal. Evidence that fails
validation must not be passed to the coding agent, written to Port as fact, or
used to justify a code change.

### On invalid or missing extraction

Follow this order — it is what
[`extract_with_self_healing()`](integrations/brightdata/scraper_studio.py)
implements:

1. Detect the failure via required-field validation, not by waiting for a crash.
   A collector that returns a record with null or empty fields has failed.
2. Heal the collector through the API flow described above.
3. Re-run the collector.
4. **Revalidate.** A healed scrape is not trusted until it passes the same gate
   as the original.
5. If it is still degraded, yield **no evidence**. Never fall back to stale or
   partial data.

Never edit the collector's code by hand — self-healing must be seen to do it.

### Local extraction is a fallback, not the pipeline

[integrations/brightdata/extractor.py](integrations/brightdata/extractor.py)
holds CSS selector sets that parse the docs locally. It predates the Scraper
Studio collector and exists only as an offline path for tests and for demos with
no network. **It is not the data pipeline** — a hardcoded parser cannot notice
that the web changed. Prefer `ScraperStudioClient`; reach for the local
extractor only when there is no Bright Data access at all, and say so plainly
when reporting results.

## Bright Data account

The pipeline needs an **activated** account and an API token with **admin**
permission — a read-only token cannot create zones or heal collectors. Required
environment:

| Variable | Purpose |
|---|---|
| `BRIGHTDATA_API_TOKEN` | Admin-scoped token |
| `BRIGHTDATA_COLLECTOR_ID` | The Scraper Studio collector (`c_*`) |
| `BRIGHTDATA_ZONE` | Web Unlocker zone, used for direct page fetches |
| `DOCS_PUBLIC_URL` | Public tunnel URL Bright Data scrapes |

`BRIGHTDATA_SCRAPER_ID` is legacy and unused — the collector id is what matters.

### Running the demo

The docs site is on localhost, which Bright Data's cloud cannot reach, so a
tunnel is required each session:

```bash
python provider-docs-site/server.py               # terminal 1
cloudflared tunnel --url http://localhost:8001    # terminal 2
```

Put the generated `*.trycloudflare.com` URL in `DOCS_PUBLIC_URL`. It changes on
every tunnel restart. Layout switching goes to `DOCS_SITE_URL` (localhost) while
scraping goes to `DOCS_PUBLIC_URL`, keeping the break under local control.

## Person C — Port entity writes

## Port entity writes

Every timestamp written to Port must go through `utc_now()` in
[integrations/port/client.py](integrations/port/client.py). Port's `date-time`
format rejects naive timestamps, and `datetime.utcnow().isoformat()` produces
them.

Entity creation upserts by default so a demo scenario can be replayed without
hitting a 409 conflict.

---

## Person A — app, mock providers, adapters


```
packages/
  domain-contracts/     Shared TS types: ProductSnapshot, provider payload shapes (V1/V2)
  provider-clients/     Adapters: Catalog / Pricing / Availability. Pricing V1 adapter must
                         fail CLEARLY on V2 input — do not make it silently coerce V2.
  telemetry/            PERSON B'S PACKAGE. Real OTel/SigNoz export. Do not edit — if the
                         API needs to change, that's a contract discussion with B.
services/
  mock-providers/       Standalone HTTP server: Catalog (~700ms), Pricing (~900ms),
                         Availability (~1100ms). Exposes deterministic mode control
                         (POST /control/pricing-mode) — this IS the "external world changing"
                         the whole demo depends on. Never make it non-deterministic.
apps/
  api-guardian/          Next.js app: Product Snapshot endpoint + thin operator dashboard.
                         src/instrumentation.ts boots B's OTel SDK (must live under src/,
                         Next does not pick it up from the app root when src/ exists).
observability/          PERSON B'S AREA. SigNoz docker stack, evaluator service, frozen
                         contracts. Read observability/contracts/, don't edit it.
*.md at repo root       The frozen three-way spec. Do not edit.
scripts/
  run-evaluation.ts      Produces the evaluation-input.json artifact Person B's evaluator
                         consumes (Contract C in MASTER_PLAN.md).
  demo-control.ts        CLI to flip pricing mode / reset state without touching JSON by hand.
```

## Hard rules (from PERSON_A_APP_AND_MOCK_APIS.md section 12 — do not relax these)

1. Follow `PERSON_A_APP_AND_MOCK_APIS.md` as the source of truth for this
   surface. Don't redesign the architecture without an explicit reason discussed with
   the team.
2. Do not edit Person B's or Person C's owned areas. `packages/telemetry/` and
   `observability/` are Person B's — merged in and working; consume their API, don't
   change it. Port blueprints/workflows and Bright Data scraping are Person C's and
   aren't in this repo yet.
3. **Do not prematurely parallelize the baseline `apps/api-guardian` provider calls.**
   Sequential Catalog → Pricing → Availability is intentional — it's the whole reason
   the first AVO-lite repair (sequential → parallel) has something to fix. The
   parallelization is supposed to happen live, as a candidate change, during the demo.
4. **Do not make the Pricing V1 adapter accept V2 payloads.** The V1 adapter must fail
   clearly (a typed error, not a silent wrong value) when it receives the nested
   `pricing.amount` / `pricing.currency` shape. That failure is the second AVO-lite
   repair's entire premise.
5. Preserve deterministic failure modes. `services/mock-providers` must always give the
   same output for the same input in the same mode — no randomness, no real network
   calls to anything outside this repo.
6. Latency is proven with SigNoz telemetry (Person B's job), not with unit test
   assertions. Don't write a test that asserts on wall-clock timing.
7. Prefer small, reviewable commits per phase. Stop at each phase's exit criteria
   (see the Person A doc, section 8) before moving to the next.

## Local dev

```bash
npm install
npm run dev:providers   # mock-providers on :4001
npm run dev:app         # Next.js app on :3000, calls mock-providers
```

`apps/api-guardian/.env.local` (copy from `.env.example`): `MOCK_PROVIDERS_URL=http://localhost:4001`

## Conventions

- TypeScript strict everywhere. No `any` without narrowing immediately.
- No comments explaining *what* — only *why*, and only when non-obvious (e.g. why the
  Pricing V1 adapter must reject V2 rather than coerce it).
- Every provider call goes through Person B's `withProviderCall`, and the whole snapshot
  through `withProductSnapshot`. Never call a provider outside those wrappers — an
  unwrapped call is invisible to SigNoz, and the fitness function scores observability
  completeness.
- Adapter failures must call `logProviderError` **inside** the active span (see the inner
  try/catch in `snapshot.ts`). Logging after the span closes loses `trace_id`/`span_id`,
  which is what makes a failure traceable back to a request.
- Two tsconfig bases on purpose: `tsconfig.base.json` (NodeNext → `dist`) is Person B's,
  for packages that compile; `tsconfig.app.json` (bundler, `noEmit`) is Person A's, for
  packages that ship raw TS. Extend the right one; don't merge them.
