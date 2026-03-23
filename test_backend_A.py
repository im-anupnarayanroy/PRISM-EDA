"""
test_api.py  —  PriSm backend test suite
=========================================
Two independent layers:

  LAYER 1 — Unit tests   (no server required)
    Imports functions directly from api.py and tests them in isolation.
    Covers: profiler, intent matcher, column detector, chart planner,
            chart data builder, and insight generator.

  LAYER 2 — Integration tests   (server must be running on localhost:8000)
    Sends real HTTP requests to every endpoint.
    Covers: /health, /analyze response structure, per-chart-type data,
            keyword routing, allowed_charts filter, and error handling.

Run options
-----------
  # Run everything (unit + integration) with pretty console output
  uv run python test_api.py

  # Unit tests only (no server needed)
  uv run python test_api.py --unit

  # Integration tests only
  uv run python test_api.py --integration

  # Via pytest (also works)
  uv run pytest test_api.py -v
  uv run pytest test_api.py -v -k "unit"
  uv run pytest test_api.py -v -k "integration"
"""

from __future__ import annotations

import io
import json
import sys
import textwrap
import time
import traceback
from typing import Any

import numpy as np
import pandas as pd
import requests

# ── Import api internals for unit testing ─────────────────────────────────────
# api.py must live in the same directory as this file.
sys.path.insert(0, ".")
from api import (
    _col_mentioned,
    _insight_for,
    _match_intents,
    build_chart_payload,
    plan_charts,
    profile_dataframe,
)

API_BASE = "http://localhost:8000"

# ══════════════════════════════════════════════════════════════════════════════
# Shared fixtures
# ══════════════════════════════════════════════════════════════════════════════

def make_supply_chain_df() -> pd.DataFrame:
    """Minimal representative slice of supply_chain_data.csv (no file I/O)."""
    rng = np.random.default_rng(42)
    n = 80
    return pd.DataFrame({
        "Product type":          rng.choice(["skincare", "haircare", "cosmetics"], n),
        "SKU":                   [f"SKU{i}" for i in range(n)],
        "Price":                 rng.uniform(1, 100, n),
        "Availability":          rng.integers(0, 100, n).astype(float),
        "Number of products sold": rng.integers(1, 1000, n).astype(float),
        "Revenue generated":     rng.uniform(500, 10000, n),
        "Customer demographics": rng.choice(["Male", "Female", "Non-binary"], n),
        "Stock levels":          rng.integers(0, 100, n).astype(float),
        "Lead times":            rng.integers(1, 30, n).astype(float),
        "Shipping costs":        rng.uniform(1, 20, n),
        "Defect rates":          rng.uniform(0, 5, n),
        "Manufacturing costs":   rng.uniform(10, 100, n),
        "Supplier name":         rng.choice(["Supplier 1", "Supplier 2", "Supplier 3"], n),
        "Location":              rng.choice(["Mumbai", "Delhi", "Bangalore", "Kolkata"], n),
    })


def make_numeric_only_df() -> pd.DataFrame:
    rng = np.random.default_rng(0)
    return pd.DataFrame({
        "A": rng.normal(50, 10, 50),
        "B": rng.normal(20, 5, 50),
        "C": rng.uniform(0, 100, 50),
        "D": rng.exponential(5, 50),
    })


def make_categorical_only_df() -> pd.DataFrame:
    rng = np.random.default_rng(1)
    return pd.DataFrame({
        "colour":  rng.choice(["red", "blue", "green"], 40),
        "size":    rng.choice(["S", "M", "L", "XL"], 40),
        "country": rng.choice(["IN", "US", "UK"], 40),
    })


def make_missing_values_df() -> pd.DataFrame:
    df = make_supply_chain_df()
    # Inject NaN into several columns
    df.loc[df.sample(10, random_state=5).index, "Price"] = np.nan
    df.loc[df.sample(5,  random_state=6).index, "Defect rates"] = np.nan
    df.loc[df.sample(8,  random_state=7).index, "Product type"] = np.nan
    return df


def df_to_csv_bytes(df: pd.DataFrame) -> bytes:
    buf = io.BytesIO()
    df.to_csv(buf, index=False)
    return buf.getvalue()


ALL_CHARTS = ["histogram", "scatter", "bar", "box", "heatmap", "line", "pie"]


# ══════════════════════════════════════════════════════════════════════════════
# Test runner helpers
# ══════════════════════════════════════════════════════════════════════════════

GREEN  = "\033[92m"
RED    = "\033[91m"
YELLOW = "\033[93m"
CYAN   = "\033[96m"
BOLD   = "\033[1m"
RESET  = "\033[0m"

_results: list[tuple[str, bool, str]] = []   # (name, passed, message)


def _run(name: str, fn):
    try:
        fn()
        _results.append((name, True, ""))
        print(f"  {GREEN}✓{RESET}  {name}")
    except Exception as exc:
        msg = traceback.format_exc(limit=3)
        _results.append((name, False, msg))
        print(f"  {RED}✗{RESET}  {name}")
        # Print short reason indented
        short = str(exc).split("\n")[0][:120]
        print(f"      {YELLOW}↳ {short}{RESET}")


def _section(title: str):
    print(f"\n{BOLD}{CYAN}{'─'*60}{RESET}")
    print(f"{BOLD}{CYAN}  {title}{RESET}")
    print(f"{BOLD}{CYAN}{'─'*60}{RESET}")


# ══════════════════════════════════════════════════════════════════════════════
# LAYER 1 — Unit tests
# ══════════════════════════════════════════════════════════════════════════════

# ── 1a. profile_dataframe ─────────────────────────────────────────────────────

