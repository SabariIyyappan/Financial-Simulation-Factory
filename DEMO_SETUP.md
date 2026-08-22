# Demo setup — run this on the demo laptop

Everything runs on one machine. That is deliberate: the venue WiFi isolates clients, so
machine-to-machine traffic does not work. One laptop, all services on localhost.

Roughly 20 minutes from clone to rehearsal.

---

## 0. Prerequisites

| | Needed | Check |
|---|---|---|
| Node | **22 or newer** | `node -v` |
| Python | 3.10+ | `python --version` |
| Docker | running (SigNoz needs it) | `docker ps` |
| cloudflared | for the docs tunnel | `cloudflared --version` |

Node 22+ is not optional — the evaluation script uses `node:fs` `globSync`, added in 22.

If `cloudflared` is missing: `brew install cloudflared` (macOS),
`winget install --id Cloudflare.cloudflared` (Windows), or download from Cloudflare.

---

## 1. Clone and install

```bash
git clone https://github.com/SabariIyyappan/Financial-Simulation-Factory.git
cd Financial-Simulation-Factory
git checkout main
npm install
pip install -r requirements.txt
npm run build -w @api-guardian/telemetry
```

That last line matters — the app imports the telemetry package from `dist/`, so it must
be built before the app starts or module resolution fails.

---

## 2. Secrets

```bash
cp config/env.template .env
```

Then fill in `.env`. **Ask Kenil for the actual values** — they are not in the repo and
must not be committed.

| Variable | Where it comes from |
|---|---|
| `PORT_CLIENT_ID` / `PORT_CLIENT_SECRET` | Port → Settings → Credentials |
| `BRIGHTDATA_API_TOKEN` | Bright Data account |
| `BRIGHTDATA_COLLECTOR_ID` | the collector from Phase C4 (`c_…`) |
| `BRIGHTDATA_ZONE` | Web Unlocker zone name |
| `ANTHROPIC_API_KEY` | console.anthropic.com |

Leave the endpoint and threshold values as they ship — they are already correct for a
single-machine setup.

The evaluator reads its own file:

```bash
cp observability/evaluator/.env.example observability/evaluator/.env
```

and needs `SIGNOZ_API_KEY` (SigNoz UI → Settings → Service Accounts) plus
`SIGNOZ_QUERY_URL=http://localhost:8080`.

### Bright Data MCP

The hackathon brief calls out MCP explicitly, and visible MCP usage in the demo is worth
more than any equivalent REST call. `.mcp.json` at the repo root points at Bright Data's
**hosted** MCP server via `mcp-remote`, so it needs no Web Unlocker zone and no local
install — just `BRIGHTDATA_MCP_TOKEN` in `.env`.

That is a **different token** from `BRIGHTDATA_API_TOKEN`; the Python client uses the
latter, MCP uses the former. Ask Kenil for both.

Claude Code loads `.mcp.json` at startup and asks you to trust the project's MCP servers
the first time. So: set the token *first*, then start Claude Code from the repo root and
approve. Verify with:

```bash
claude mcp list
```

`brightdata` should show as connected. If Claude Code was already running when you set
the token, restart it — the config is read at startup only.

---

## 3. Bring up the services

Six terminals. Start them in this order — later ones depend on earlier ones.

```bash
# 1. SigNoz (wait ~90s for ClickHouse; UI at http://localhost:8080)
npm run signoz:up

# 2. Mock providers  → :4001
npm run dev:providers

# 3. The app         → :3000
npm run dev:app

# 4. Fitness evaluator → :8090
npm run evaluator:start

# 5. Provider docs site → :8001
python provider-docs-site/server.py

# 6. Tunnel for the docs site — Bright Data runs in the cloud and cannot see localhost
cloudflared tunnel --url http://localhost:8001
```

Copy the `https://….trycloudflare.com` URL that step 6 prints into `.env` as
`DOCS_PUBLIC_URL`, then restart anything already running that reads it.

**The tunnel URL changes every restart.** If Bright Data extraction returns empty during
rehearsal, this is the first thing to check.

---

## 4. Verify before rehearsing

Run all five. Every one should pass.

```bash
# a) telemetry reaches SigNoz — ships a real span, not just a port check
npx tsx scripts/check-telemetry.ts http://localhost:4318

# b) baseline snapshot: expect HTTP 200 in ~2.7s
curl "http://localhost:3000/api/snapshot?factoryRunId=SMOKE&candidateId=BASELINE&scenario=baseline-v1"

# c) the incident: expect HTTP 502, provider "pricing", SCHEMA_FIELD_MISSING
npm run demo:break-pricing
curl "http://localhost:3000/api/snapshot?factoryRunId=SMOKE&candidateId=BASELINE&scenario=pricing-v2-break"
npm run demo:reset

# d) test suites
npm test
pytest

# e) Bright Data extraction against the tunnel
python demo/scripts/run_scraper_pipeline.py --status
```

