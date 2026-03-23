# PriSm: Automated EDA Pipeline

PriSm is a robust, client-server application designed to automate Exploratory Data Analysis (EDA). It pairs a highly interactive **Streamlit** frontend for user configuration with a fast, scalable **FastAPI** backend that handles heavy data processing and dynamic visualization generation.

## Features
* **Decoupled Architecture**: Clean separation between the UI (Client) and the processing engine (Server).
* **Automated Visualizations**: Automatically generates Histograms, Scatter Plots, and Bar Charts based on user selection.
* **Modern Dependency Management**: Built and managed entirely with `uv` for lightning-fast, reproducible virtual environments.

## Project Structure
```
prism/
├── .venv/                      # Virtual environment (managed by uv)
├── pyproject.toml              # Project metadata and dependencies
├── uv.lock                     # Lockfile for reproducible builds
├── backend.py                  # FastAPI backend (Data processing & EDA)
├── frontend.py                 # Streamlit frontend (UI & user inputs)
├── README.md                   # Project documentation
└── supply_chain_data.csv       # Sample dataset for testing
```


# uv sync

# Start backend API: 
# uv run uvicorn backend:app --reload --port 8000 
# The API will be available at http://127.0.0.1:8000

# Test backend API first before running frontend
# uv run python test_backend.py
```
this should show something like this:

Sending request to http://127.0.0.1:8000/process_data...

✅ Success! API is working perfectly.

Message: EDA completed successfully.
Problem Statement Acknowledged: Testing the PriSm backend with supply chain data.
Number of plots successfully generated and encoded: 3
(The base64 image strings are ready to be rendered by the frontend!)

```

# start frontend APP: 
# uv run streamlit run frontend.py
# The UI will open in your default browser, typically at http://localhost:8501

```
Open the Streamlit UI in your browser.

Upload your target .csv dataset (e.g., supply_chain_data.csv).

Enter your specific problem statement or objective in the text area.

Select the desired visualization types (Histogram, Scatter Plot, Bar Chart).

Click Process Data to trigger the API. The backend will analyze the data and return the generated plots directly to your screen.

```


```

This dataset is rich because it spans the entire supply chain lifecycle—from manufacturing and suppliers to shipping and sales. Since you are building an automated EDA pipeline, the best problem statements should be multi-variate, forcing the tool to analyze relationships across different stages of the data.

Here are some complex, advanced problem statements you can feed into PriSm, along with the specific EDA approaches that would solve them:

1. The Cost-to-Serve Optimization Problem

Problem Statement: "Identify the most cost-efficient combinations of Transportation Modes, Routes, and Shipping Carriers without compromising Shipping Times or increasing Defect Rates."

Why it's complex: It requires analyzing the trade-offs between logistics (modes, routes, carriers) and their financial impact (shipping costs, overall costs) while ensuring quality (defect rates) and speed (shipping times) don't degrade.

Ideal PriSm Visualizations:

Scatter Plot: Shipping times vs. Shipping costs (colored by Transportation modes).

Bar Chart: Average Costs grouped by Routes and Shipping carriers.

2. Supplier Risk & Quality Control Analysis

Problem Statement: "Determine if specific Suppliers, Locations, or Manufacturing Lead Times are driving higher Defect Rates and failing Inspection Results."

Why it's complex: This is a precursor to predictive maintenance or vendor-scoring models. It correlates upstream manufacturing variables with downstream quality assurance outcomes.

Ideal PriSm Visualizations:

Bar Chart: Average Defect rates grouped by Supplier name or Location.

Scatter Plot: Manufacturing lead time vs. Defect rates (colored by Inspection results - Pass/Fail/Pending).

3. Inventory Efficiency and Demand Fulfillment

Problem Statement: "Analyze the relationship between Stock Levels, Order Quantities, and Lead Times to identify product types that are at risk of overstocking (capital tie-up) or understocking (missed revenue)."

Why it's complex: This touches on inventory optimization. High availability but low order quantities mean dead stock; low availability with high sales means stockouts.

Ideal PriSm Visualizations:

Scatter Plot: Stock levels vs. Number of products sold (colored by Product type).

Histogram: Distribution of Lead times overlaying different Product types.

4. Profitability and Margin Erosion

Problem Statement: "Evaluate which Product Types and Customer Demographics generate the highest net margins by comparing Revenue Generated against the sum of Manufacturing Costs, Shipping Costs, and general Costs."

Why it's complex: It requires engineering a new understanding of "Profit" from multiple cost columns and mapping it against demographic sales data to find the most lucrative market segments.

Ideal PriSm Visualizations:

Bar Chart: Revenue generated vs. combined Costs grouped by Product type.

Scatter Plot: Price vs Number of products sold (colored by Customer demographics) to find pricing sweet spots.

5. Production Bottleneck Identification

Problem Statement: "Investigate how Production Volumes impact Manufacturing Lead Times and Manufacturing Costs across different Locations."

Why it's complex: It seeks to find the point of diminishing returns in the manufacturing process—do larger production volumes scale efficiently, or do they cause exponential delays and cost spikes in certain regions?

Ideal PriSm Visualizations:

Scatter Plot: Production volumes vs Manufacturing Costs (colored by Location).

Scatter Plot: Production volumes vs Manufacturing lead time.

How to use these in PriSm:
You can copy and paste any of the quoted problem statements directly into your Streamlit text area. To make the pipeline even smarter in the future, you could have PriSm's backend dynamically parse these sentences (perhaps using a lightweight NLP model) to automatically select the optimal X, Y, and hue columns for the user!

```