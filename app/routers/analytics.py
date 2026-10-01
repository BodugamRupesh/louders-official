"""Analytics router for LOUD Platform Licensing System."""

from typing import Annotated

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_admin
from app.models import AdminUser
from app.schemas import SuccessResponse
from app.services.customer_service import CustomerService
from app.services.device_service import DeviceService
from app.services.license_service import LicenseService
from app.services.product_service import ProductService
from app.utils.responses import success_response


router = APIRouter(
    prefix="/api/v1/analytics",
    tags=["Analytics"],
)


@router.get(
    "",
    response_model=SuccessResponse,
    status_code=status.HTTP_200_OK,
    summary="Get Analytics Summary",
    description="Retrieve aggregated platform analytics. Authenticated admins only.",
)
async def get_analytics(
    db: Annotated[Session, Depends(get_db)],
    current_admin: Annotated[AdminUser, Depends(get_current_admin)],
) -> SuccessResponse:
    license_stats = LicenseService.get_license_stats(db)
    device_stats = DeviceService.get_device_stats(db)
    customers = CustomerService.list_customers(db)
    products = ProductService.list_products(db)

    return success_response(
        "Analytics retrieved successfully.",
        data={
            "licenses": license_stats,
            "devices": device_stats,
            "customer_count": len(customers),
            "product_count": len(products),
        },
    )