def unit_profile_shape():
    df = make_supply_chain_df()
    p  = profile_dataframe(df)
    assert p["shape"]["rows"] == len(df)
    assert p["shape"]["cols"] == len(df.columns)


def unit_profile_numeric_columns():
    df = make_supply_chain_df()
    p  = profile_dataframe(df)
    expected_num = df.select_dtypes(include="number").columns.tolist()
    assert set(p["numeric_columns"]) == set(expected_num)


def unit_profile_categorical_columns():
    df = make_supply_chain_df()
    p  = profile_dataframe(df)
    expected_cat = df.select_dtypes(exclude="number").columns.tolist()
    assert set(p["categorical_columns"]) == set(expected_cat)


def unit_profile_missing_values_counted():
    df = make_missing_values_df()
    p  = profile_dataframe(df)
    mv = p["missing_values"]
    assert mv["Price"] == df["Price"].isnull().sum()
    assert mv["Defect rates"] == df["Defect rates"].isnull().sum()


def unit_profile_correlations_sorted():
    df = make_supply_chain_df()
    p  = profile_dataframe(df)
    corrs = p["top_correlations"]
    assert len(corrs) >= 1
    abs_vals = [abs(c["correlation"]) for c in corrs]
    assert abs_vals == sorted(abs_vals, reverse=True), "Correlations must be sorted descending"


def unit_profile_correlations_capped_at_10():
    df = make_supply_chain_df()
    p  = profile_dataframe(df)
    assert len(p["top_correlations"]) <= 10


def unit_profile_numeric_summary_keys():
    df = make_supply_chain_df()
    p  = profile_dataframe(df)
    for col in p["numeric_columns"]:
        assert col in p["numeric_summary"], f"Missing numeric summary for {col}"


def unit_profile_categorical_summary_unique():
    df = make_supply_chain_df()
    p  = profile_dataframe(df)
    for col in p["categorical_columns"]:
        assert "unique"     in p["categorical_summary"][col]
        assert "top_values" in p["categorical_summary"][col]


def unit_profile_numeric_only_df():
    """Should work fine with no categorical columns at all."""
    df = make_numeric_only_df()
    p  = profile_dataframe(df)
    assert len(p["numeric_columns"]) == 4
    assert len(p["categorical_columns"]) == 0


def unit_profile_categorical_only_df():
    """Should work fine with no numeric columns at all."""
    df = make_categorical_only_df()
    p  = profile_dataframe(df)
    assert len(p["numeric_columns"]) == 0
    assert len(p["categorical_columns"]) == 3
    assert "top_correlations" not in p
    assert "numeric_summary"  not in p


# ── 1b. _match_intents ───────────────────────────────────────────────────────

def unit_intent_histogram():
    assert "histogram" in _match_intents("Show me the distribution of prices")


def unit_intent_scatter():
    assert "scatter" in _match_intents("What is the correlation between cost and defects?")


def unit_intent_bar():
    assert "bar" in _match_intents("Compare the average revenue by product type")


def unit_intent_box():
    assert "box" in _match_intents("Find outliers in manufacturing costs")


def unit_intent_line():
    assert "line" in _match_intents("Show the trend over time for stock levels")


def unit_intent_pie():
    assert "pie" in _match_intents("Show the proportion of each product category")


def unit_intent_heatmap():
    assert "heatmap" in _match_intents("Give me a correlation matrix of all features")


def unit_intent_multiple():
    """A rich problem statement should trigger multiple intents."""
    intents = _match_intents("Compare average revenue and show the distribution of defect rates")
    assert "bar"       in intents
    assert "histogram" in intents


def unit_intent_none():
    """No known keywords → empty list."""
    result = _match_intents("I just uploaded my file")
    assert isinstance(result, list)   # may be empty — that is correct


def unit_intent_case_insensitive():
    """Keywords must match regardless of casing."""
    assert "scatter" in _match_intents("CORRELATION between Price and Revenue")


# ── 1c. _col_mentioned ───────────────────────────────────────────────────────

def unit_col_mentioned_exact():
    cols = ["Price", "Defect rates", "Location"]
    assert "Price" in _col_mentioned("What drives Price variation?", cols)


def unit_col_mentioned_multi():
    cols = ["Price", "Defect rates", "Location"]
    found = _col_mentioned("Analyse Price vs Defect rates by Location", cols)
    assert set(found) == {"Price", "Defect rates", "Location"}


def unit_col_mentioned_none():
    cols = ["Price", "Revenue generated"]
    assert _col_mentioned("nothing relevant here", cols) == []


def unit_col_mentioned_case_insensitive():
    cols = ["Manufacturing costs"]
    assert "Manufacturing costs" in _col_mentioned("impact on manufacturing costs", cols)


# ── 1d. plan_charts ──────────────────────────────────────────────────────────

def _plan(problem, df=None, charts=None):
    if df is None:
        df = make_supply_chain_df()
    if charts is None:
        charts = ALL_CHARTS
    profile = profile_dataframe(df)
    return plan_charts(problem, profile, charts, df)


def unit_plan_max_6_charts():
    specs = _plan("Show everything possible about this dataset")
    assert len(specs) <= 6


def unit_plan_at_least_1_chart():
    specs = _plan("generic analysis")
    assert len(specs) >= 1


def unit_plan_respects_allowed_charts():
    specs = _plan("distribution and correlation", charts=["histogram"])
    for s in specs:
        assert s["chart_type"] == "histogram", f"Got disallowed chart: {s['chart_type']}"


def unit_plan_no_duplicate_keys():
    specs = _plan("compare average revenue across product types, show distribution of prices")
    keys = [(s["chart_type"], s["x_col"], s["y_col"]) for s in specs]
    assert len(keys) == len(set(keys)), "Duplicate (ctype, x_col, y_col) found"


