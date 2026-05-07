# Serinn Labs — Structured Content Generation

Local Python app that turns sports schedule / stats spreadsheets into upload-ready CSV question rows (MLB, MLS, World Cup–style layouts, F1, etc.). See **`# Epic: Structured Content Generation Sy.md`** for scope, architecture, and delivery checklist.

## How to use this properly (simple map)

Everything below connects **inputs** → **templates** → **export**. If one link is wrong, you get empty runs, wrong topic IDs, or templates that never appear.

### 1. Pick an **input package**

In [`config/settings.yaml`](config/settings.yaml), `inputs.category_key` chooses which block under `inputs.files` is active (e.g. `world_cup`, `mlb`, `MLS`). That same key drives **which templates** are allowed (see step 4).

### 2. Put files where `inputs.files` says they should go

For each slot (`event_source`, `metric_source`, `schedule`, `stats`, …) the value is the **filename** that must live under your inputs directory (default `inputs/`). Upload those files in the UI (**Save uploads + create normalizer profile**) or copy them in manually.

### 3. **Topic import ID** (where questions land downstream)

Generated CSV rows include a **`topic_import_id`** column. That value comes from settings—not from template ids:

| Setting | Meaning |
|--------|---------|
| `topic_import_ids.<package>` | Per-package override. Keys are **lowercase** package ids (`mlb`, `world_cup`, `mls`, …). When present for the active package, this wins. |
| `topic_import_id` | Fallback when there is no entry for the active package. |

Example: active package `world_cup` → use `topic_import_ids.world_cup` if set; else `topic_import_id`.

**Template `id`** (e.g. `world_cup_event_winner_mc`) is only the template’s name and `templates_enabled` switch—it is **not** the topic import id.

### 4. **Templates**: `id` vs `subcategory` vs config “Subcategory label”

| Field | What it does |
|--------|----------------|
| **`id`** | Unique template name; used in `templates_enabled` to turn templates on/off. |
| **`subcategory`** (on each template) | Two jobs: (1) **Match the input package** after normalization (e.g. `World Cup` ↔ `world_cup`). (2) **Printed on every CSV row** in the `subcategory` column for questions built from that template. |
| **`subcategory`** in `settings.yaml` (UI: “Subcategory label”) | Display/filename hint and fallback when the app infers a label for the package—it does **not** replace each template’s `subcategory` on export rows. |

Matching rule: labels are compared in a **normalized** form (case-insensitive; spaces/punctuation stripped), so `World Cup`, `world_cup`, and `WORLD_CUP` line up with package `world_cup`.

### 5. **Date filter** and **date rules**

- **`date_filter.start` / `date_filter.end`**: Only events (and thus questions) in that window are considered.
- **`date_rules`**: Offsets for start / expiration / resolution on each row. Keys under `date_rules` can follow **`date_rules.default`** plus overrides; row assembly uses the template’s subcategory (lower case) when resolving rules—add a block if you need custom offsets for a new vertical.

### 6. Enable templates

In `templates_enabled`, set each template **`id`** you want to `true`. Disabled ids are skipped even if they match the package.

### 7. New / custom workbook layouts — AI normalizer

For a package without a built-in Python normalizer, use the UI flow: upload inputs → **Save uploads + create normalizer profile** (proposes a declarative spec, previews, saves under `config/input_profiles/normalizers/`). Then generation uses that profile when parsing your `.xlsx` files.

### Sample template CSVs

See [`samples/`](samples/) (e.g. [`samples/template_upload_two_world_cup_templates.csv`](samples/template_upload_two_world_cup_templates.csv)) for the repeating header row format used by **Upload** in the UI.

---

## Multi-vertical inputs (reference)

- **MLB (legacy):** Under `inputs.files.mlb`, keep `event_source` and `metric_source` filenames (e.g. `schedule.xlsx`, `stats.xlsx`). Set `inputs.category_key` to `mlb`. No change from the original workflow.
- **Additional packages (e.g. F1):** Add `inputs.files.<Package>` with slot ids → target filenames (any `.xlsx` basename per slot). Slots whose ids match a `SourceRole` (`event_source`, `metric_source`, `entity_source`, `reference_source`) or a built-in alias (`schedule`, `stats`, `fixtures`, `roster`, …) are mapped automatically—no `inputs.file_roles` required unless you use opaque slot names. For schedule+stats only, you can reuse the same two-slot ids as MLB with any filenames. Schedule-only packages omit metric slots.
- **Templates:** Each JSON template’s `subcategory` must match the selected input package when normalized (case-insensitive), e.g. `F1` templates with package `F1`.
- **Aliases:** If the input package key should differ from the template label or parser key, add `inputs.package_aliases`, e.g. `formula_one: [F1, Formula 1]`. The alias allows `formula_one` inputs to use `F1` templates and the registered F1 normalizer.
- **New packages (e.g. MLS):** If there is no Python normalizer for your package key yet, configure **both** `event_source` and `metric_source` (or `schedule` + `stats` with role inference) so the pipeline can run the same schedule+stats composition as MLB; detection still uses your package key for saved profiles. Single-file calendar feeds should map with `package_aliases` to `f1` or add a dedicated normalizer.
- **Export Topic Import ID:** Optional map `topic_import_ids` in `config/settings.yaml` (`mlb`, `f1`, …) keyed by lowercase package id; falls back to top-level `topic_import_id`.
- **Calendar-style event labels:** Normalizers may set `event_display` on `NormalizedEvent`; the CSV `event` column uses it when present (otherwise `Away vs Home`).

