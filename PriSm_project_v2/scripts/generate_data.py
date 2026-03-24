import pandas as pd
import random
from datetime import datetime, timedelta

NUM_ROWS = 10000

products = ["P" + str(i) for i in range(1, 51)]
regions = ["North", "South", "East", "West"]

orders = []

for i in range(NUM_ROWS):
    orders.append({
        "order_id": i + 1,
        "product_id": random.choice(products),
        "region": random.choice(regions),
        "order_date": datetime.now() - timedelta(days=random.randint(1, 365)),
        "quantity": random.randint(1, 20)
    })

pd.DataFrame(orders).to_csv("backend/data/orders.csv", index=False)

pd.DataFrame({
    "product_id": products,
    "category": [random.choice(["Electronics","Clothing","Furniture"]) for _ in products],
    "price": [random.randint(20,500) for _ in products]
}).to_csv("backend/data/products.csv", index=False)

pd.DataFrame({
    "product_id": products,
    "stock": [random.randint(5,100) for _ in products],
    "warehouse_location": [random.choice(["Bangalore","Chennai","Hyderabad"]) for _ in products]
}).to_csv("backend/data/inventory.csv", index=False)