def unit_plan_histogram_keyword():
    specs = _plan("Show the distribution of prices")
    types = [s["chart_type"] for s in specs]
    assert "histogram" in types


def unit_plan_scatter_keyword():
    specs = _plan("What is the correlation between Manufacturing costs and Defect rates?")
    types = [s["chart_type"] for s in specs]
    assert "scatter" in types


def unit_plan_bar_keyword():
    specs = _plan("Compare average Revenue generated across different Product type")
    types = [s["chart_type"] for s in specs]
    assert "bar" in types


def unit_plan_heatmap_keyword():
    specs = _plan("Show me a heatmap of all features")
    types = [s["chart_type"] for s in specs]
    assert "heatmap" in types


def unit_plan_pie_keyword():
    specs = _plan("What is the proportion breakdown of Location?")
    types = [s["chart_type"] for s in specs]
    assert "pie" in types


def unit_plan_column_name_used_as_axis():
    """Mentioning 'Revenue generated' should make it appear as an axis somewhere."""
    specs = _plan("Show the distribution of Revenue generated")
    axes = [s["x_col"] for s in specs] + [s["y_col"] for s in specs]
    assert "Revenue generated" in axes, f"Expected 'Revenue generated' in axes, got: {axes}"


def unit_plan_structure_fallback_numeric_only():
    """With no categorical cols the planner should still produce charts."""
    specs = _plan("generic analysis", df=make_numeric_only_df())
    assert len(specs) >= 1


def unit_plan_structure_fallback_categorical_only():
    """With no numeric cols should still produce at least bar/pie."""
    specs = _plan("breakdown and comparison", df=make_categorical_only_df())
    assert len(specs) >= 1


def unit_plan_empty_allowed_charts():
    specs = _plan("anything", charts=[])
    assert specs == []


def unit_plan_missing_values_df():
    """Planner should not crash on a DataFrame with NaN."""
    specs = _plan("compare average revenue", df=make_missing_values_df())
    assert len(specs) >= 1


def unit_plan_all_spec_fields_present():
    specs = _plan("compare average Revenue generated by Product type")
    required = {"chart_type", "title", "x_col", "y_col", "insight"}
    for s in specs:
        missing = required - s.keys()
        assert not missing, f"Chart spec missing fields: {missing}"


# ── 1e. build_chart_payload ──────────────────────────────────────────────────

def _build(ctype, x_col=None, y_col=None, color_col=None, df=None):
    if df is None:
        df = make_supply_chain_df()
    spec = {"chart_type": ctype, "title": f"Test {ctype}",
            "x_col": x_col, "y_col": y_col, "color_col": color_col, "insight": ""}
    return build_chart_payload(df, spec)


def unit_build_histogram_keys():
    p = _build("histogram", "Price")
    assert "bin_centers" in p["data"]
    assert "counts"      in p["data"]
    assert "normality"   in p["data"]
    assert len(p["data"]["bin_centers"]) == len(p["data"]["counts"])


def unit_build_histogram_bins_count():
    p = _build("histogram", "Revenue generated")
    assert len(p["data"]["bin_centers"]) == 30


def unit_build_scatter_stats():
    p = _build("scatter", "Price", "Revenue generated")
    assert "pearson_r" in p["data"]
    assert "p_value"   in p["data"]
    assert -1.0 <= p["data"]["pearson_r"] <= 1.0


def unit_build_scatter_with_color():
    p = _build("scatter", "Price", "Revenue generated", "Product type")
    assert "color" in p["data"]
    assert len(p["data"]["color"]) == len(p["data"]["x"])


def unit_build_bar_count_mode():
    """Bar without a numeric y_col → count mode."""
    p = _build("bar", "Product type", y_col=None)
    assert "categories" in p["data"]
    assert "values"     in p["data"]
    assert p["data"]["y_label"] == "count"


def unit_build_bar_mean_mode():
    """Bar with a numeric y_col → mean mode."""
    p = _build("bar", "Product type", "Revenue generated")
    assert p["data"]["y_label"] == "Revenue generated"


def unit_build_bar_lists_equal_length():
    p = _build("bar", "Location", "Manufacturing costs")
    assert len(p["data"]["categories"]) == len(p["data"]["values"])


def unit_build_box_single_keys():
    p = _build("box", "Price")
    d = p["data"]
    assert "values" in d
    assert "q1"     in d
    assert "median" in d
    assert "q3"     in d
    assert "iqr"    in d


def unit_build_box_iqr_correct():
    p = _build("box", "Price")
    d = p["data"]
    assert abs(d["iqr"] - (d["q3"] - d["q1"])) < 1e-6


def unit_build_box_grouped():
    p = _build("box", "Price", color_col="Product type")
    assert "groups" in p["data"]
    assert isinstance(p["data"]["groups"], dict)
    assert len(p["data"]["groups"]) > 0


def unit_build_heatmap_square_matrix():
    df = make_supply_chain_df()
    p  = _build("heatmap", df=df)
    n  = len(p["data"]["columns"])
    assert len(p["data"]["matrix"])    == n
    assert len(p["data"]["matrix"][0]) == n


def unit_build_heatmap_diagonal_ones():
    p = _build("heatmap")
    for i, row in enumerate(p["data"]["matrix"]):
        assert abs(row[i] - 1.0) < 1e-4, f"Diagonal[{i}] is {row[i]}, expected 1.0"


def unit_build_pie_labels_values():
    p = _build("pie", "Product type")
    assert "labels" in p["data"]
    assert "values" in p["data"]
    assert len(p["data"]["labels"]) == len(p["data"]["values"])


def unit_build_pie_max_10_slices():
    p = _build("pie", "Product type")
    assert len(p["data"]["labels"]) <= 10


