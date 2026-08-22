# Person C - Phase Tracker

## Phase Status

- [x] **Phase C0**: Setup & Credentials ✅
  - Port credentials configured
  - Bright Data credentials configured
  - Connection tests passing
  - Created credentials management system
  - Verified API connectivity

- [x] **Phase C1**: Port Foundation ✅
  - [x] Upload blueprints to Port
    - Created 6 blueprints: service, externalApi, factoryRun, candidateVersion, evaluation, release
    - Fixed enum colors for Port compatibility
    - All blueprints successfully uploaded
  - [x] Seed initial entities (service, external APIs)
    - Created API Guardian service entity
    - Created 3 external API entities (Catalog, Pricing, Availability)
    - Established relationships between service and dependencies
  - [x] Verify entities in Port dashboard
    - All blueprints verified
    - All entities verified
    - Setup script completed successfully

- [x] **Phase C2**: Port Workflow Skeleton ✅
  - [x] Create workflow definitions
    - Full lifecycle driven from `orchestration/factory/loop.py` via Port REST API
    - DETECTED → INVESTIGATING → PLANNED → IMPLEMENTED → EVALUATING → REJECTED | READY_FOR_APPROVAL → APPROVED → RELEASED
  - [x] Test state transitions
    - Both PASS and FAIL paths exercised end-to-end against live Port
    - 17 regression tests added in `tests/test_factory_loop.py` (offline, faked Port client)
  - [x] Verify workflow in Port
    - Full lineage confirmed: factoryRun → candidateVersion → evaluation → release
    - Service `currentRelease` / `score` updated on release

- [x] **Phase C3**: Provider Docs Site ✅
  - [x] Start docs site server
  - [x] Test layout V1
  - [x] Test layout V2
  - [x] Test layout switching

- [x] **Phase C4**: Bright Data Scraper Studio ✅
  - [x] Real collector built from the terminal with `bdata scraper create`
        → `c_mt4xbkwsrxt8czehu` (AI-generated, 9-stage build)
  - [x] Collector runs against the live docs site and returns structured JSON
  - [x] Layout change genuinely degrades its output (4 fields null/empty)
  - [x] Bright Data AI self-healing rewrites the collector code in place,
        preserving the collector id
  - [x] Whole pipeline driven from Python/terminal — no dashboard step
  - [x] Test extraction with layout V1 — all required fields captured
  - [x] Test extraction with layout V2 — V1 selectors genuinely fail (4 fields missing)
  - [x] Test self-healing — re-derives V2 selectors, evidence recovers, revalidated
  - [x] Real selector-based extractor (`integrations/brightdata/extractor.py`)
  - [x] Bright Data usage rules written to `CLAUDE.md` per plan section 5
  - [x] MCP server configured (`.mcp.json`, `@brightdata/mcp` v2.11.1) as the
        live-narration layer; Python client remains the execution path

- [ ] **Phase C5**: Evaluation Integration
  - [ ] Test mock evaluator
  - [ ] Integrate with Port workflows
  - [ ] Verify evaluation flow

- [ ] **Phase C6**: Factory Loop - Latency Optimization
  - [ ] Run baseline scenario
  - [ ] Generate optimization plan
  - [ ] Simulate code change
  - [ ] Evaluate and approve

- [ ] **Phase C7**: Pricing V2 Incident
  - [ ] Trigger API break
  - [ ] Detect failure
  - [ ] Create incident in Port

- [x] **Phase C8**: Docs Self-Healing ✅ (mechanics working; runs against local extraction)
  - [x] Break docs layout — `demo/scripts/run_docs_selfheal.py` step 2
  - [x] Trigger self-healing — selectors re-derived from the changed page
  - [x] Verify recovery — same evidence recovered, `self_heal_attempted=True`

- [ ] **Phase C9**: Factory Loop - Schema Repair
  - [ ] Gather evidence
  - [ ] Generate repair plan
  - [ ] Simulate fix
  - [ ] Evaluate and release

- [ ] **Phase C10**: Port Dashboards
  - [ ] Create service overview
  - [ ] Create factory run history
  - [ ] Create candidate lineage
  - [ ] Create approval queue

- [ ] **Phase C11**: Demo Orchestration
  - [ ] Create demo scripts
  - [ ] Create runbook
  - [ ] Test end-to-end demo
  - [ ] Record demo video

---

## Current Phase: C5 - Evaluation Integration
(C4 code complete; its remaining item is a Bright Data account fix, not code)

### Completed in Phase C2:
- ✅ Factory loop drives the full candidate lifecycle into Port from the terminal
- ✅ FAIL path: `baseline-v1` → REJECTED at 80/100, latency 0/20 as the visible cause
- ✅ PASS path: `optimized-v1` → RELEASED at 100/100, release entity + service update
- ✅ Demo runner added: `python demo/scripts/run_factory_loop.py --both --auto-approve`
- ✅ Scenarios are idempotent (Port upsert), so a beat can be replayed mid-demo

