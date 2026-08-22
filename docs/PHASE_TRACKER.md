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

- [ ] **Phase C2**: Port Workflow Skeleton
  - [ ] Create workflow definitions
  - [ ] Test state transitions
  - [ ] Verify workflow in Port

- [x] **Phase C3**: Provider Docs Site ✅
  - [x] Start docs site server
  - [x] Test layout V1
  - [x] Test layout V2
  - [x] Test layout switching

- [ ] **Phase C4**: Bright Data Integration
  - [ ] Create scraper in Scraper Studio
  - [ ] Test extraction with layout V1
  - [ ] Test extraction with layout V2
  - [ ] Test self-healing

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

- [ ] **Phase C8**: Docs Self-Healing
  - [ ] Break docs layout
  - [ ] Trigger self-healing
  - [ ] Verify recovery

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

## Current Phase: C4 - Bright Data Integration

### Completed in Phase C3:
- ✅ Docs site server starts cleanly on port 8001 (`/health` returns healthy)
- ✅ Layout V1 and V2 both render via `/api/docs/pricing`
- ✅ `/api/docs/layout` POST endpoint switches versions deterministically; `/api/docs/layout/current` reflects state
- ✅ Verified V1/V2 use materially different selectors/class names/nesting (e.g. `.migration-section .field-change .old-field` vs `.breaking-changes-container .field-mapping .deprecated`)
- ✅ Verified human-visible text content is byte-identical between layouts (removed a footer string that leaked the layout version, which would have given away the switch to a scraper/judge)
- ✅ Reset to v1 as the default state after verification

### Next Steps (Phase C4):
1. Create Bright Data Scraper Studio scraper targeting `/api/docs/pricing`
2. Define required structured fields (provider, version, old/new field paths, migration guidance, changelog date)
3. Run extraction against docs-layout-v1, validate output
4. Persist scraper usage rules in coding-agent project rules (CLAUDE.md) per plan section 5
5. Confirm BRIGHTDATA_SCRAPER_ID once scraper is created (currently a placeholder in .env)