def unit_build_line_lists():
    p = _build("line", "Price", "Revenue generated")
    assert "x" in p["data"]
    assert "y" in p["data"]
    assert len(p["data"]["x"]) == len(p["data"]["y"])


def unit_build_invalid_column_no_crash():
    """A non-existent column should be silently handled — no exception."""
    p = _build("histogram", "NonExistentColumn_XYZ")
    assert p["chart_type"] == "histogram"
    # data will be empty dict (column safely resolved to None)


def unit_build_no_error_key_on_valid_input():
    for ctype, x, y in [
        ("histogram", "Price",            None),
        ("scatter",   "Price",            "Revenue generated"),
        ("bar",       "Product type",     "Revenue generated"),
        ("box",       "Defect rates",     None),
        ("heatmap",   None,               None),
        ("pie",       "Location",         None),
        ("line",      "Price",            "Revenue generated"),
    ]:
        p = _build(ctype, x, y)
        assert "error" not in p, f"Unexpected 'error' in {ctype} payload: {p.get('error')}"


# ── 1f. _insight_for ────────────────────────────────────────────────────────

def unit_insight_histogram_non_empty():
    df = make_supply_chain_df()
    s  = _insight_for("histogram", "Price", None, None, df)
    assert len(s) > 0


def unit_insight_histogram_mentions_skewness():
    df = make_supply_chain_df()
    s  = _insight_for("histogram", "Price", None, None, df)
    assert "skewness" in s.lower() or "skew" in s.lower()


def unit_insight_scatter_mentions_correlation():
    df = make_supply_chain_df()
    s  = _insight_for("scatter", "Price", "Revenue generated", None, df)
    assert "correlation" in s.lower() or "r=" in s.lower()


def unit_insight_scatter_pearson_in_range():
    df  = make_supply_chain_df()
    s   = _insight_for("scatter", "Price", "Defect rates", None, df)
    # Should mention r=... with a number
    import re
    match = re.search(r"r=(-?\d+\.\d+)", s)
    assert match, f"Could not find r=... in insight: {s}"
    assert -1.0 <= float(match.group(1)) <= 1.0


def unit_insight_bar_mentions_highest():
    df = make_supply_chain_df()
    s  = _insight_for("bar", "Product type", "Revenue generated", None, df)
    assert "highest" in s.lower() or "average" in s.lower()


def unit_insight_box_mentions_outliers():
    df = make_supply_chain_df()
    s  = _insight_for("box", "Price", None, None, df)
    assert "outlier" in s.lower() or "median" in s.lower()


def unit_insight_heatmap_non_empty():
    df = make_supply_chain_df()
    s  = _insight_for("heatmap", None, None, None, df)
    assert len(s) > 0


def unit_insight_pie_mentions_categories():
    df = make_supply_chain_df()
    s  = _insight_for("pie", "Product type", None, None, df)
    assert len(s) > 0


def unit_insight_bad_col_no_crash():
    df = make_supply_chain_df()
    s  = _insight_for("histogram", "ghost_column", None, None, df)
    assert isinstance(s, str)  # must return a string (possibly empty)


# ══════════════════════════════════════════════════════════════════════════════
# LAYER 2 — Integration tests  (requires server on localhost:8000)
# ══════════════════════════════════════════════════════════════════════════════

def _post_analyze(df: pd.DataFrame, problem: str, allowed=None) -> requests.Response:
    csv_bytes = df_to_csv_bytes(df)
    data: dict[str, Any] = {"problem_statement": problem}
    if allowed is not None:
        data["allowed_charts"] = json.dumps(allowed)
    return requests.post(
        f"{API_BASE}/analyze",
        files={"file": ("data.csv", csv_bytes, "text/csv")},
        data=data,
        timeout=30,
    )


def integration_health_200():
    r = requests.get(f"{API_BASE}/health", timeout=5)
    assert r.status_code == 200


def integration_health_payload():
    r = requests.get(f"{API_BASE}/health", timeout=5)
    body = r.json()
    assert body.get("status") == "ok"
    assert body.get("app")    == "PriSm"


def integration_analyze_200():
    r = _post_analyze(make_supply_chain_df(), "generic analysis")
    assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text[:200]}"


def integration_analyze_top_level_keys():
    r    = _post_analyze(make_supply_chain_df(), "generic analysis")
    body = r.json()
    for key in ("profile", "charts", "problem_statement"):
        assert key in body, f"Missing top-level key: '{key}'"


def integration_analyze_problem_echoed():
    prob = "Analyse defect rates by supplier"
    r    = _post_analyze(make_supply_chain_df(), prob)
    assert r.json()["problem_statement"] == prob


def integration_analyze_chart_count_bounded():
    r      = _post_analyze(make_supply_chain_df(), "generic eda")
    charts = r.json()["charts"]
    assert 1 <= len(charts) <= 6, f"Expected 1–6 charts, got {len(charts)}"


def integration_analyze_chart_required_fields():
    r      = _post_analyze(make_supply_chain_df(), "generic eda")
    charts = r.json()["charts"]
    for ch in charts:
        for field in ("chart_type", "title", "data", "insight"):
            assert field in ch, f"Chart missing field '{field}': {ch}"


def integration_analyze_chart_types_valid():
    r      = _post_analyze(make_supply_chain_df(), "generic eda")
    charts = r.json()["charts"]
    for ch in charts:
        assert ch["chart_type"] in ALL_CHARTS


def integration_analyze_no_chart_errors():
    r      = _post_analyze(make_supply_chain_df(), "generic eda")
    charts = r.json()["charts"]
    for ch in charts:
        assert "error" not in ch, f"Chart '{ch['title']}' has error: {ch['error']}"


