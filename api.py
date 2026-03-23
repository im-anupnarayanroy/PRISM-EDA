#from __future__ import annotations

import io
import json
from typing import Any

import numpy as np
import pandas as pd
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from scipy import stats

app = FastAPI(title="PriSm EDA API", version="2.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Dataset Profiler

def profile_dataframe(df: pd.DataFrame) -> dict[str, Any]:
    numeric_cols     = df.select_dtypes(include="number").columns.tolist()
    categorical_cols = df.select_dtypes(exclude="number").columns.tolist()

    profile: dict[str, Any] = {
        "shape":               {"rows": int(df.shape[0]), "cols": int(df.shape[1])},
        "columns":             df.columns.tolist(),
        "numeric_columns":     numeric_cols,
        "categorical_columns": categorical_cols,
        "missing_values":      df.isnull().sum().to_dict(),
        "dtypes":              {c: str(t) for c, t in df.dtypes.items()},
    }

    if numeric_cols:
        desc = df[numeric_cols].describe().round(4)
        profile["numeric_summary"] = desc.to_dict()

        corr  = df[numeric_cols].corr()
        pairs: list[dict] = []
        for i, c1 in enumerate(numeric_cols):
            for c2 in numeric_cols[i + 1:]:
                val = corr.loc[c1, c2]
                if not np.isnan(val):
                    pairs.append({"col1": c1, "col2": c2,
                                  "correlation": round(float(val), 4)})
        pairs.sort(key=lambda x: abs(x["correlation"]), reverse=True)
        profile["top_correlations"] = pairs[:10]

    cat_summary: dict[str, Any] = {}
    for c in categorical_cols:
        vc = df[c].value_counts()
        cat_summary[c] = {"unique": int(df[c].nunique()),
                          "top_values": vc.head(10).to_dict()}
    profile["categorical_summary"] = cat_summary

    return profile


# Heuristic Chart Planner
# Priority ladder:
# A) Keyword-driven  — problem text → intent buckets + mentioned cols
# B) Correlation-driven — top numeric pairs → scatter
# C) Structure-driven  — cat×num→bar/box, ≥4 nums→heatmap, low-card→pie
# D) Fallback          — histogram per numeric col

_INTENT_MAP: list[tuple[list[str], str]] = [
    (["distribut", "spread", "frequen", "histogram", "skew"],       "histogram"),
    (["correlat", "relation", "vs", "versus", "scatter", "impact",
      "affect", "influence", "between"],                             "scatter"),
    (["compare", "comparison", "rank", "top", "best", "worst",
      "average", "mean", "total", "sum", "highest", "lowest"],      "bar"),
    (["outlier", "variance", "quartile", "iqr", "box", "range"],    "box"),
    (["trend", "over time", "time series", "growth", "line",
      "progress", "change"],                                         "line"),
    (["proportion", "share", "breakdown", "pie", "segment",
      "percentage", "ratio"],                                        "pie"),
    (["correlation matrix", "heatmap", "all correlat",
      "feature relationship"],                                       "heatmap"),
]

def _match_intents(problem: str) -> list[str]:
    lower   = problem.lower()
    matched = []
    for keywords, chart_type in _INTENT_MAP:
        if any(kw in lower for kw in keywords):
            matched.append(chart_type)
    return matched


def _col_mentioned(problem: str, columns: list[str]) -> list[str]:
    lower = problem.lower()
    return [c for c in columns if c.lower() in lower]


def _insight_for(ctype: str, x_col: str | None, y_col: str | None,
                 color_col: str | None, df: pd.DataFrame) -> str:
    """Return a short, purely statistical insight — no LLM required."""
    try:
        if ctype == "histogram" and x_col:
            s    = df[x_col].dropna()
            skew = s.skew()
            shape = ("right-skewed" if skew > 0.5
                     else "left-skewed" if skew < -0.5
                     else "roughly symmetric")
            return (f"{x_col} is {shape} (skewness={skew:.2f}, "
                    f"mean={s.mean():.2f}, std={s.std():.2f}).")

        if ctype == "scatter" and x_col and y_col:
            sub = df[[x_col, y_col]].dropna()
            r, p = stats.pearsonr(sub[x_col], sub[y_col])
            strength  = "strong" if abs(r) > 0.7 else "moderate" if abs(r) > 0.4 else "weak"
            direction = "positive" if r > 0 else "negative"
            sig       = "statistically significant" if p < 0.05 else "not significant"
            return (f"{strength.capitalize()} {direction} correlation between "
                    f"{x_col} and {y_col} (r={r:.3f}, p={p:.4f}, {sig}).")

        if ctype == "bar" and x_col:
            if y_col and y_col in df.select_dtypes(include="number").columns:
                grp = df.groupby(x_col)[y_col].mean()
                top = grp.idxmax()
                return f"'{top}' has the highest average {y_col} ({grp[top]:.2f})."
            top = df[x_col].value_counts().idxmax()
            cnt = df[x_col].value_counts().max()
            return f"'{top}' is the most frequent value in {x_col} ({cnt} occurrences)."

        if ctype == "box" and x_col:
            col = y_col or x_col
            s   = df[col].dropna()
            q1, q3 = s.quantile(0.25), s.quantile(0.75)
            iqr = q3 - q1
            n_out = int(((s < q1 - 1.5 * iqr) | (s > q3 + 1.5 * iqr)).sum())
            return (f"{col}: median={s.median():.2f}, IQR={iqr:.2f}, "
                    f"{n_out} outlier(s) detected.")

        if ctype == "heatmap":
            return "Correlation matrix — red/blue intensity shows relationship strength."

        if ctype == "pie" and x_col:
            return f"{x_col} has {df[x_col].nunique()} categories shown proportionally."

        if ctype == "line" and x_col and y_col:
            sub = df[[x_col, y_col]].dropna().sort_values(x_col)
            return (f"{y_col} ranges from {sub[y_col].min():.2f} to "
                    f"{sub[y_col].max():.2f} across {x_col}.")
    except Exception:
        pass
    return ""


def plan_charts(
    problem: str,
    profile: dict[str, Any],
    allowed_charts: list[str],
    df: pd.DataFrame,
) -> list[dict[str, Any]]:
    num_cols    = profile["numeric_columns"]
    cat_cols    = profile["categorical_columns"]
    all_cols    = profile["columns"]
    corr_pairs  = profile.get("top_correlations", [])

    specs: list[dict[str, Any]] = []
    seen: set[tuple] = set()

    def add(ctype, title, x_col, y_col, color_col=None):
        if ctype not in allowed_charts:
            return
        key = (ctype, x_col, y_col)
        if key in seen:
            return
        seen.add(key)
        specs.append({
            "chart_type": ctype,
            "title":      title,
            "x_col":      x_col,
            "y_col":      y_col,
            "color_col":  color_col,
            "insight":    _insight_for(ctype, x_col, y_col, color_col, df),
        })

    intent_types  = _match_intents(problem)
    mentioned     = _col_mentioned(problem, all_cols)
    mentioned_num = [c for c in mentioned if c in num_cols]
    mentioned_cat = [c for c in mentioned if c in cat_cols]

    # ── A) Keyword × column combos ────────────────────────────
    for ctype in intent_types:
        if len(specs) >= 6:
            break

        if ctype == "histogram":
            for c in (mentioned_num or num_cols)[:2]:
                add("histogram", f"Distribution of {c}", c, None)

        elif ctype == "scatter":
            if len(mentioned_num) >= 2:
                add("scatter", f"{mentioned_num[0]} vs {mentioned_num[1]}",
                    mentioned_num[0], mentioned_num[1],
                    mentioned_cat[0] if mentioned_cat else None)
            elif corr_pairs:
                p = corr_pairs[0]
                add("scatter",
                    f"{p['col1']} vs {p['col2']} (r={p['correlation']})",
                    p["col1"], p["col2"],
                    cat_cols[0] if cat_cols else None)

        elif ctype == "bar":
            x = mentioned_cat[0] if mentioned_cat else (cat_cols[0] if cat_cols else None)
            y = mentioned_num[0] if mentioned_num else (num_cols[0] if num_cols else None)
            if x:
                add("bar", f"Avg {y} by {x}" if y else f"Count by {x}", x, y)

        elif ctype == "box":
            x     = mentioned_num[0] if mentioned_num else (num_cols[0] if num_cols else None)
            color = mentioned_cat[0] if mentioned_cat else (cat_cols[0] if cat_cols else None)
            if x:
                lbl = f"{x} Distribution" + (f" by {color}" if color else "")
                add("box", lbl, x, None, color)

        elif ctype == "pie":
            x = mentioned_cat[0] if mentioned_cat else None
            if not x:
                x = next((c for c in cat_cols if df[c].nunique() <= 8), None)
            if x:
                add("pie", f"Breakdown of {x}", x, None)

        elif ctype == "line":
            x = mentioned_num[0] if mentioned_num else (num_cols[0] if num_cols else None)
            y = (mentioned_num[1] if len(mentioned_num) > 1
                 else (num_cols[1] if len(num_cols) > 1 else None))
            if x and y:
                add("line", f"{y} over {x}", x, y)

        elif ctype == "heatmap":
            if num_cols:
                add("heatmap", "Correlation Heatmap", None, None)

    # ── B) Top correlated pairs → scatter ─────────────────────
    for pair in corr_pairs[:2]:
        if len(specs) >= 6:
            break
        add("scatter",
            f"{pair['col1']} vs {pair['col2']} (r={pair['correlation']})",
            pair["col1"], pair["col2"],
            cat_cols[0] if cat_cols else None)

    # ── C) Structure-driven fallbacks ─────────────────────────
    if cat_cols and num_cols and len(specs) < 6:
        best_num = max(num_cols, key=lambda c: df[c].std() if not np.isnan(df[c].std()) else 0)
        add("bar", f"Avg {best_num} by {cat_cols[0]}", cat_cols[0], best_num)

    if cat_cols and num_cols and len(specs) < 6:
        add("box", f"{num_cols[0]} by {cat_cols[0]}", num_cols[0], None, cat_cols[0])

    if len(num_cols) >= 4 and len(specs) < 6:
        add("heatmap", "Correlation Heatmap", None, None)

    for c in cat_cols:
        if len(specs) >= 6:
            break
        if df[c].nunique() <= 6:
            add("pie", f"Breakdown of {c}", c, None)
            break

    # ── D) Histogram fallback ─────────────────────────────────
    for c in num_cols:
        if len(specs) >= 6:
            break
        add("histogram", f"Distribution of {c}", c, None)

    return specs[:6]


# Chart Data Builder

def build_chart_payload(df: pd.DataFrame, chart_spec: dict[str, Any]) -> dict[str, Any]:
    ctype     = chart_spec["chart_type"]
    x_col     = chart_spec.get("x_col")
    y_col     = chart_spec.get("y_col")
    color_col = chart_spec.get("color_col")

    def safe(c):
        return c if c and c in df.columns else None

    x_col, y_col, color_col = safe(x_col), safe(y_col), safe(color_col)

    payload: dict[str, Any] = {
        "chart_type": ctype,
        "title":      chart_spec.get("title", ctype),
        "insight":    chart_spec.get("insight", ""),
        "x_col":      x_col,
        "y_col":      y_col,
        "color_col":  color_col,
        "data":       {},
    }

    try:
        if ctype == "histogram" and x_col:
            series = df[x_col].dropna()
            counts, bin_edges = np.histogram(series, bins=30)
            payload["data"] = {
                "bin_centers": ((bin_edges[:-1] + bin_edges[1:]) / 2).tolist(),
                "counts":      counts.tolist(),
                "x_label":     x_col,
                "normality": {
                    "skewness": round(float(series.skew()), 4),
                    "kurtosis": round(float(series.kurtosis()), 4),
                },
            }

        elif ctype == "scatter" and x_col and y_col:
            sub = df[[x_col, y_col]].dropna()
            r, p = stats.pearsonr(sub[x_col], sub[y_col])
            payload["data"] = {
                "x":         sub[x_col].tolist(),
                "y":         sub[y_col].tolist(),
                "pearson_r": round(float(r), 4),
                "p_value":   round(float(p), 6),
            }
            if color_col:
                payload["data"]["color"] = df.loc[sub.index, color_col].tolist()

        elif ctype == "bar" and x_col:
            if y_col and y_col in df.select_dtypes(include="number").columns:
                grp = df.groupby(x_col)[y_col].mean().nlargest(15)
            else:
                grp = df[x_col].value_counts().head(15)
            payload["data"] = {
                "categories": [str(k) for k in grp.index.tolist()],
                "values":     [round(float(v), 4) for v in grp.values.tolist()],
                "x_label":    x_col,
                "y_label":    y_col or "count",
            }

        elif ctype == "box" and x_col:
            numeric_col = y_col if y_col else x_col
            if color_col and color_col in df.select_dtypes(exclude="number").columns:
                groups: dict[str, list] = {}
                for grp_name, grp_df in df.groupby(color_col)[numeric_col]:
                    groups[str(grp_name)] = grp_df.dropna().tolist()
                payload["data"] = {"groups": groups, "y_label": numeric_col}
            else:
                s = df[numeric_col].dropna()
                q1, q3 = float(s.quantile(0.25)), float(s.quantile(0.75))
                payload["data"] = {
                    "values": s.tolist(),
                    "q1": q1, "median": float(s.median()), "q3": q3,
                    "iqr": q3 - q1, "y_label": numeric_col,
                }

        elif ctype == "heatmap":
            n_cols = df.select_dtypes(include="number").columns.tolist()
            corr   = df[n_cols].corr().round(4)
            payload["data"] = {"columns": n_cols, "matrix": corr.values.tolist()}

        elif ctype == "line" and x_col and y_col:
            sub = df[[x_col, y_col]].dropna().sort_values(x_col)
            payload["data"] = {"x": sub[x_col].tolist(), "y": sub[y_col].tolist()}

        elif ctype == "pie" and x_col:
            vc = df[x_col].value_counts().head(10)
            payload["data"] = {
                "labels": [str(k) for k in vc.index.tolist()],
                "values": vc.values.tolist(),
            }

    except Exception as exc:
        payload["error"] = str(exc)

    return payload


# Endpoints

@app.post("/analyze")
async def analyze(
    file: UploadFile = File(...),
    problem_statement: str = Form(...),
    allowed_charts: str = Form('["histogram","scatter","bar","box","heatmap","line","pie"]'),
):
    try:
        contents = await file.read()
        df = pd.read_csv(io.BytesIO(contents))
    except Exception:
        raise HTTPException(status_code=400, detail="Could not parse CSV file.")

    try:
        charts_list: list[str] = json.loads(allowed_charts)
    except Exception:
        charts_list = ["histogram", "scatter", "bar", "box", "heatmap", "line", "pie"]

    profile        = profile_dataframe(df)
    chart_specs    = plan_charts(problem_statement, profile, charts_list, df)
    chart_payloads = [build_chart_payload(df, spec) for spec in chart_specs]

    return {
        "profile":           profile,
        "charts":            chart_payloads,
        "problem_statement": problem_statement,
    }


@app.get("/health")
def health():
    return {"status": "ok", "app": "PriSm"}