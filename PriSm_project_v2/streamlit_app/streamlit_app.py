import streamlit as st
import requests
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import os

API_URL = os.getenv("API_URL", "http://localhost:8000")

st.title("PriSm Supply Chain Dashboard")

res = requests.get(f"{API_URL}/top-products")
data = res.json()
df = pd.DataFrame(list(data.items()), columns=["Product", "Revenue"])

fig, ax = plt.subplots()
sns.barplot(x="Product", y="Revenue", data=df, ax=ax)
st.pyplot(fig)

res = requests.get(f"{API_URL}/inventory-risk")
risk_df = pd.DataFrame(res.json())
st.dataframe(risk_df)