def integration_analyze_profile_shape():
    df = make_supply_chain_df()
    r  = _post_analyze(df, "generic eda")
    p  = r.json()["profile"]
    assert p["shape"]["rows"] == len(df)
    assert p["shape"]["cols"] == len(df.columns)


def integration_analyze_histogram_data():
    r      = _post_analyze(make_supply_chain_df(), "distribution of prices")
    charts = r.json()["charts"]
    hists  = [c for c in charts if c["chart_type"] == "histogram"]
    assert len(hists) >= 1, "Expected at least one histogram for 'distribution' keyword"
    for h in hists:
        assert "bin_centers" in h["data"]
        assert "counts"      in h["data"]
        assert len(h["data"]["bin_centers"]) == len(h["data"]["counts"])


def integration_analyze_scatter_pearson():
    r       = _post_analyze(make_supply_chain_df(), "correlation between features")
    charts  = r.json()["charts"]
    scatters = [c for c in charts if c["chart_type"] == "scatter"]
    assert len(scatters) >= 1, "Expected at least one scatter for 'correlation' keyword"
    for sc in scatters:
        assert "pearson_r" in sc["data"]
        assert "p_value"   in sc["data"]
        assert -1.0 <= sc["data"]["pearson_r"] <= 1.0


def integration_analyze_bar_lengths_match():
    r      = _post_analyze(make_supply_chain_df(), "compare average revenue by product type")
    charts = r.json()["charts"]
    bars   = [c for c in charts if c["chart_type"] == "bar"]
    for bar in bars:
        d = bar["data"]
        assert len(d["categories"]) == len(d["values"])


def integration_analyze_heatmap_square():
    r      = _post_analyze(make_supply_chain_df(), "show me the heatmap")
    charts = r.json()["charts"]
    hmaps  = [c for c in charts if c["chart_type"] == "heatmap"]
    assert len(hmaps) >= 1, "Expected heatmap for 'heatmap' keyword"
    for hm in hmaps:
        n = len(hm["data"]["columns"])
        assert len(hm["data"]["matrix"])    == n
        assert len(hm["data"]["matrix"][0]) == n


def integration_analyze_pie_slices():
    r      = _post_analyze(make_supply_chain_df(), "proportion breakdown of each category")
    charts = r.json()["charts"]
    pies   = [c for c in charts if c["chart_type"] == "pie"]
    assert len(pies) >= 1, "Expected pie for 'proportion' keyword"
    for pi in pies:
        assert len(pi["data"]["labels"]) == len(pi["data"]["values"])
        assert len(pi["data"]["labels"]) <= 10


def integration_analyze_keyword_bar():
    r      = _post_analyze(make_supply_chain_df(), "compare average revenue across product types")
    charts = r.json()["charts"]
    types  = [c["chart_type"] for c in charts]
    assert "bar" in types


def integration_analyze_keyword_histogram():
    r      = _post_analyze(make_supply_chain_df(), "show the distribution of defect rates")
    charts = r.json()["charts"]
    types  = [c["chart_type"] for c in charts]
    assert "histogram" in types


def integration_analyze_keyword_scatter():
    r      = _post_analyze(make_supply_chain_df(), "what is the correlation between price and revenue")
    charts = r.json()["charts"]
    types  = [c["chart_type"] for c in charts]
    assert "scatter" in types


def integration_analyze_allowed_charts_filter():
    """With only 'bar' allowed, every returned chart must be a bar."""
    r      = _post_analyze(make_supply_chain_df(), "generic analysis", allowed=["bar"])
    charts = r.json()["charts"]
    assert len(charts) >= 1
    for ch in charts:
        assert ch["chart_type"] == "bar", f"Got non-bar chart: {ch['chart_type']}"


def integration_analyze_all_charts_disabled():
    """Empty allowed_charts → 0 charts, no crash."""
    r = _post_analyze(make_supply_chain_df(), "generic analysis", allowed=[])
    assert r.status_code == 200
    assert r.json()["charts"] == []


def integration_analyze_bad_csv_400():
    r = requests.post(
        f"{API_BASE}/analyze",
        files={"file": ("bad.csv", b"this is not a csv @@@@\x00\x00", "text/csv")},
        data={"problem_statement": "test"},
        timeout=10,
    )
    assert r.status_code == 400


def integration_analyze_missing_values_csv():
    r      = _post_analyze(make_missing_values_df(), "generic analysis")
    assert r.status_code == 200
    charts = r.json()["charts"]
    assert len(charts) >= 1


def integration_analyze_numeric_only_csv():
    r      = _post_analyze(make_numeric_only_df(), "distribution and correlation")
    assert r.status_code == 200
    charts = r.json()["charts"]
    assert len(charts) >= 1


def integration_analyze_categorical_only_csv():
    r      = _post_analyze(make_categorical_only_df(), "proportion and comparison")
    assert r.status_code == 200
    charts = r.json()["charts"]
    assert len(charts) >= 1


def integration_analyze_single_row_csv():
    df = make_supply_chain_df().head(1)
    r  = _post_analyze(df, "generic")
    assert r.status_code == 200


def integration_analyze_insights_are_strings():
    r      = _post_analyze(make_supply_chain_df(), "generic eda")
    charts = r.json()["charts"]
    for ch in charts:
        assert isinstance(ch["insight"], str)


def integration_analyze_chart_titles_non_empty():
    r      = _post_analyze(make_supply_chain_df(), "generic eda")
    charts = r.json()["charts"]
    for ch in charts:
        assert len(ch["title"].strip()) > 0, "Chart title must not be empty"


# ══════════════════════════════════════════════════════════════════════════════
# pytest-compatible wrappers  (each test_ function = one pytest case)
# ══════════════════════════════════════════════════════════════════════════════