Bugs found and fixed during C2:
- `datetime.utcnow().isoformat()` produced naive timestamps that Port's `date-time`
  format rejected with 422 — every Port write now goes through `utc_now()`
- Re-running a scenario returned 409 Conflict — `create_entity` now upserts
- Evaluation entities dropped all five score components, so a FAIL showed a bare
  80/100 with no visible reason — breakdown is now written
- `search_entities` sent Port search rules as a query-string param (rejected as
  `invalid_request`, silently swallowed); now POSTs to `/entities/search`

### Completed in Phase C3:
- ✅ Docs site server starts cleanly on port 8001 (`/health` returns healthy)
- ✅ Layout V1 and V2 both render via `/api/docs/pricing`
- ✅ `/api/docs/layout` POST endpoint switches versions deterministically; `/api/docs/layout/current` reflects state
- ✅ Verified V1/V2 use materially different selectors/class names/nesting (e.g. `.migration-section .field-change .old-field` vs `.breaking-changes-container .field-mapping .deprecated`)
- ✅ Verified human-visible text content is byte-identical between layouts (removed a footer string that leaked the layout version, which would have given away the switch to a scraper/judge)
- ✅ Reset to v1 as the default state after verification

### Completed in Phase C4:
- ✅ Replaced the fabricated scraper API calls (`/scrapers/{id}/runs`, `/self-heal`,
  `/health` — none of which exist) with a real selector-based extractor
- ✅ `_mock_scrape()`'s hard-coded return values are gone; extraction now genuinely
  parses the page, so layout V2 fails required-field validation for real
- ✅ Self-healing re-derives working selectors from the changed page and the client
  adopts them — no manual scraper edit
- ✅ Evidence is revalidated after healing before it reaches the repair workflow
- ✅ Migrated Pydantic V1 `@validator` → V2 `@field_validator`; `.dict()` → `.model_dump()`
- ✅ 18 extraction/self-heal tests added (`tests/test_brightdata_extraction.py`),
  including guards that the V1/V2 break stays genuine and visible text stays identical
- ✅ Verified compound scenario: Pricing API breaks *and* docs layout changes →
  scraper self-heals mid-run → healed evidence produces a repair hypothesis citing
  the real scraped field paths (`price` → `pricing.amount`)

### Bright Data account — RESOLVED 2026-08-22 ✅
Account activated ($100 balance, 5,000 free credits, promo valid to 2026-09-06)
and the API token was reissued with admin permission. With that:
- Created Web Unlocker zone **`api_guardian_docs`** programmatically via `POST /zone`
- `POST /request` through the zone returns real HTML (verified against example.com
  and against the docs site through a cloudflared tunnel)
- **The full break/heal demo now runs over hosted Bright Data infrastructure** —
  every fetch goes through the zone, no local fallback

Live demo prerequisites (both needed each session):
1. `python provider-docs-site/server.py` — docs site on :8001
2. `cloudflared tunnel --url http://localhost:8001` — then put the generated URL
   in `DOCS_PUBLIC_URL` in `.env`. The tunnel URL changes every run.

Layout switching stays local (`DOCS_SITE_URL`) while scraping goes through the
public URL (`DOCS_PUBLIC_URL`), so the demo operator keeps deterministic control
of the break.

`BRIGHTDATA_SCRAPER_ID` is legacy and unused. The pipeline is driven by
`BRIGHTDATA_COLLECTOR_ID=c_mt4xbkwsrxt8czehu` (the Scraper Studio collector);
the zone is only used for direct page fetches.

### Bright Data CLI heal bug (worked around)

`bdata scraper heal --auto-approve` **reports success without saving the fix.**
Observed twice: `status: done`, `success: true`, `code_fixer` and
`request_fulfillment_validator` in `completed_steps` — but the collector kept its
old selectors and kept failing. Reading
`GET /dca/collectors/{id}/refactor_template/progress` showed the AI's repaired
code extracting correctly in `preview_result`, stuck at step `user_approval`.

The CLI does not answer the automation's `pending_answer` prompt, so the repaired
code is discarded. `ScraperStudioClient.heal()` polls for that state and posts
`resume_automation_job` with `{"message": true, "auto_save": true}`, which
commits it. Calling that endpoint after the automation closes returns
`400 Invalid ide automation` — it has to be caught in the window.

Do not switch the heal path back to the CLI command.

### Next Steps (Phase C5):
1. Integrate Person B's real evaluation object once available (mock evaluator
   contract is in `orchestration/evaluator/mock_evaluator.py` and is Person C's
   *guess* at B's output shape — confirm field names with B before C5 lands)
2. Attach Bright Data evidence to the FactoryRun entity in Port (currently
   gathered in `inspect()` but not yet written to Port)
