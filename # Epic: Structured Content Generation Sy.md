# Epic: Structured Content Generation System

**Client:** Serinn Labs  
**Contractor:** Foster Young LLC  
**Phase:** 1  
**Test Category:** MLB (Sports)  
**Target Delivery:** 5 weeks from inputs received  
**Plan status:** Office hours formalized (2026-04-13) — premises locked; alternatives and risks recorded below. **Implementation approach locked: B (2026-04-13).**

**Implementation tracking:** Rollup table and task checklists live under [Implementation progress](#implementation-progress) (update as epics ship).

---

## Overview

A locally-run Python application that transforms structured source input files (schedules, rosters, stat sheets) into fully populated, upload-ready CSV rows conforming to the client's schema. The system exposes a lightweight local web UI so the client or a team member can drop in files, configure parameters, and export a clean CSV — no terminal required after initial setup.

The architecture is modular: MLB sports is the first implemented category, but the system is designed so that new categories (markets, entertainment, news) can be added by dropping in a new input package and template config without touching core logic.

---

## Deliverable Summary

- Runnable Python application (local)
- Lightweight local web UI (browser-based, no deployment)
- Template and config system for question generation
- CSV export matching client upload schema
- Full documentation + setup guide
- Recorded walkthrough session

---

## Output Schema

Every generated row must conform to this structure:

| Field           | Format                                          |
| --------------- | ----------------------------------------------- |
| Category ID     | Provided via config (system-assigned on upload) |
| Subcategory     | String (e.g. "MLB")                             |
| Event           | String (e.g. "Mets vs Yankees")                 |
| Question        | String                                          |
| Answer Type     | "yes_no" or "multiple_choice"                   |
| Answer Options  | Pipe-delimited string (e.g. "Mets\|\|Yankees")  |
| Start Date      | ISO 8601 (e.g. 2026-05-14T19:10:00)             |
| Expiration Date | ISO 8601                                        |
| Resolution Date | ISO 8601                                        |
| Priority Flag   | "true" or "false"                               |

---

## System Architecture

```
INPUT FILES                CONFIG
(schedule, stats)    +   (templates, rules)
        |                       |
        └──────────┬────────────┘
                   ▼
          INPUT PARSER LAYER
     (normalizes + joins files)
                   |
                   ▼
       CONTROLLED GENERATION
        (LLM via OpenAI API)
                   |
                   ▼
         BATCH STRATEGY LAYER
      (50-200 rows per API call)
                   |
                   ▼
           LIGHT DEDUP + QA
      (remove dupes, schema checks)
                   |
                   ▼
          CSV EXPORT + UPLOAD
```

---

## Epic Breakdown

---

## Implementation progress

**Convention:** Keep the rollup table current as epics complete. For finished epics, task subsections use Markdown checklists (`[x]` / `[ ]`). Update this file when work ships so the doc stays the single source of truth for status.

| Epic | Topic | Status | Notes |
|------|-------|--------|-------|
| 1 | Project Setup and Environment | **Complete** | `requirements.txt`, `config/settings.yaml`, `main.py`, Flask UI (`ui/`), README setup, `.env.example`; `core/config.py` loads YAML + optional `settings.local.yaml` + `OPENAI_API_KEY` |
| 2 | Input Parser Layer | Not started | |
| 3 | Template and Config System | **Complete** | `templates/*.json` (6 MLB + 3 stubs); `core/template_config/` schema + loader; `templates_directory` in `config/settings.yaml`; `tests/test_templates.py` |
| 4 | Date Logic Layer | Not started | |
| 5 | Controlled Generation Layer | Not started | |
| 6 | Deduplication and QA Layer | Not started | |
| 7 | CSV Export | Not started | |
| 8 | Local Web UI | Not started | |
| 9 | Documentation and Handoff | Not started | |

**Last updated:** 2026-04-14 (EPIC 3 marked complete)

---

### EPIC 1 — Project Setup and Environment

**Goal:** Get the project running locally end to end before any logic is built.

**Status:** **Complete** (2026-04-14)

#### Task 1.1 — Repository and folder structure

- [x] Initialize project repo in Cursor
- [x] Define folder structure:
  ```
  /inputs          # user drops source files here
  /outputs         # generated CSVs land here
  /templates       # question template configs (JSON)
  /config          # global config file (YAML)
  /core            # generation, parsing, QA logic
  /ui              # Flask app and HTML front end
  main.py          # entry point
  requirements.txt
  README.md
  ```

#### Task 1.2 — Dependencies and requirements.txt

- [x] Python 3.10+ (required; documented in README)
- [x] `openai` — LLM API calls
- [x] `pandas` — input file parsing and CSV export
- [x] `openpyxl` — xlsx reading
- [x] `flask` — local web UI
- [x] `pyyaml` — config file parsing
- [x] `python-dateutil` — date arithmetic
- [x] `jinja2` — prompt templating

#### Task 1.3 — Python installation documentation

- [x] Write a setup section in README covering:
  - [x] How to check if Python is installed (`python --version`)
  - [x] Where to download Python 3.10+ (python.org)
  - [x] How to create a virtual environment (`python -m venv venv`)
  - [x] How to activate it (Mac/Linux vs Windows)
  - [x] How to install dependencies (`pip install -r requirements.txt`)
  - [x] How to add the OpenAI API key to environment or config

#### Task 1.4 — Global config file (config/settings.yaml)

- [x] Define all user-editable parameters in one place (committed `config/settings.yaml`; optional gitignored `config/settings.local.yaml`; `OPENAI_API_KEY` env override implemented in `core/config.py`):
  ```yaml
  openai_api_key: ""
  model: "gpt-5.4"
  category_id: ""
  date_filter:
    start: "2026-05-15"
    end: "2026-06-01"
  batch_size: 100
  ```

---

### EPIC 2 — Input Parser Layer

**Goal:** Ingest any structured input file and normalize it into a standard internal format the generation layer can consume regardless of category.

#### Task 2.1 — Abstract input parser interface

- Define a base `InputParser` class with standard methods:
  - `load(filepath)` — reads the file
  - `normalize()` — returns a list of standardized event dicts
- All category-specific parsers inherit from this base

#### Task 2.2 — MLB schedule parser

- Reads `inputs/schedule.xlsx`
- Combines `event_date` and `Event_time` columns into a single datetime
- Applies date range filter from config
- Outputs normalized event records:
  ```json
  {
    "event_id": "MLB000657",
    "home_team": "Athletics",
    "away_team": "Giants",
    "event_datetime": "2026-05-15T21:40:00",
    "subcategory": "MLB"
  }
  ```

#### Task 2.3 — MLB player stats parser

- Reads `inputs/stats.xlsx`, uses 2026 sheet as source of truth for team assignment
- Filters out any rows where team is "2TM" (multi-team, ambiguous)
- Applies team name normalization map (full name → abbreviation):
  ```python
  TEAM_MAP = {
    "Mets": "NYM", "Yankees": "NYY", "Dodgers": "LAD",
    "Braves": "ATL", "Athletics": "ATH", "Giants": "SFG",
    # ... all 30 teams
  }
  ```
- Exposes a method `get_top_players(team, stat, n)` that returns top N players for a given team and stat column

#### Task 2.4 — Input validator

- On load, check that required columns are present
- Warn if date range yields zero rows
- Warn if any team in the schedule has no matching players in the stats file
- Surface errors clearly so the user knows what to fix before running

---

### EPIC 3 — Template and Config System

**Goal:** Define all question generation logic in config files, not in code, so new categories can be added without a code change.

**Status:** **Complete** (2026-04-14)

#### Task 3.1 — Template schema definition

- [x] Each template is a JSON file in `/templates`
- [x] Standard template fields:
  ```json
  {
    "id": "mlb_game_winner",
    "subcategory": "MLB",
    "question_family": "event",
    "question": "Who will win {home_team} vs {away_team}?",
    "answer_type": "multiple_choice",
    "answer_options": "{home_team}||{away_team}",
    "priority": "true",
    "requires_entities": false
  }
  ```
- [x] Entity-based templates include additional fields:
  ```json
  {
    "id": "mlb_home_run",
    "question_family": "entity_stat",
    "question": "Who will hit a home run?",
    "answer_type": "multiple_choice",
    "stat_column": "HR",
    "top_n_per_team": 2,
    "priority": "false",
    "requires_entities": true
  }
  ```

#### Task 3.2 — MLB Phase 1 templates (game-level)

- [x] Template: Game Winner (`mlb_game_winner.json`)
- [x] Template: Win by more than 2 runs (yes/no) (`mlb_win_margin_2.json`)
- [x] Template: Total runs exceed 8.5 (yes/no) (`mlb_total_runs_over_8_5.json`)

#### Task 3.3 — MLB Phase 1 templates (player/stat-level)

- [x] Template: Who will hit a home run? (HR, top 2 per team) (`mlb_home_run.json`)
- [x] Template: Which player will record an RBI? (RBI, top 2 per team) (`mlb_rbi.json`)
- [x] Template: Who is more likely to steal a base? (SB, top 2 per team) (`mlb_steal_base.json`)

#### Task 3.4 — Stub templates for future categories

- [x] Create placeholder template files for markets, news, entertainment (`*_placeholder.json`)
- [x] Same schema, placeholder values
- [x] Comment in each (`_comment`): "extend by adding question and input package definition"

---

### EPIC 4 — Date Logic Layer

**Goal:** Deterministically compute all three date fields from event datetime and config rules.

#### Task 4.1 — Date rule engine

- Implement as a standalone function, not baked into generation
- Rules (per client spec):
  - `start_date` = event_datetime - 24 hours
  - `expiration_date` = event_datetime
  - `resolution_date` = event_datetime + 4 hours
- Output format: ISO 8601 without timezone offset (per client example)
- Make lead/lag values configurable in settings.yaml so they can be changed per category without code changes

---

### EPIC 5 — Controlled Generation Layer

**Goal:** Use the OpenAI API to generate clean, well-worded question text within the structure defined by templates. The LLM handles natural language quality — phrasing, player name handling, grammatical cleanup — but does not invent question structures. All question types, answer formats, and priority rules are defined by templates and config.

**Confirmed approach (Phase 1):** Template-driven (Option A). The LLM is used within templates, not instead of them. Architecture should leave a hook for a future dynamic generation mode without requiring a rewrite.

#### Task 5.1 — Prompt builder

- Takes a template + normalized event record and builds a structured prompt
- For event-level questions: slots in home_team, away_team, event values and instructs the LLM to produce clean, natural-sounding question text matching the template structure
- For entity questions: includes the resolved player list in the prompt context and instructs the LLM to construct answer options and wording cleanly
- System prompt enforces:
  - Output format: JSON array of rows, one per question
  - Do not invent new question types — only produce output conforming to the supplied template
  - Answer options must exactly match the entities provided — no hallucinated player names
- Include a `generation_mode` field in the prompt config (set to `"template"` for Phase 1) so a future `"dynamic"` mode can be added without restructuring the prompt builder

#### Task 5.2 — Batch execution

- Groups events into batches of N (configurable, default 100)
- Sends one API call per batch
- Parses JSON response back into row dicts
- Handles API errors gracefully — logs failed batches, continues processing, reports at end

#### Task 5.3 — Output row assembly

- For each generated question, assembles the full output row:
  - Pulls category_id from config
  - Pulls subcategory from template
  - Constructs event string from event record
  - Inserts LLM-generated question text
  - Inserts answer type and options (from template or entity resolution)
  - Computes date fields via date rule engine
  - Sets priority flag from template

#### Task 5.4 — Token cost logging

- After each run, log approximate token usage and estimated cost to console
- Keeps the client informed without surprises on the API bill

---

### EPIC 6 — Deduplication and QA Layer

**Goal:** Catch bad output before it hits the CSV.

#### Task 6.1 — Deduplication

- Hash each row on (subcategory + event + question)
- Remove exact duplicates
- Flag near-duplicates (same event, similar question text) for review — write to a separate `flagged.csv` rather than silently dropping

#### Task 6.2 — Schema validation

- Check every row has all required fields populated
- Validate answer_type is exactly "yes_no" or "multiple_choice"
- Validate date fields parse as valid ISO 8601
- Validate priority_flag is "true" or "false"
- Any row failing validation is written to `outputs/errors.csv` with a reason column

#### Task 6.3 — QA summary report

- After each run, print a summary to console:
  - Total rows generated
  - Rows passed validation
  - Rows flagged as near-duplicate
  - Rows written to errors
  - Estimated API cost

---

### EPIC 7 — CSV Export

**Goal:** Write a clean, upload-ready CSV with correct column names and formatting.

#### Task 7.1 — CSV writer

- Column order matches client schema exactly
- No index column
- UTF-8 encoding
- Output filename: `outputs/generated_{subcategory}_{date_window}_{timestamp}.csv`

#### Task 7.2 — Output directory management

- Auto-create `/outputs` if it doesn't exist
- Never overwrite a previous output — always timestamp the filename

---

### EPIC 8 — Local Web UI

**Goal:** Wrap the script in a minimal browser-based interface so the client can run it without using the terminal after initial setup.

#### Task 8.1 — Flask app skeleton

- Single-page app served at `localhost:5000`
- Routes:
  - `GET /` — main UI
  - `POST /run` — triggers generation run
  - `GET /download/<filename>` — serves output CSV

#### Task 8.2 — UI: file upload

- Two file drop zones: Schedule and Stats
- Accepts .xlsx files
- Files saved to `/inputs` on upload

#### Task 8.3 — UI: config panel

- Editable fields rendered from settings.yaml:
  - Date range (start / end)
  - Category / subcategory
  - Top N per team (for entity questions)
  - Template toggles (checkboxes to enable/disable each template)
- Changes written back to settings.yaml on run

#### Task 8.4 — UI: run and output

- "Generate" button triggers the pipeline
- Progress indicator while running
- On completion: summary stats displayed (rows generated, errors, cost estimate)
- Download button for the output CSV
- Download button for errors.csv if any errors exist

#### Task 8.5 — UI: basic styling

- Clean, minimal, functional
- No external dependencies — plain HTML/CSS only
- Should work in any modern browser

---

### EPIC 9 — Documentation and Handoff

**Goal:** Client or intern can set up and run the system independently without help.

#### Task 9.1 — README.md

- What the system does (one paragraph)
- Prerequisites: Python 3.10+, OpenAI API key
- Python installation instructions (Mac, Windows)
- Setup steps (clone/download, venv, pip install)
- How to add API key
- How to start the app (`python main.py`)
- How to use the UI
- How to add a new category (pointer to templates folder)
- Troubleshooting section (common errors and fixes)

#### Task 9.2 — Template authoring guide

- How to write a new template JSON
- Field definitions and valid values
- Event-level vs entity-stat template differences
- Example: adding a new sports subcategory
- Example: adding a markets category

#### Task 9.3 — Recorded walkthrough

- Screen recording covering:
  - Initial setup from scratch
  - Loading the MLB files
  - Running a generation job
  - Reviewing output and errors
  - How to adjust config and re-run

---

## Out of Scope (Phase 1)

- Live deployed service
- Real-time data fetching
- Deep third-party API integrations beyond OpenAI
- Production infrastructure
- Automated scheduling or cron-based runs
- User authentication

---

## Definition of Done

Phase 1 is complete when:

- The system accepts the MLB schedule and stats files as inputs
- Runs end to end and produces a valid CSV matching the client schema
- All three game-level templates and all three player-stat templates generate correct output
- Date fields are correctly computed for all rows
- QA layer catches and reports schema errors
- UI allows file upload, config edit, run, and CSV download without terminal
- README allows a non-technical user to set up and run the system from scratch
- Recorded walkthrough is delivered

---

## Office Hours — Plan Formalization (GStack)

*Session mode: contract delivery (client + fixed scope). The Epic already contained a complete execution plan; interactive YC-style demand discovery was skipped in favor of premise check, alternatives, and risk pass.*

### Context

- **Branch / repo:** `main` in workspace; application code not yet present — this document is the source of truth for scope.
- **Framing:** Serinn Labs needs a **local** pipeline from spreadsheets → validated CSV rows matching their upload schema, with **templates in config** so MLB is first category, not the only architecture.

### Landscape (Search Before Building)

| Layer | Takeaway |
| ----- | -------- |
| **1 — Tried and true** | Separate ingestion from generation; batch work in chunks; validate every row against a schema; never trust raw LLM text for IDs/dates/options without deterministic assembly. |
| **2 — Current discourse** | Batch LLM→CSV pipelines fail on timeouts, rate limits, JSON/CSV quoting drift, and schema rejection when “structured output” is pushed too far in one call. Chunking (e.g. 25–500 rows per request), bounded retries, and per-row status metadata are standard mitigations. |
| **3 — First principles for this Epic** | Your design already **limits the LLM to wording** inside fixed templates; **dates and options are deterministic** from code + data. That division of labor is the right move for cost, auditability, and upload safety. **EUREKA (for this plan):** “Everyone lets the model invent rows” is the common failure mode; your Epic explicitly does not — keep that invariant in implementation. |

### Premises (agree before build)

1. **Contract truth** — Delivery is defined by **Definition of Done** + client schema; “nice to have” does not ship in Phase 1 unless change order. **Agree** (implicit in Epic).
2. **Trust boundary** — The LLM may polish **question strings** only; **answer options for player templates** must come from **resolved stats** (no invented players). **Agree** (matches EPIC 5 Task 5.1).
3. **Category growth** — New markets/verticals ship by **new parsers + templates**, not forks of core logic. **Agree** (Overview + EPIC 2/3).
4. **No deployment** — Local Flask + file drop is sufficient; auth and hosted infra stay out of scope. **Agree** (Out of Scope).

### Approaches considered

| | **Approach A — Minimal viable (ship fastest)** | **Approach B — Ideal architecture (Epic as written)** | **Approach C — Lateral (max determinism)** |
| -- | ---------------------------------------------- | ----------------------------------------------------- | ------------------------------------------ |
| **Summary** | Thin CLI: parsers + Jinja prompts + single CSV out; Flask later. | Full vertical slice: parsers, templates, dates, batch gen, QA, UI, docs — per Epic order. | Deterministic row bodies (code fills question text from templates); LLM optional or for copy-only variants; strongest anti-hallucination. |
| **Effort** | S | M–L (5-week box) | M |
| **Risk** | Med — UI and handoff deferred; client may need UI sooner. | Low–Med — scope is clear; watch API cost and batch failures. | Med — may over-fit; client asked for LLM “quality” on language. |
| **Pros** | Fastest path to “CSV in hand.” | Matches contract; one coherent handoff. | Lowest trust risk on options/entities. |
| **Cons** | Does not match “no terminal after setup” alone. | More moving parts to integrate. | May duplicate product intent if naturalness suffers. |

**RECOMMENDATION:** **Approach B (build the Epic as specified)** — it matches the signed scope, delivers the local UI and documentation the client needs, and already encodes the right LLM boundary. Use Approach A only if the schedule slips and you need a **milestone CSV** before UI polish; use Approach C selectively for **entity rows** if QA shows residual name/option drift.

### Decision — locked (office hours)

| Decision | Choice | Rationale |
| -------- | ------ | --------- |
| **Phase 1 implementation approach** | **B — Full Epic (ideal architecture)** | Matches **Definition of Done** in one delivery: local UI (no terminal after setup), six MLB templates, QA, CSV, README, walkthrough. A and C remain **contingencies** only (schedule slip → milestone CSV; QA drift on entities → tighten determinism inside Approach B — not a fork). |

**Implications:**

- Build **one** pipeline invoked from both CLI (optional/dev) and **Flask `/run`** — avoid maintaining separate generation paths.
- **EPIC 8** is in scope for Phase 1, not a follow-on phase.
- If timeline pressure appears mid-project, **shrink date window / template toggles** in config first; only then consider a time-boxed CSV-only milestone (A-style) without redefining the locked approach.

### Critical path (suggested sequencing)

1. **EPIC 1** — runnable skeleton + `settings.yaml` (prove `main.py` + venv story).
2. **EPIC 2 + 4** — normalized events + date engine (no API cost; testable unit outputs).
3. **EPIC 3** — templates locked for six MLB Phase 1 templates.
4. **EPIC 5 → 6 → 7** — generation + QA + CSV (core value).
5. **EPIC 8** — Flask wrapper on the same pipeline (avoid two divergent “run” paths).
6. **EPIC 9** — README, template guide, recording last (reflect final behavior).

### Risks & mitigations

| Risk | Mitigation |
| ---- | ---------- |
| JSON parse failures / truncated batches | Log batch id; retry with smaller `batch_size`; write partial successes; never silent drop. |
| Hallucinated or extra player names | Validator rejects options not in resolved list; errors → `errors.csv`. |
| Near-duplicate definition too loose/tight | Define similarity threshold in code + document behavior; keep `flagged.csv` human-reviewable. |
| API cost surprises | Token/cost logging (EPIC 5.4) + dry-run with tiny date window in config. |
| Client schema drift | Single module mapping internal row → column order; assert columns on write. |

### Open questions (resolve with client if ambiguous)

- **Category ID:** Epic says system-assigned on upload — confirm whether CSV may leave blank or must use placeholder.
- **Timezone:** Schedule + stats combine to naive ISO — confirm all events are single-timezone or document assumption (e.g. venue local).
- **“Near duplicate”** — confirm whether fuzzy match is required in Phase 1 or exact dedupe + manual flagging is enough.

### The assignment (next concrete action)

**Initialize the application repo inside this workspace** (or a dedicated repo): create the folder layout in EPIC 1 Task 1.1, add `requirements.txt`, a no-op `main.py` that loads config, and a one-page README with venv steps — so the next session is **parser work**, not scaffolding debate.

### Delivery signals observed in this plan

- **Specific schema and file shapes** (schedule columns, stats sheet, TEAM_MAP) — executable, not vague.
- **Clear LLM boundary** (templates + “do not invent types”) — reduces downstream trust bugs.
- **Explicit out-of-scope** — avoids scope creep into hosting and cron.

---

## Plan: Engineering Review (/plan-eng-review)

**Design doc:** `~/.gstack/projects/serinn-labs-question-generator/jackcarlson-main-design-20260413-150729.md`  
**Test plan:** `~/.gstack/projects/serinn-labs-question-generator/jackcarlson-main-eng-review-test-plan-20260413-151157.md`  
**Branch:** `main` (workspace; application code greenfield)

### Step 0 — Scope challenge

| Check | Result |
| ----- | ------ |
| **Existing code** | None yet — no parallel flows to retire. |
| **Minimum viable scope** | Already narrowed to MLB + six templates + local UI; defer multi-category parsers beyond stubs. |
| **Complexity / file smell** | Many modules, but **incremental PRs** (parsers → dates → gen → QA → CSV → UI) keep each change set small — **no single PR should touch 8+ files** without necessity. |
| **Search / built-ins** | **[Layer 2]** OpenAI **Structured Outputs** / `parse()` + Pydantic reduces JSON breakage vs prompt-only arrays — **add explicitly to EPIC 5** (not an “ocean”; one SDK feature). **[Layer 2]** Long Flask requests → **background work + polling** is standard for local tools; Celery is **out of scope**. |
| **TODOS.md** | Created in repo root from this review (`TODOS.md`). |
| **Completeness** | Plan already aims for full QA + UI + docs — **boil the lake** on tests for parsers, dates, validation, and job/download paths. |

### Decision locked (you chose)

| Topic | Decision | Notes |
| ----- | -------- | ----- |
| **Flask long-running generation** | **B — Background job + job id + polling** | `POST /run` returns quickly with `job_id`; UI polls e.g. `GET /run/status/<job_id>` for phase, counts, errors; avoids browser/proxy timeouts on multi-minute OpenAI batches. Implementation: **in-process thread + locked job dict** is enough for single-user local; no Celery. |

### Plan amendments (apply during implementation)

1. **EPIC 5 — Structured outputs:** Prefer `response_format` / `chat.completions.parse` with a Pydantic model for “batch of rows” so validation is **machine-checked**, not regex-repaired. Keep template-driven semantics; schema encodes **allowed fields**, not business rules (those stay in code).
2. **EPIC 8 — Routes:** Extend Task 8.1 to include **`GET /run/status/<job_id>`** (and optionally `POST /run` only starts the job; separate `POST /upload` if you want cleaner separation). Document **double-submit** behavior (ignore or queue second job — pick one; see `TODOS.md` E4).
3. **EPIC 8 — Download security:** Validate `filename` is a **basename** under `outputs/` only (no `..`, no absolute paths).
4. **Secrets:** Prefer **`OPENAI_API_KEY` env var**; keep `settings.yaml` key empty in template + `.gitignore` for local overrides; README warns never to commit keys.
5. **Batching unit of work:** Clarify in code that a **batch** is “chunk of work sent in one API call” — likely **(event × enabled templates)** rows, capped by `batch_size` **tokens/rows** — define in generation module so retries are coherent.

### Architecture (boundaries)

ASCII — end-to-end flow:

```
  schedule.xlsx     stats.xlsx          templates/*.json
        \              |                      |
         \             |    settings.yaml     |
          \            |         |              |
           v           v         v              v
        +---------------------------------------------+
        | InputParser (MLB)    TemplateRegistry      |
        |   -> normalized      -> enabled ids        |
        |       events              |                |
        +---------------------------|----------------+
                                    v
                          +-------------------+
                          | PromptBuilder      |
                          |  generation_mode   |
                          |  = "template"      |
                          +---------+---------+
                                    v
                          +-------------------+
                          | OpenAI batches     |
                          | (structured JSON)  |
                          +---------+---------+
                                    v
                          +-------------------+
                          | RowAssembler       |
                          | + DateRuleEngine   |
                          +---------+---------+
                                    v
                          +-------------------+
                          | QA + Dedupe        |
                          +---------+---------+
                                    v
                          +-------------------+
                          | CSV writers        |
                          | outputs/ …         |
                          +-------------------+

  Flask:  POST /run -----> start job in thread
          GET  /run/status/<id> ---> read job state
          GET  /download/<file> ---> safe path only
```

**Production-style failure:** OpenAI 429/5xx mid-batch → plan already says log and continue; **add:** exponential backoff + cap, and **persist partial CSV** only if spec allows — otherwise all rows for failed batch → recoverable error in summary.

### Code quality (plan-level)

- **DRY:** One `Row` / schema definition consumed by validator + CSV writer + (optional) Pydantic model for LLM parse.
- **Explicit:** One function `run_pipeline(settings_path) -> RunResult` used by CLI tests and Flask job wrapper — **no duplicated orchestration**.

### Test review

See **test plan file** for routes and E2E scope. Target **pytest**; **mock OpenAI** in default CI; **golden xlsx fixtures** in `tests/fixtures/`. Mark **LLM wording** checks as `[→EVAL]` (small fixed batch), not blocking unit CI.

**Coverage intent:** Parsers, date engine, QA, download safety, and job lifecycle should reach **★★★** on critical branches; Flask flow at least one **[→E2E]** or scripted manual checklist before handoff.

### Performance

- **Sequential batches** are acceptable for Phase 1; document expected runtime ~ `(#batches × latency)`.
- **Optional later:** parallel batches with `asyncio` + semaphore — **NOT in scope** unless client needs speed.

### NOT in scope (eng review)

- Hosted deployment, auth, multi-tenant UI, Celery/Redis, cron, real-time sports APIs.

### What already exists

- **No application code** in this workspace yet — only planning artifacts and gstack skills under `.cursor/skills/`.

### Failure modes → tests / handling

| Failure | Test? | User-visible? |
| ------- | ----- | ------------- |
| Truncated LLM JSON | Structured output + retry | Summary shows batch failed |
| Hallucinated player in options | Validator rejects | Row in `errors.csv` |
| Path traversal on download | Unit | 404 or 400 |
| Double-click Generate | Integration/E2E | Second run blocked or queued (define) |
| Empty inputs | Parser validator | Clear error before spend |

**Critical gap if unimplemented:** **download path traversal** and **unbounded synchronous POST** — **mitigated** by amendments above + decision **B**.

### Outside voice (Codex)

Skipped — `codex` CLI not available in this environment.

---

## GSTACK REVIEW REPORT

| Review | Trigger | Why | Runs | Status | Findings |
|--------|---------|-----|------|--------|----------|
| CEO Review | `/plan-ceo-review` | Scope & strategy | 0 | — | — |
| Codex Review | `/codex review` | Independent 2nd opinion | 0 | — | — |
| Eng Review | `/plan-eng-review` | Architecture & tests (required) | 1 | CLEAR (plan) | Structured outputs + job/poll + download hardening + test plan; see section above |
| Design Review | `/plan-design-review` | UI/UX gaps | 0 | — | — |

**UNRESOLVED:** Client open questions (category_id, timezone, near-dup policy) — listed in Epic + `TODOS.md` E6.

**VERDICT:** **Eng plan review complete** — implement with amendments and `TODOS.md`. Optional next: **`/plan-design-review`** for Flask single-page UX (progress, errors, empty states). Run **`/ship`** when code exists and diff-scoped reviews apply.
