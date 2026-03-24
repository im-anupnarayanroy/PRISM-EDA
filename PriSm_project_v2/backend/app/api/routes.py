from fastapi import APIRouter
from app.services.analytics_service import AnalyticsService

router = APIRouter()
service = AnalyticsService()

@router.get("/top-products")
def top_products():
    return service.top_products().to_dict()

@router.get("/inventory-risk")
def inventory_risk():
    return service.inventory_risk().to_dict(orient="records")