See [`config/settings.yaml`](config/settings.yaml) for a commented example with both `mlb` and `F1`.

## Requirements

- **Python 3.10+** (check with `python --version` or `python3 --version`)
- If Python is missing or older than 3.10, install a current release from [python.org/downloads](https://www.python.org/downloads/)

## Setup

### 1. Virtual environment

From the project root:

```bash
python -m venv venv
```

### 2. Activate the virtual environment

**macOS / Linux:**

```bash
source venv/bin/activate
```

**Windows (Command Prompt):**

```cmd
venv\Scripts\activate.bat
```

**Windows (PowerShell):**

```powershell
venv\Scripts\Activate.ps1
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. OpenAI API key

**Preferred:** set the environment variable so secrets are not stored in files tracked by git:

**macOS / Linux:**

```bash
export OPENAI_API_KEY="sk-..."
```

**Windows (Command Prompt):**

```cmd
set OPENAI_API_KEY=sk-...
```

**Windows (PowerShell):**

```powershell
$env:OPENAI_API_KEY = "sk-..."
```

If `OPENAI_API_KEY` is set, it overrides any key in [`config/settings.yaml`](config/settings.yaml).

**Optional:** copy values you want to override into `config/settings.local.yaml` (gitignored). Use that file for local tweaks such as `model` or `date_filter`. Do **not** commit real API keys in `settings.yaml` or any tracked file.

See also [`.env.example`](.env.example) for variable names you can set manually (this project does not load `.env` automatically unless you add a loader later).

## Run

```bash
python main.py
```

Open the URL printed in the terminal (default [http://127.0.0.1:5000/](http://127.0.0.1:5000/)). Optional environment variables: `HOST`, `PORT`, `FLASK_DEBUG` (see `.env.example`).

In the UI: pick the **input package**, set **date range** / **topic import id** / **subcategory label** as needed, **upload** `.xlsx` files (and run **Save uploads + create normalizer profile** once if you use a new layout), enable templates, then **generate** and download the CSV.

## Adding a new client category

Every new category should be added through the same acceptance contract:

1. Add or update an input profile under [`config/input_profiles/`](config/input_profiles/) if auto-detection cannot infer the workbook shape.
2. Add fixture builders in [`tests/fixtures/workbooks.py`](tests/fixtures/workbooks.py) for representative happy-path and malformed workbooks.
3. Add templates under [`templates/`](templates/) or test-local template fixtures with the intended `subcategory`.
4. Add a `PipelineMatrixCase` in [`tests/fixtures/matrix.py`](tests/fixtures/matrix.py) covering the category’s happy path and at least one failure path.
5. If package names and template labels differ, add `inputs.package_aliases` coverage so the relationship is explicit.
6. Run the deterministic gates below before client handoff.

The shared matrix intentionally uses mocked generation. This proves parser/template/pipeline/output behavior without calling OpenAI; live provider checks are opt-in smoke tests only.

## Testing

| Command | Purpose |
|--------|---------|
| `.venv/bin/python -m pytest` | Full default suite. Exhaustive/live checks are skipped unless explicitly enabled. |
| `.venv/bin/python -m pytest -m integration` | Parser registry, bundle loading, and deterministic pipeline matrix tests. |
| `.venv/bin/python -m pytest -m "not needs_local_inputs and not live_openai and not exhaustive"` | CI-safe gate excluding local client files, live OpenAI, and exhaustive-only cases. |
| `RUN_EXHAUSTIVE_TESTS=1 .venv/bin/python -m pytest -m exhaustive` | Pre-delivery edge-case matrix expansion. |
| `RUN_LIVE_OPENAI_TESTS=1 OPENAI_API_KEY=... .venv/bin/python -m pytest -m live_openai` | Optional live provider smoke tests when such tests exist. |

Factories for `.xlsx` files live in [`tests/fixtures/workbooks.py`](tests/fixtures/workbooks.py). Add new vertical checks beside [`tests/integration/test_f1_bundle_load.py`](tests/integration/test_f1_bundle_load.py).

## Status

Repository initialized; implementation follows the Epic (EPIC 1+).