Then open SigNoz at http://localhost:8080 and confirm the baseline trace shows four
spans — `api_guardian.product_snapshot` with `provider.catalog`, `provider.pricing`,
`provider.availability` as children, running **sequentially** in the waterfall.

That staircase is the demo's central visual. If the spans overlap, someone parallelized
the app early and Scene 2 has nothing to fix.

---

## 5. Three settings that decide whether the demo works

**`AUTO_APPROVE=false`** — must stay false. Auto-approval removes the human gate, which
is the specific thing the judging criteria call out. The demo is stronger when you click
approve yourself.

**`USE_MOCK_EVALUATOR=false`** — must stay false. The mock returns fixture scores keyed
on the scenario *name*, so it reports PASS for anything labelled `optimized-v1` whether
or not the code was ever optimized. Real evaluation queries live SigNoz.

**Warm-up is built in.** Cold start measures ~1579ms against a 1600ms full-score
threshold — 21ms of headroom. `RealEvaluator` fires throwaway requests before opening the
evaluation window so the first compile does not land in the sample. Do not remove it: if
a cold request lands in the window, the parallel candidate scores 10 latency points
instead of 20, totals 80, and fails its own release gate on stage.

---

## 6. Demo runbook

**Scene 1 — healthy but slow (~45s).**
Open the app at localhost:3000, click *Build Product Snapshot*. ~2.7s. Open SigNoz, show
the sequential staircase. Run the factory: it scores 70 and **FAILS on latency**.

```bash
python demo/scripts/run_factory_loop.py --scenario baseline-v1
```

Say out loud: *nothing an LLM said produced that verdict — correctness is schema
validation and tests, latency is a measured p95.*

**Scene 2 — the factory repairs it (~60s).**
The agent identifies the serialized calls and parallelizes them. Re-evaluate: p95 drops
~2.7s → ~1.1s, score 70 → 90, decision PASS. Port moves the candidate to
`READY_FOR_APPROVAL` — **not** APPROVED. Click approve yourself. Show the release.

**Scene 3 — the provider breaks (~45s).**

```bash
npm run demo:break-pricing
```

Snapshot returns 502. In SigNoz, `provider.pricing` is red; click it and land on the
error log carrying `error.code=SCHEMA_FIELD_MISSING` at the same `trace_id`. That
click-through is the moment worth pausing on.

**Scene 4 — the docs move too (~60s).**

```bash
python demo/scripts/run_scraper_pipeline.py --switch v2
python demo/scripts/run_docs_selfheal.py
```

Extraction breaks, self-heal repairs the same collector, extraction recovers. Note that
the collector id is unchanged — it healed rather than being replaced.

**Scene 5 — repair with both evidence sources (~60s).**
The agent gets the SigNoz failure *and* the Bright Data migration guidance, patches the
Pricing adapter, tests pass, error rate returns to zero, human approves, release.

**Close (~15s).** Latency 2.7s → 1.1s. Pricing incident detected → repaired. Docs
scraper broken → self-healed. Two releases, both human-approved, full lineage in Port.

---

## If something breaks mid-demo

| Symptom | Cause | Fix |
|---|---|---|
| No traces in SigNoz | app started before SigNoz was ready | restart the app; look for `[telemetry] OTel SDK initialised` |
| App won't start, telemetry import error | `dist/` not built | `npm run build -w @api-guardian/telemetry` |
| Bright Data returns empty | tunnel URL rotated | restart cloudflared, update `DOCS_PUBLIC_URL`, restart |
| Evaluator errors "no traces in window" | queried before the batch flushed | it waits 12s; if it still fails, check `SIGNOZ_API_KEY` |
| Snapshot 502 unexpectedly | pricing left in V2 | `npm run demo:reset` |
| Score stuck at 70 after parallelizing | cold request in the window, or mock evaluator on | check `USE_MOCK_EVALUATOR=false`; re-run |

**Reset to a clean state between rehearsals:**

```bash
npm run demo:reset
python demo/scripts/run_scraper_pipeline.py --switch v1
```

---

## Known-good measurements

Verified on Person A's machine — use these to tell "different" from "broken".

| | Value |
|---|---|
| Baseline snapshot | 2727–2780 ms |
| Parallel, warm | p50 1136 ms · p95 1145 ms |
| Parallel, cold start | 1579 ms ← why warm-up exists |
| Baseline score | 70, FAIL on latency |
| Parallel score | 90, PASS |
| TS tests | 8 passing |
| Provider spans, baseline | catalog 704ms → pricing 905ms → availability 1104ms |

During the Pricing V2 incident the TypeScript tests still report **8/8 passing**. That is
correct and worth saying out loud: the adapter's unit contract is to *reject* V2, and it
does. The integration is what broke, and `tests.schema_valid=false` is what trips the
correctness gate. Otherwise "8/8 passing" during an incident reads as a broken suite.
