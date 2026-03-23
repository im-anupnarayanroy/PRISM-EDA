"""
app.py  —  Streamlit EDA frontend
Run with:  uv run streamlit run app.py
"""

from __future__ import annotations

import json

import plotly.express as px
import plotly.graph_objects as go
import requests
import streamlit as st

API_URL = "http://localhost:8000/analyze"

CHART_OPTIONS = {
    "histogram": "📊 Histogram",
    "scatter": "🔵 Scatter Plot",
    "bar": "📈 Bar Chart",
    "box": "📦 Box Plot",
    "heatmap": "🌡️ Correlation Heatmap",
    "line": "📉 Line Chart",
    "pie": "🥧 Pie Chart",
}

COLOR_PALETTE = px.colors.qualitative.Pastel


# ─────────────────────────────────────────────
# Page config
# ─────────────────────────────────────────────
st.set_page_config(
    page_title="PriSm — EDA",
    page_icon="🔷",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(
    """
    <style>
        .block-container { padding-top: 2rem; }
        .stAlert { border-radius: 10px; }
        h1 { color: #4F8BF9; }
    </style>
    """,
    unsafe_allow_html=True,
)


# ─────────────────────────────────────────────
# Sidebar — configuration
# ─────────────────────────────────────────────
with st.sidebar:
    st.markdown("### 🔷 PriSm — Configuration")
    st.markdown("---")

    st.subheader("📊 Chart Types to Enable")
    selected_charts = []
    for key, label in CHART_OPTIONS.items():
        if st.checkbox(label, value=True, key=f"chart_{key}"):
            selected_charts.append(key)

    st.markdown("---")
    st.subheader("🎨 Visual Settings")
    chart_height = st.slider("Chart height (px)", 300, 800, 450, step=50)
    show_insights = st.toggle("Show AI insights below charts", value=True)
    show_profile = st.toggle("Show dataset profile", value=True)

    st.markdown("---")
    st.subheader("🔗 API")
    api_url_input = st.text_input("Backend URL", value=API_URL)


# ─────────────────────────────────────────────
# Main area
# ─────────────────────────────────────────────
st.markdown(
    "<h1 style='letter-spacing:3px; margin-bottom:0;'>"
    "Pri<span style='color:#4F8BF9;'>Sm</span></h1>"
    "<p style='color:grey; margin-top:0;'>"
    "<b>Precision Insights Machine</b> — upload a CSV, describe your goal, "
    "and PriSm selects the most relevant charts automatically.</p>",
    unsafe_allow_html=True,
)

col1, col2 = st.columns([1, 2])

with col1:
    uploaded_file = st.file_uploader(
        "📂 Upload your CSV dataset",
        type=["csv"],
        help="Upload any CSV file. Column types are auto-detected.",
    )

with col2:
    problem_statement = st.text_area(
        "💬 Problem Statement",
        height=120,
        placeholder=(
            "Describe what you want to analyse.\n\n"
            "Example: 'Which product types have the highest revenue and how does "
            "defect rate correlate with manufacturing cost?'"
        ),
    )

# Quick preview
if uploaded_file is not None:
    import pandas as pd

    preview_df = pd.read_csv(uploaded_file)
    uploaded_file.seek(0)  # reset for later upload

    with st.expander(f"👀 Preview — {preview_df.shape[0]} rows × {preview_df.shape[1]} cols", expanded=False):
        st.dataframe(preview_df.head(20), use_container_width=True)

st.markdown("---")

process_btn = st.button(
    "⚡ Process Data",
    type="primary",
    disabled=(uploaded_file is None or not problem_statement.strip() or not selected_charts),
    use_container_width=True,
)

if uploaded_file is None:
    st.info("⬆️ Upload a CSV file to get started.")
elif not problem_statement.strip():
    st.warning("✏️ Please enter a problem statement.")
elif not selected_charts:
    st.warning("🔧 Enable at least one chart type in the sidebar.")


# ─────────────────────────────────────────────
# Render helpers
# ─────────────────────────────────────────────
def render_histogram(data: dict, title: str, height: int) -> go.Figure:
    fig = go.Figure(
        go.Bar(
            x=data["bin_centers"],
            y=data["counts"],
            marker_color="#4F8BF9",
            name=data.get("x_label", "value"),
        )
    )
    fig.update_layout(
        title=title,
        xaxis_title=data.get("x_label", ""),
        yaxis_title="Frequency",
        height=height,
        bargap=0.05,
    )
    return fig


def render_scatter(data: dict, title: str, x_col: str, y_col: str, height: int) -> go.Figure:
    if "color" in data:
        fig = px.scatter(
            x=data["x"],
            y=data["y"],
            color=data["color"],
            labels={"x": x_col, "y": y_col},
            title=title,
            height=height,
            color_discrete_sequence=COLOR_PALETTE,
        )
    else:
        fig = go.Figure(
            go.Scatter(
                x=data["x"],
                y=data["y"],
                mode="markers",
                marker=dict(color="#4F8BF9", opacity=0.6, size=6),
            )
        )
        fig.update_layout(
            title=title,
            xaxis_title=x_col,
            yaxis_title=y_col,
            height=height,
        )
    return fig


def render_bar(data: dict, title: str, height: int) -> go.Figure:
    fig = go.Figure(
        go.Bar(
            x=data["categories"],
            y=data["values"],
            marker_color="#7EC8E3",
            text=[f"{v:,.2f}" for v in data["values"]],
            textposition="outside",
        )
    )
    fig.update_layout(
        title=title,
        xaxis_title=data.get("x_label", ""),
        yaxis_title=data.get("y_label", "value"),
        height=height,
        xaxis_tickangle=-35,
    )
    return fig


def render_box(data: dict, title: str, height: int) -> go.Figure:
    if "groups" in data:
        fig = go.Figure()
        for grp_name, values in data["groups"].items():
            fig.add_trace(go.Box(y=values, name=grp_name, boxmean=True))
        fig.update_layout(title=title, yaxis_title=data.get("y_label", ""), height=height)
    else:
        fig = go.Figure(go.Box(y=data["values"], name=data.get("y_label", ""), boxmean=True))
        fig.update_layout(title=title, height=height)
    return fig


def render_heatmap(data: dict, title: str, height: int) -> go.Figure:
    fig = go.Figure(
        go.Heatmap(
            z=data["matrix"],
            x=data["columns"],
            y=data["columns"],
            colorscale="RdBu",
            zmid=0,
            text=[[f"{v:.2f}" for v in row] for row in data["matrix"]],
            texttemplate="%{text}",
        )
    )
    fig.update_layout(title=title, height=height)
    return fig


def render_line(data: dict, title: str, x_col: str, y_col: str, height: int) -> go.Figure:
    fig = go.Figure(
        go.Scatter(
            x=data["x"],
            y=data["y"],
            mode="lines+markers",
            line=dict(color="#4F8BF9"),
        )
    )
    fig.update_layout(
        title=title,
        xaxis_title=x_col,
        yaxis_title=y_col,
        height=height,
    )
    return fig


def render_pie(data: dict, title: str, height: int) -> go.Figure:
    fig = go.Figure(
        go.Pie(
            labels=data["labels"],
            values=data["values"],
            hole=0.3,
            marker=dict(colors=COLOR_PALETTE),
        )
    )
    fig.update_layout(title=title, height=height)
    return fig


def render_chart(chart: dict, height: int) -> go.Figure | None:
    ctype = chart.get("chart_type")
    data = chart.get("data", {})
    title = chart.get("title", ctype)
    x_col = chart.get("x_col") or ""
    y_col = chart.get("y_col") or ""

    if chart.get("error"):
        st.error(f"⚠️ Chart error: {chart['error']}")
        return None

    if ctype == "histogram":
        return render_histogram(data, title, height)
    elif ctype == "scatter":
        return render_scatter(data, title, x_col, y_col, height)
    elif ctype == "bar":
        return render_bar(data, title, height)
    elif ctype == "box":
        return render_box(data, title, height)
    elif ctype == "heatmap":
        return render_heatmap(data, title, height)
    elif ctype == "line":
        return render_line(data, title, x_col, y_col, height)
    elif ctype == "pie":
        return render_pie(data, title, height)
    return None


# ─────────────────────────────────────────────
# Process button handler
# ─────────────────────────────────────────────
if process_btn:
    with st.spinner("⚙️ Analysing dataset and selecting best charts…"):
        try:
            response = requests.post(
                api_url_input,
                files={"file": (uploaded_file.name, uploaded_file.getvalue(), "text/csv")},
                data={
                    "problem_statement": problem_statement,
                    "allowed_charts": json.dumps(selected_charts),
                },
                timeout=120,
            )
            response.raise_for_status()
            result = response.json()
        except requests.exceptions.ConnectionError:
            st.error(
                "❌ Could not connect to the API. "
                "Make sure the FastAPI server is running on `localhost:8000`.\n\n"
                "Run: `uv run uvicorn api:app --reload --port 8000`"
            )
            st.stop()
        except requests.exceptions.HTTPError as exc:
            st.error(f"❌ API returned an error: {exc.response.text}")
            st.stop()

    st.success("✅ Analysis complete!")

    # ── Dataset Profile ────────────────────────────────
    if show_profile:
        profile = result["profile"]
        with st.expander("📋 Dataset Profile", expanded=False):
            m1, m2, m3, m4 = st.columns(4)
            m1.metric("Rows", profile["shape"]["rows"])
            m2.metric("Columns", profile["shape"]["cols"])
            m3.metric("Numeric cols", len(profile["numeric_columns"]))
            m4.metric("Categorical cols", len(profile["categorical_columns"]))

            st.subheader("Top Correlations")
            import pandas as pd

            corr_df = pd.DataFrame(profile.get("top_correlations", []))
            if not corr_df.empty:
                corr_df["correlation"] = corr_df["correlation"].apply(lambda v: f"{v:+.4f}")
                st.dataframe(corr_df, use_container_width=True, hide_index=True)

    # ── Charts ─────────────────────────────────────────
    st.markdown("## 🔷 PriSm Charts")
    charts = result.get("charts", [])

    # Display in 2-column grid
    for i in range(0, len(charts), 2):
        cols = st.columns(2)
        for j, col in enumerate(cols):
            if i + j < len(charts):
                chart = charts[i + j]
                with col:
                    fig = render_chart(chart, chart_height)
                    if fig:
                        st.plotly_chart(fig, use_container_width=True)
                    if show_insights and chart.get("insight"):
                        st.caption(f"💡 {chart['insight']}")

    # ── Stat summary for scatter charts ───────────────
    scatter_charts = [c for c in charts if c["chart_type"] == "scatter"]
    if scatter_charts:
        with st.expander("📐 Correlation Statistics", expanded=False):
            for sc in scatter_charts:
                d = sc.get("data", {})
                if "pearson_r" in d:
                    st.markdown(
                        f"**{sc['title']}** — Pearson r = `{d['pearson_r']}`, "
                        f"p-value = `{d['p_value']}`"
                    )

    # ── Histogram stats ────────────────────────────────
    hist_charts = [c for c in charts if c["chart_type"] == "histogram"]
    if hist_charts:
        with st.expander("📐 Distribution Statistics", expanded=False):
            for hc in hist_charts:
                d = hc.get("data", {})
                if "normality" in d:
                    n = d["normality"]
                    st.markdown(
                        f"**{hc['title']}** — Skewness = `{n['skewness']}`, "
                        f"Kurtosis = `{n['kurtosis']}`"
                    )

    # ── Raw JSON (debug) ───────────────────────────────
    with st.expander("🔧 Raw API Response (JSON)", expanded=False):
        st.json(result)