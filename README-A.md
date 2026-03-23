# 🔷 PriSm — Precision Insights Machine

> Self-contained Exploratory Data Analysis app.  
> Upload a CSV → describe your goal → PriSm picks and renders the best charts automatically.  
> **No API keys. No external services. Fully offline.**

---

## Table of Contents

1. [Project Structure](#1-project-structure)
2. [Prerequisites](#2-prerequisites)
3. [Installation](#3-installation)
4. [Running the App](#4-running-the-app)
5. [Testing the Backend](#5-testing-the-backend)
6. [All Commands — Quick Reference](#6-all-commands--quick-reference)
7. [Architecture](#7-architecture)
8. [How the Chart Planner Works](#8-how-the-chart-planner-works)
9. [API Reference](#9-api-reference)
10. [Configurable UI Options](#10-configurable-ui-options)
11. [Supported Chart Types](#11-supported-chart-types)
12. [Dependencies](#12-dependencies)
13. [Troubleshooting](#13-troubleshooting)

---

## 1. Project Structure

```
eda-app/
├── api.py            ← FastAPI backend  (EDA engine, chart planner, stats)
├── app.py            ← Streamlit frontend  (upload, configure, render charts)
├── test_api.py       ← Backend test suite  (65 unit + integration tests)
├── run.sh            ← One-command launcher for both servers
├── pyproject.toml    ← uv dependency manifest
└── README.md
```

---

## 2. Prerequisites

| Requirement | Minimum version | Check |
|---|---|---|
| Python | 3.11 | `python --version` |
| uv | latest | `uv --version` |

Install **uv** if you don't have it:

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
source $HOME/.local/bin/env   # or restart your terminal
```

---

## 3. Installation

```bash
# Clone / download the project, then enter the folder
cd eda-app

# Install all runtime dependencies
uv sync

# Install runtime + dev dependencies (includes pytest)
uv sync --dev
```

`uv sync` reads `pyproject.toml` and creates an isolated virtual environment
automatically — no manual `pip install` or `venv` activation needed.

---

## 4. Running the App

### Option A — One command (recommended)

Starts both the API and the UI in a single terminal:

```bash
bash run.sh
```

```
🔷 PriSm — starting servers...

⚙️  Starting FastAPI backend on http://localhost:8000 ...
🖥️  Starting Streamlit frontend on http://localhost:8501 ...

✅ PriSm is running.
   API docs  : http://localhost:8000/docs
   App UI    : http://localhost:8501

Press Ctrl+C to stop.
```

### Option B — Two separate terminals

```bash
# Terminal 1 — backend
uv run uvicorn api:app --reload --port 8000

# Terminal 2 — frontend
uv run streamlit run app.py --server.port 8501
```

### Open the app

| URL | What it is |
|---|---|
| http://localhost:8501 | PriSm UI (Streamlit) |
| http://localhost:8000/docs | Interactive API docs (Swagger) |
| http://localhost:8000/health | API health check |

---

## 5. Testing the Backend

The test suite (`test_api.py`) has **two independent layers**:

- **Layer 1 — Unit tests** import `api.py` functions directly. No server needed.
- **Layer 2 — Integration tests** send real HTTP requests. Server must be running.

### Run unit tests only (no server needed)

```bash
uv run python test_api.py --unit
```

Use this to verify the backend logic before starting anything.

### Run integration tests only (server must be up first)

```bash
# Terminal 1 — start the API
uv run uvicorn api:app --reload --port 8000

# Terminal 2 — run integration tests
uv run python test_api.py --integration
```

### Run both layers together

```bash
# Start API first, then in another terminal:
uv run python test_api.py
```

Layer 2 is silently skipped if the server isn't reachable — it will never block you.

### Run via pytest

```bash
# All tests
uv run pytest test_api.py -v

# Unit tests only
uv run pytest test_api.py -v -k "unit"

# Integration tests only (server must be running)
uv run pytest test_api.py -v -k "integration"

# Stop on first failure
uv run pytest test_api.py -x

# Show only failures
uv run pytest test_api.py -v --tb=short
```

### Recommended pre-launch workflow

```bash
# Step 1 — verify logic without touching the server
uv run python test_api.py --unit

# Step 2 — start the API
uv run uvicorn api:app --reload --port 8000

# Step 3 — verify the live endpoints
uv run python test_api.py --integration

# Step 4 — start the UI (everything is confirmed working)
uv run streamlit run app.py --server.port 8501
```

---

## 6. All Commands — Quick Reference

### Installation

```bash
uv sync                        # Install runtime deps only
uv sync --dev                  # Install runtime + pytest
```

### Start servers

```bash
bash run.sh                                              # Both servers, one terminal
uv run uvicorn api:app --reload --port 8000              # API only
uv run streamlit run app.py --server.port 8501           # UI only
uv run uvicorn api:app --host 0.0.0.0 --port 8000        # API (network-accessible)
```

### Testing

```bash
uv run python test_api.py                                # Unit + integration (auto-skips if no server)
uv run python test_api.py --unit                         # Unit tests only
uv run python test_api.py --integration                  # Integration tests only

uv run pytest test_api.py -v                             # All tests via pytest
uv run pytest test_api.py -v -k "unit"                   # Unit tests via pytest
uv run pytest test_api.py -v -k "integration"            # Integration tests via pytest
uv run pytest test_api.py -x                             # Stop on first failure
uv run pytest test_api.py -v --tb=short                  # Short traceback on failure
uv run pytest test_api.py -v --tb=long                   # Full traceback
```

### Health check

```bash
curl http://localhost:8000/health                        # Expect: {"status":"ok","app":"PriSm"}
```

### Manual API call (curl)

```bash
curl -X POST http://localhost:8000/analyze \
  -F "file=@supply_chain_data.csv" \
  -F "problem_statement=Compare average revenue by product type" \
  -F 'allowed_charts=["bar","scatter","histogram"]'
```

---

## 7. Architecture

```
┌─────────────────────────────────────┐     HTTP POST /analyze
│         Streamlit  (app.py)          │ ──────────────────────────►
│         port 8501                    │   multipart: CSV file
│                                      │   + problem_statement
│  1. Upload CSV                        │   + allowed_charts (JSON)
│  2. Enter problem statement           │
│  3. Toggle chart types (sidebar)     │ ◄──────────────────────────
│  4. Press "Process Data"             │    JSON: profile + charts
│  5. View Plotly charts (2-col grid)  │
└─────────────────────────────────────┘

                    │
                    ▼

┌─────────────────────────────────────┐
│         FastAPI  (api.py)            │
│         port 8000                    │
│                                      │
│  parse CSV  →  pandas DataFrame      │
│       │                              │
│       ▼                              │
│  profile_dataframe()                 │
│    • shape, dtypes                   │
│    • numeric summary (describe)      │
│    • top 10 correlation pairs        │
│    • categorical value counts        │
│       │                              │
│       ▼                              │
│  plan_charts()   ← heuristic engine  │
│    A) keyword match on problem text  │
│    B) column names mentioned → axes  │
│    C) top correlated pairs → scatter │
│    D) structure rules (cat×num etc.) │
│    E) histogram fallback             │
│       │                              │
│       ▼                              │
│  build_chart_payload() × N           │
│    • bins, Pearson r, grouped means  │
│    • IQR / outlier counts            │
│    • correlation matrix              │
│    • statistical insight strings     │
└─────────────────────────────────────┘
```

---

## 8. How the Chart Planner Works

PriSm selects charts using a four-stage heuristic — no LLM, no external API.

### Stage A — Keyword intent matching

Your problem statement is scanned for intent keywords:

| Keywords detected | Chart selected |
|---|---|
| distribut, spread, frequen, histogram, skew | Histogram |
| correlat, relation, vs, versus, impact, between | Scatter |
| compare, rank, top, best, average, mean, total, highest | Bar |
| outlier, variance, quartile, iqr, range | Box |
| trend, over time, growth, progress, change | Line |
| proportion, share, breakdown, segment, ratio, percentage | Pie |
| correlation matrix, heatmap, feature relationship | Heatmap |

### Stage B — Column name detection

Column names mentioned in your problem text are used directly as chart axes.
Example: *"Show Revenue generated vs Defect rates"* → scatter with those exact columns.

### Stage C — Correlation-driven

The top statistically correlated numeric pairs (by absolute Pearson r) are
automatically added as scatter charts if slots remain.

### Stage D — Structure-driven fallbacks

Applied when fewer than 6 charts have been selected:
- Categorical × highest-variance numeric → bar chart
- Categorical × first numeric → grouped box plot
- 4+ numeric columns present → correlation heatmap
- Low-cardinality category (≤ 6 unique values) → pie chart
- Remaining numeric columns → histograms

All statistical insights (skewness, Pearson r, IQR, outlier count, top category)
are computed locally with `pandas` and `scipy`.

---

## 9. API Reference

### `GET /health`

```
200 OK
{"status": "ok", "app": "PriSm"}
```

### `POST /analyze`

**Request** — `multipart/form-data`

| Field | Type | Required | Description |
|---|---|---|---|
| `file` | CSV file | ✅ | Dataset to analyse |
| `problem_statement` | string | ✅ | Free-text description of your goal |
| `allowed_charts` | JSON array string | optional | Chart types to allow. Default: all 7 |

**`allowed_charts` values:** `"histogram"`, `"scatter"`, `"bar"`, `"box"`, `"heatmap"`, `"line"`, `"pie"`

**Response** — `application/json`

```jsonc
{
  "problem_statement": "...",
  "profile": {
    "shape":               { "rows": 100, "cols": 14 },
    "columns":             ["Product type", "Price", ...],
    "numeric_columns":     ["Price", "Revenue generated", ...],
    "categorical_columns": ["Product type", "Location", ...],
    "missing_values":      { "Price": 0, ... },
    "numeric_summary":     { "Price": { "mean": 45.2, ... }, ... },
    "top_correlations":    [{ "col1": "A", "col2": "B", "correlation": 0.82 }, ...],
    "categorical_summary": { "Product type": { "unique": 3, "top_values": {...} }, ... }
  },
  "charts": [
    {
      "chart_type": "scatter",
      "title":      "Price vs Revenue generated (r=0.43)",
      "x_col":      "Price",
      "y_col":      "Revenue generated",
      "color_col":  "Product type",
      "insight":    "Moderate positive correlation between Price and Revenue generated (r=0.432, p=0.0001, statistically significant).",
      "data": {
        "x": [...], "y": [...],
        "pearson_r": 0.432, "p_value": 0.0001,
        "color": [...]
      }
    }
    // up to 6 charts total
  ]
}
```

**Error responses**

| Status | Cause |
|---|---|
| `400` | File could not be parsed as CSV |
| `422` | Missing required form field |
| `500` | Unexpected server error |

---

## 10. Configurable UI Options

All options live in the **sidebar** of the Streamlit app:

| Option | Type | Description |
|---|---|---|
| Chart types | Checkboxes | Toggle each of the 7 chart types on/off |
| Chart height | Slider (300–800 px) | Height applied to every chart |
| AI insights | Toggle | Show/hide the per-chart statistical caption |
| Dataset profile | Toggle | Show/hide the correlations panel and shape info |
| Backend URL | Text input | Change if running the API on a different host/port |

---

## 11. Supported Chart Types

| Type | Best for | Key stats returned |
|---|---|---|
| Histogram | Numeric distributions | Skewness, kurtosis, bin counts |
| Scatter | Correlation between two numeric cols | Pearson r, p-value |
| Bar | Category aggregations / rankings | Mean or count per group |
| Box | Spread, outliers, grouped comparisons | Q1, median, Q3, IQR, outlier count |
| Heatmap | Full numeric correlation matrix | N×N Pearson r matrix |
| Line | Ordered / trend data | Min, max across axis |
| Pie | Proportional category breakdown | Value counts, ≤ 10 slices |

---

## 12. Dependencies

Managed by `uv` via `pyproject.toml` — no manual installs needed.

**Runtime**

| Package | Purpose |
|---|---|
| `streamlit` | Web UI |
| `fastapi` + `uvicorn` | REST API server |
| `pandas` + `numpy` | Data parsing and statistics |
| `scipy` | Pearson correlation, statistical tests |
| `plotly` | Interactive charts |
| `python-multipart` | File upload handling in FastAPI |
| `requests` | HTTP client (Streamlit → API) |
| `matplotlib` + `seaborn` | Available for future chart extensions |

**Dev**

| Package | Purpose |
|---|---|
| `pytest` | Test runner for `test_api.py` |

---

## 13. Troubleshooting

**`ModuleNotFoundError` on startup**
```bash
uv sync          # re-installs all dependencies
```

**`Connection refused` when running integration tests**
```bash
# Make sure the API is running first:
uv run uvicorn api:app --reload --port 8000
# Then in another terminal:
uv run python test_api.py --integration
```

**Port already in use**
```bash
# Kill whatever is on port 8000 or 8501:
lsof -ti :8000 | xargs kill -9
lsof -ti :8501 | xargs kill -9
# Then restart normally
```

**Streamlit can't reach the API**  
Check that the *Backend URL* in the sidebar matches where your API is running
(default: `http://localhost:8000/analyze`). If running in Docker or a VM, use
the correct host/IP address.

**`422 Unprocessable Entity` from the API**  
The `problem_statement` form field is required. Make sure you have typed something
in the text area before clicking *Process Data*.

**Charts show no data / all empty**  
Your CSV may have column names that don't match any keywords. Try mentioning
exact column names in the problem statement, e.g.:
*"Show the distribution of Price and correlation between Revenue generated and Defect rates."*


---------------------------------------------------------------------------------------------------


Based on the exact columns in `supply_chain_data.csv`, here are statements ranging from one-liner to multi-objective:

---

## 🟢 Simple — single intent, one or two columns

These trigger one clear chart type each.

1. `Show the distribution of Defect rates`
2. `Show the distribution of Manufacturing costs`
3. `What is the breakdown of Product type?`
4. `Compare average Revenue generated across different Supplier name`
5. `Show proportion of each Transportation modes`
6. `Which Location has the highest Shipping costs?`
7. `Show the spread and outliers in Lead times`
8. `How are Stock levels distributed across products?`
9. `Show a breakdown of Inspection results`
10. `What is the count of each Shipping carriers?`

---

## 🟡 Moderate — two intents, cross-column relationships

These trigger 2–3 chart types and cross categorical with numeric columns.

11. `Compare average Defect rates by Supplier name and show its distribution`
12. `How does Manufacturing costs vary across Location, and what does its spread look like?`
13. `Show the correlation between Shipping costs and Lead times, and compare averages by Shipping carriers`
14. `What is the relationship between Price and Revenue generated? Also break down revenue by Product type`
15. `Analyse Stock levels across Supplier name and show the proportion of each Transportation modes`
16. `Compare Manufacturing lead time by Location and show outliers in Production volumes`
17. `How does Order quantities correlate with Revenue generated? Also show distribution of Order quantities`
18. `Show which Routes have the highest Costs and how Shipping times are distributed`

---

## 🔴 Complex — multiple intents, named columns, competing dimensions

These are designed to push the planner to its full 6-chart limit across all chart types.

19. `Analyse the correlation between Manufacturing costs and Defect rates, compare average Revenue generated by Product type, show the distribution of Shipping costs, and identify outliers in Lead times`

20. `Which Supplier name has the highest average Manufacturing costs and worst Defect rates? Also show the correlation between Price and Revenue generated, and the breakdown of Transportation modes used`

21. `Show how Defect rates and Manufacturing costs are correlated across different Location, compare Revenue generated by Supplier name, and display the spread of Shipping costs grouped by Shipping carriers`

22. `Identify the top-performing Product type by Revenue generated, show the distribution of Manufacturing lead time, analyse the relationship between Stock levels and Number of products sold, and highlight any outliers in Shipping costs`

23. `I want to understand end-to-end supply chain efficiency — compare Lead times and Manufacturing lead time by Supplier name, show how Defect rates impact Revenue generated, analyse the proportion of Inspection results outcomes, and display the correlation matrix of all cost and time variables`

---

## 💡 Tips for best results

| Goal | What to include in your statement |
|---|---|
| Target a specific chart | Use the keyword directly — *"distribution"*, *"heatmap"*, *"trend"* |
| Lock in specific axes | Mention the exact column name — PriSm will detect it and use it |
| Get a heatmap | Say *"correlation matrix"* or *"all numeric features"* |
| Get grouped box plots | Say *"outliers in `<numeric>` by `<category>`"* |
| Max out all 6 chart slots | Chain multiple intents with *"and"* / *"also"* / *","* |