# Unit
def test_unit_profile_shape():                    unit_profile_shape()
def test_unit_profile_numeric_columns():          unit_profile_numeric_columns()
def test_unit_profile_categorical_columns():      unit_profile_categorical_columns()
def test_unit_profile_missing_values_counted():   unit_profile_missing_values_counted()
def test_unit_profile_correlations_sorted():      unit_profile_correlations_sorted()
def test_unit_profile_correlations_capped():      unit_profile_correlations_capped_at_10()
def test_unit_profile_numeric_summary_keys():     unit_profile_numeric_summary_keys()
def test_unit_profile_categorical_summary():      unit_profile_categorical_summary_unique()
def test_unit_profile_numeric_only():             unit_profile_numeric_only_df()
def test_unit_profile_categorical_only():         unit_profile_categorical_only_df()
def test_unit_intent_histogram():                 unit_intent_histogram()
def test_unit_intent_scatter():                   unit_intent_scatter()
def test_unit_intent_bar():                       unit_intent_bar()
def test_unit_intent_box():                       unit_intent_box()
def test_unit_intent_line():                      unit_intent_line()
def test_unit_intent_pie():                       unit_intent_pie()
def test_unit_intent_heatmap():                   unit_intent_heatmap()
def test_unit_intent_multiple():                  unit_intent_multiple()
def test_unit_intent_none():                      unit_intent_none()
def test_unit_intent_case_insensitive():          unit_intent_case_insensitive()
def test_unit_col_mentioned_exact():              unit_col_mentioned_exact()
def test_unit_col_mentioned_multi():              unit_col_mentioned_multi()
def test_unit_col_mentioned_none():               unit_col_mentioned_none()
def test_unit_col_mentioned_case_insensitive():   unit_col_mentioned_case_insensitive()
def test_unit_plan_max_6():                       unit_plan_max_6_charts()
def test_unit_plan_at_least_1():                  unit_plan_at_least_1_chart()
def test_unit_plan_respects_allowed():            unit_plan_respects_allowed_charts()
def test_unit_plan_no_duplicates():               unit_plan_no_duplicate_keys()
def test_unit_plan_histogram_keyword():           unit_plan_histogram_keyword()
def test_unit_plan_scatter_keyword():             unit_plan_scatter_keyword()
def test_unit_plan_bar_keyword():                 unit_plan_bar_keyword()
def test_unit_plan_heatmap_keyword():             unit_plan_heatmap_keyword()
def test_unit_plan_pie_keyword():                 unit_plan_pie_keyword()
def test_unit_plan_column_name_axis():            unit_plan_column_name_used_as_axis()
def test_unit_plan_numeric_only_fallback():       unit_plan_structure_fallback_numeric_only()
def test_unit_plan_categorical_only_fallback():   unit_plan_structure_fallback_categorical_only()
def test_unit_plan_empty_allowed():               unit_plan_empty_allowed_charts()
def test_unit_plan_missing_values():              unit_plan_missing_values_df()
def test_unit_plan_all_spec_fields():             unit_plan_all_spec_fields_present()
def test_unit_build_histogram_keys():             unit_build_histogram_keys()
def test_unit_build_histogram_bins():             unit_build_histogram_bins_count()
def test_unit_build_scatter_stats():              unit_build_scatter_stats()
def test_unit_build_scatter_color():              unit_build_scatter_with_color()
def test_unit_build_bar_count():                  unit_build_bar_count_mode()
def test_unit_build_bar_mean():                   unit_build_bar_mean_mode()
def test_unit_build_bar_equal_length():           unit_build_bar_lists_equal_length()
def test_unit_build_box_keys():                   unit_build_box_single_keys()
def test_unit_build_box_iqr():                    unit_build_box_iqr_correct()
def test_unit_build_box_grouped():                unit_build_box_grouped()
def test_unit_build_heatmap_square():             unit_build_heatmap_square_matrix()
def test_unit_build_heatmap_diagonal():           unit_build_heatmap_diagonal_ones()
def test_unit_build_pie_labels():                 unit_build_pie_labels_values()
def test_unit_build_pie_max_10():                 unit_build_pie_max_10_slices()
def test_unit_build_line_lists():                 unit_build_line_lists()
def test_unit_build_invalid_col():                unit_build_invalid_column_no_crash()
def test_unit_build_no_error_on_valid():          unit_build_no_error_key_on_valid_input()
def test_unit_insight_histogram():                unit_insight_histogram_non_empty()
def test_unit_insight_histogram_skew():           unit_insight_histogram_mentions_skewness()
def test_unit_insight_scatter_corr():             unit_insight_scatter_mentions_correlation()
def test_unit_insight_scatter_range():            unit_insight_scatter_pearson_in_range()
def test_unit_insight_bar_highest():              unit_insight_bar_mentions_highest()
def test_unit_insight_box_outliers():             unit_insight_box_mentions_outliers()
def test_unit_insight_heatmap():                  unit_insight_heatmap_non_empty()
def test_unit_insight_pie():                      unit_insight_pie_mentions_categories()
def test_unit_insight_bad_col():                  unit_insight_bad_col_no_crash()

import pytest
# Integration tests are skipped automatically by pytest unless server is up
@pytest.fixture(scope="session", autouse=False)
def _server_check():
    try:
        requests.get(f"{API_BASE}/health", timeout=2)
    except Exception:
        pytest.skip("PriSm API server not running — skipping integration tests")

