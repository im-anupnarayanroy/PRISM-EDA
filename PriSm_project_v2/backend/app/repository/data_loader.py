import pandas as pd
import os
from app.core.config import settings

class DataLoader:

    def load_all(self):
        base = settings.DATA_PATH

        orders = pd.read_csv(os.path.join(base, "orders.csv"))
        products = pd.read_csv(os.path.join(base, "products.csv"))
        inventory = pd.read_csv(os.path.join(base, "inventory.csv"))

        df = orders.merge(products, on="product_id") \
                   .merge(inventory, on="product_id")

        df["revenue"] = df["quantity"] * df["price"]
        df["stock_gap"] = df["quantity"] - df["stock"]

        return df
