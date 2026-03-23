import streamlit as st
import requests
import base64

st.set_page_config(page_title="PriSm | Automated EDA", layout="wide")

st.title("📊 PriSm: Automated EDA Pipeline")
st.write("Upload your dataset, define your problem statement, and configure your visual outputs.")

uploaded_file = st.file_uploader("Upload Dataset (CSV)", type=["csv"])

problem_statement = st.text_area(
    "Problem Statement", 
    placeholder="E.g., Identify the correlation between manufacturing costs and defect rates."
)

plot_options = ["Histogram", "Scatter Plot", "Bar Chart"]
selected_plots = st.multiselect("Select Visualizations", plot_options, default=["Histogram"])

if st.button("Process Data", type="primary"):
    if not uploaded_file or not problem_statement.strip() or not selected_plots:
        st.error("Please provide a CSV, a problem statement, and at least one plot type.")
    else:
        with st.spinner("PriSm is analyzing your data..."):
            files = {"file": (uploaded_file.name, uploaded_file.getvalue(), "text/csv")}
            data = {
                "problem_statement": problem_statement,
                "plot_types": ",".join(selected_plots)
            }
            
            try:
                # Target the FastAPI backend
                response = requests.post("http://127.0.0.1:8000/process_data", files=files, data=data)
                
                if response.status_code == 200:
                    st.success("Analysis Complete!")
                    response_data = response.json()
                    
                    st.info(f"**Target Objective:** {response_data['problem_statement_received']}")
                    
                    plots = response_data.get("plots", [])
                    if plots:
                        cols = st.columns(len(plots))
                        for idx, plot_base64 in enumerate(plots):
                            image_bytes = base64.b64decode(plot_base64)
                            with cols[idx]:
                                st.image(image_bytes, use_container_width=True)
                    else:
                        st.warning("No plots generated. Ensure dataset contains required data types (e.g., numeric columns for scatter plots).")
                else:
                    st.error(f"PriSm API Error: {response.status_code}")
            except requests.exceptions.ConnectionError:
                st.error("Backend unreachable. Ensure the PriSm API (FastAPI) is running on port 8000.")