def test_integration_health_200(_server_check):                integration_health_200()
def test_integration_health_payload(_server_check):            integration_health_payload()
def test_integration_analyze_200(_server_check):               integration_analyze_200()
def test_integration_analyze_top_level_keys(_server_check):    integration_analyze_top_level_keys()
def test_integration_analyze_problem_echoed(_server_check):    integration_analyze_problem_echoed()
def test_integration_analyze_chart_count(_server_check):       integration_analyze_chart_count_bounded()
def test_integration_analyze_chart_fields(_server_check):      integration_analyze_chart_required_fields()
def test_integration_analyze_chart_types(_server_check):       integration_analyze_chart_types_valid()
def test_integration_analyze_no_errors(_server_check):         integration_analyze_no_chart_errors()
def test_integration_analyze_profile_shape(_server_check):     integration_analyze_profile_shape()
def test_integration_analyze_histogram(_server_check):         integration_analyze_histogram_data()
def test_integration_analyze_scatter(_server_check):           integration_analyze_scatter_pearson()
def test_integration_analyze_bar_lengths(_server_check):       integration_analyze_bar_lengths_match()
def test_integration_analyze_heatmap(_server_check):           integration_analyze_heatmap_square()
def test_integration_analyze_pie(_server_check):               integration_analyze_pie_slices()
def test_integration_keyword_bar(_server_check):               integration_analyze_keyword_bar()
def test_integration_keyword_histogram(_server_check):         integration_analyze_keyword_histogram()
def test_integration_keyword_scatter(_server_check):           integration_analyze_keyword_scatter()
def test_integration_allowed_filter(_server_check):            integration_analyze_allowed_charts_filter()
def test_integration_empty_allowed(_server_check):             integration_analyze_all_charts_disabled()
def test_integration_bad_csv(_server_check):                   integration_analyze_bad_csv_400()
def test_integration_missing_values(_server_check):            integration_analyze_missing_values_csv()
def test_integration_numeric_only(_server_check):              integration_analyze_numeric_only_csv()
def test_integration_categorical_only(_server_check):          integration_analyze_categorical_only_csv()
def test_integration_single_row(_server_check):                integration_analyze_single_row_csv()
def test_integration_insights_strings(_server_check):          integration_analyze_insights_are_strings()
def test_integration_titles_non_empty(_server_check):          integration_analyze_chart_titles_non_empty()


# ══════════════════════════════════════════════════════════════════════════════
# Standalone runner
# ══════════════════════════════════════════════════════════════════════════════

UNIT_TESTS = [
    ("Profile: shape",                          unit_profile_shape),
    ("Profile: numeric columns",                unit_profile_numeric_columns),
    ("Profile: categorical columns",            unit_profile_categorical_columns),
    ("Profile: missing values counted",         unit_profile_missing_values_counted),
    ("Profile: correlations sorted desc",       unit_profile_correlations_sorted),
    ("Profile: correlations capped at 10",      unit_profile_correlations_capped_at_10),
    ("Profile: numeric summary keys",           unit_profile_numeric_summary_keys),
    ("Profile: categorical summary unique",     unit_profile_categorical_summary_unique),
    ("Profile: numeric-only dataframe",         unit_profile_numeric_only_df),
    ("Profile: categorical-only dataframe",     unit_profile_categorical_only_df),
    ("Intent: histogram keyword",               unit_intent_histogram),
    ("Intent: scatter keyword",                 unit_intent_scatter),
    ("Intent: bar keyword",                     unit_intent_bar),
    ("Intent: box keyword",                     unit_intent_box),
    ("Intent: line keyword",                    unit_intent_line),
    ("Intent: pie keyword",                     unit_intent_pie),
    ("Intent: heatmap keyword",                 unit_intent_heatmap),
    ("Intent: multiple keywords",               unit_intent_multiple),
    ("Intent: no keywords → empty list",        unit_intent_none),
    ("Intent: case insensitive",                unit_intent_case_insensitive),
    ("ColMention: exact match",                 unit_col_mentioned_exact),
    ("ColMention: multiple columns",            unit_col_mentioned_multi),
    ("ColMention: no match",                    unit_col_mentioned_none),
    ("ColMention: case insensitive",            unit_col_mentioned_case_insensitive),
    ("Planner: max 6 charts",                   unit_plan_max_6_charts),
    ("Planner: at least 1 chart",               unit_plan_at_least_1_chart),
    ("Planner: respects allowed_charts",        unit_plan_respects_allowed_charts),
    ("Planner: no duplicate (type,x,y) keys",   unit_plan_no_duplicate_keys),
    ("Planner: histogram keyword",              unit_plan_histogram_keyword),
    ("Planner: scatter keyword",                unit_plan_scatter_keyword),
    ("Planner: bar keyword",                    unit_plan_bar_keyword),
    ("Planner: heatmap keyword",                unit_plan_heatmap_keyword),
    ("Planner: pie keyword",                    unit_plan_pie_keyword),
    ("Planner: column name used as axis",       unit_plan_column_name_used_as_axis),
    ("Planner: numeric-only fallback",          unit_plan_structure_fallback_numeric_only),
    ("Planner: categorical-only fallback",      unit_plan_structure_fallback_categorical_only),
    ("Planner: empty allowed_charts → []",      unit_plan_empty_allowed_charts),
    ("Planner: handles missing values",         unit_plan_missing_values_df),
    ("Planner: all spec fields present",        unit_plan_all_spec_fields_present),
    ("Build histogram: keys present",           unit_build_histogram_keys),
    ("Build histogram: 30 bins",                unit_build_histogram_bins_count),
    ("Build scatter: Pearson stats",            unit_build_scatter_stats),
    ("Build scatter: color list attached",      unit_build_scatter_with_color),
    ("Build bar: count mode (no y_col)",        unit_build_bar_count_mode),
    ("Build bar: mean mode (with y_col)",       unit_build_bar_mean_mode),
    ("Build bar: categories == values length",  unit_build_bar_lists_equal_length),
    ("Build box: single — q1/median/q3/iqr",    unit_build_box_single_keys),
    ("Build box: IQR = Q3 − Q1",                unit_build_box_iqr_correct),
    ("Build box: grouped by color_col",         unit_build_box_grouped),
    ("Build heatmap: square matrix",            unit_build_heatmap_square_matrix),
    ("Build heatmap: diagonal = 1.0",           unit_build_heatmap_diagonal_ones),
    ("Build pie: labels & values present",      unit_build_pie_labels_values),
    ("Build pie: ≤ 10 slices",                  unit_build_pie_max_10_slices),
    ("Build line: x & y lists",                 unit_build_line_lists),
    ("Build: invalid col → no crash",           unit_build_invalid_column_no_crash),
    ("Build: no 'error' key on valid input",    unit_build_no_error_key_on_valid_input),
    ("Insight histogram: non-empty",            unit_insight_histogram_non_empty),
    ("Insight histogram: mentions skewness",    unit_insight_histogram_mentions_skewness),
    ("Insight scatter: mentions correlation",   unit_insight_scatter_mentions_correlation),
    ("Insight scatter: Pearson r in [-1,1]",    unit_insight_scatter_pearson_in_range),
    ("Insight bar: mentions highest",           unit_insight_bar_mentions_highest),
    ("Insight box: mentions outliers/median",   unit_insight_box_mentions_outliers),
    ("Insight heatmap: non-empty",              unit_insight_heatmap_non_empty),
    ("Insight pie: non-empty",                  unit_insight_pie_mentions_categories),
    ("Insight: bad col → no crash",             unit_insight_bad_col_no_crash),
]

