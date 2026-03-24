from app.repository.data_loader import DataLoader

class AnalyticsService:

    def __init__(self):
        self.df = DataLoader().load_all()

    def top_products(self):
        return (
            self.df.groupby("product_id")["revenue"]
            .sum()
            .sort_values(ascending=False)
            .head(10)
        )

    def inventory_risk(self):
        return self.df[self.df["stock_gap"] > 0]
