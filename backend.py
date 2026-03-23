from fastapi import FastAPI, UploadFile, File, Form
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import io
import base64

app = FastAPI(title="PriSm API", description="Automated EDA Backend")

def get_image_base64():
    """Converts matplotlib plots to base64 strings."""
    buf = io.BytesIO()
    plt.savefig(buf, format="png", bbox_inches="tight")
    buf.seek(0)
    img_base64 = base64.b64encode(buf.getvalue()).decode("utf-8")
    plt.close() 
    return img_base64

@app.post("/process_data")
async def process_data(
    file: UploadFile = File(...),
    problem_statement: str = Form(...),
    plot_types: str = Form(...) 
):
    df = pd.read_csv(file.file)
    
    numeric_cols = df.select_dtypes(include=['number']).columns.tolist()
    cat_cols = df.select_dtypes(include=['object', 'category']).columns.tolist()
    
    plot_types_list = plot_types.split(",")
    generated_plots = []
    sns.set_theme(style="whitegrid")

    if "Histogram" in plot_types_list and numeric_cols:
        plt.figure(figsize=(8, 5))
        sns.histplot(df[numeric_cols[0]], kde=True, color="skyblue")
        plt.title(f"Histogram of {numeric_cols[0]}")
        generated_plots.append(get_image_base64())

    if "Scatter Plot" in plot_types_list and len(numeric_cols) >= 2:
        plt.figure(figsize=(8, 5))
        sns.scatterplot(data=df, x=numeric_cols[0], y=numeric_cols[1], color="coral")
        plt.title(f"Scatter Plot: {numeric_cols[0]} vs {numeric_cols[1]}")
        generated_plots.append(get_image_base64())

    if "Bar Chart" in plot_types_list and cat_cols and numeric_cols:
        plt.figure(figsize=(8, 5))
        top_cats = df[cat_cols[0]].value_counts().nlargest(10).index
        sns.barplot(
            data=df[df[cat_cols[0]].isin(top_cats)], 
            x=cat_cols[0], 
            y=numeric_cols[0], 
            errorbar=None, 
            palette="viridis"
        )
        plt.title(f"Bar Chart: {numeric_cols[0]} by {cat_cols[0]}")
        plt.xticks(rotation=45)
        generated_plots.append(get_image_base64())

    return {
        "message": "EDA completed successfully.",
        "problem_statement_received": problem_statement,
        "plots": generated_plots
    }