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

## Status

Repository initialized; implementation follows the Epic (EPIC 1+).
