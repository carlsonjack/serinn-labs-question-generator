# Serinn Labs — Structured Content Generation

Local Python app that turns MLB schedule/stats spreadsheets into upload-ready CSV question rows. See **`# Epic: Structured Content Generation Sy.md`** for scope, architecture, and delivery checklist.

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

## Multi-vertical inputs (MLB + other sports)

- **MLB (legacy):** Under `inputs.files.mlb`, keep `event_source` and `metric_source` filenames (e.g. `schedule.xlsx`, `stats.xlsx`). Set `inputs.category_key` to `mlb`. No change from the original workflow.
- **Additional packages (e.g. F1):** Add a block under `inputs.files` (e.g. `F1`) with arbitrary slot ids (`schedule`, …), then map each slot to a `SourceRole` in `inputs.file_roles` (e.g. `event_source`). Schedule-only packages omit metric slots.
- **Templates:** Each JSON template’s `subcategory` must match the selected input package when normalized (case-insensitive), e.g. `F1` templates with package `F1`.
- **Export `category_id`:** Optional map `category_ids` in `config/settings.yaml` (`mlb`, `f1`, …) keyed by lowercase package id; falls back to top-level `category_id`.
- **Calendar-style event labels:** Normalizers may set `event_display` on `NormalizedEvent`; the CSV `event` column uses it when present (otherwise `Away vs Home`).

See [`config/settings.yaml`](config/settings.yaml) for a commented example with both `mlb` and `F1`.

## Testing

| Command | Purpose |
|--------|---------|
| `pytest` | Full suite (fast path skips optional MLB files under `inputs/` when missing). |
| `pytest -m integration` | Parser registry + F1 bundle integration tests (`tests/integration/`). |
| `pytest -m "not needs_local_inputs"` | CI-style run excluding tests that expect `inputs/schedule.xlsx` + `stats.xlsx`. |

Factories for `.xlsx` files live in [`tests/fixtures/workbooks.py`](tests/fixtures/workbooks.py). Add new vertical checks beside [`tests/integration/test_f1_bundle_load.py`](tests/integration/test_f1_bundle_load.py).

## Status

Repository initialized; implementation follows the Epic (EPIC 1+).