INTEGRATION_TESTS = [
    ("GET /health → 200",                       integration_health_200),
    ("GET /health payload (status+app)",        integration_health_payload),
    ("POST /analyze → 200",                     integration_analyze_200),
    ("Response has profile/charts/statement",   integration_analyze_top_level_keys),
    ("Problem statement echoed back",           integration_analyze_problem_echoed),
    ("Chart count 1–6",                         integration_analyze_chart_count_bounded),
    ("Each chart has required fields",          integration_analyze_chart_required_fields),
    ("Chart types all valid",                   integration_analyze_chart_types_valid),
    ("No chart has 'error' key",                integration_analyze_no_chart_errors),
    ("Profile shape matches uploaded CSV",      integration_analyze_profile_shape),
    ("Histogram: bin_centers + counts",         integration_analyze_histogram_data),
    ("Scatter: pearson_r in [-1, 1]",           integration_analyze_scatter_pearson),
    ("Bar: categories == values length",        integration_analyze_bar_lengths_match),
    ("Heatmap: square NxN matrix",              integration_analyze_heatmap_square),
    ("Pie: labels == values, ≤ 10 slices",      integration_analyze_pie_slices),
    ("Keyword 'compare' → bar in results",      integration_analyze_keyword_bar),
    ("Keyword 'distribution' → histogram",      integration_analyze_keyword_histogram),
    ("Keyword 'correlation' → scatter",         integration_analyze_keyword_scatter),
    ("allowed_charts=['bar'] → only bars",      integration_analyze_allowed_charts_filter),
    ("allowed_charts=[] → empty charts list",   integration_analyze_all_charts_disabled),
    ("Bad CSV → HTTP 400",                      integration_analyze_bad_csv_400),
    ("CSV with NaN → no crash",                 integration_analyze_missing_values_csv),
    ("Numeric-only CSV → charts returned",      integration_analyze_numeric_only_csv),
    ("Categorical-only CSV → charts returned",  integration_analyze_categorical_only_csv),
    ("Single-row CSV → no crash",               integration_analyze_single_row_csv),
    ("Insights are strings",                    integration_analyze_insights_are_strings),
    ("Chart titles non-empty",                  integration_analyze_chart_titles_non_empty),
]


def _server_is_up() -> bool:
    try:
        requests.get(f"{API_BASE}/health", timeout=2)
        return True
    except Exception:
        return False


def run_suite(name: str, tests: list[tuple[str, Any]]):
    _section(name)
    for label, fn in tests:
        _run(label, fn)


def print_summary():
    passed = sum(1 for _, ok, _ in _results if ok)
    failed = sum(1 for _, ok, _ in _results if not ok)
    total  = len(_results)

    print(f"\n{BOLD}{'═'*60}{RESET}")
    print(f"{BOLD}  Results: {GREEN}{passed} passed{RESET}{BOLD}  "
          f"{RED}{failed} failed{RESET}{BOLD}  / {total} total{RESET}")
    print(f"{BOLD}{'═'*60}{RESET}")

    if failed:
        print(f"\n{BOLD}{RED}Failed tests:{RESET}")
        for name, ok, msg in _results:
            if not ok:
                print(f"\n  {RED}✗ {name}{RESET}")
                for line in textwrap.indent(msg, "    ").splitlines()[-8:]:
                    print(f"  {YELLOW}{line}{RESET}")

    return failed == 0


def main():
    args = sys.argv[1:]
    run_unit        = "--integration" not in args
    run_integration = "--unit"        not in args

    print(f"\n{BOLD}🔷 PriSm — Backend Test Suite{RESET}")
    print(f"   api.py target: {CYAN}{API_BASE}{RESET}")

    if run_unit:
        run_suite("LAYER 1 — Unit Tests  (no server needed)", UNIT_TESTS)

    if run_integration:
        if _server_is_up():
            run_suite("LAYER 2 — Integration Tests  (live API)", INTEGRATION_TESTS)
        else:
            print(f"\n{YELLOW}⚠  Integration tests skipped — server not reachable at {API_BASE}{RESET}")
            print(f"   Start it first:  {CYAN}uv run uvicorn api:app --reload --port 8000{RESET}")

    ok = print_summary()
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()