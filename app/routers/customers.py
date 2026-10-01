"""
Customers Router for LOUD Platform Licensing System.
"""

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_admin, require_admin_or_owner, require_owner
from app.models import AdminUser, Customer, License
from app.schemas import (
    CustomerCreate,
    CustomerResponse,
    CustomerUpdate,
    LicenseResponse,
    SuccessResponse,
)
from app.services.customer_service import CustomerService
from app.utils.datetime_utils import get_current_time
from app.utils.responses import success_response

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/v1/customers",
    tags=["Customers"],
)


def _serialize_customer(customer: Customer) -> dict:
    """Serialize a Customer ORM model with primary license summary."""
    data = CustomerResponse.model_validate(
        customer,
        from_attributes=True,
    ).model_dump()

    licenses = list(customer.licenses) if customer.licenses else []
    data["license_count"] = len(licenses)
    if licenses:
        # Latest active license preferred
        active_lics = [l for l in licenses if l.status == "active"]
        primary = active_lics[-1] if active_lics else licenses[-1]
        data["primary_license_key"] = primary.license_key
        data["primary_license_status"] = primary.status
        data["primary_license_expiry"] = primary.expires_at.isoformat() if primary.expires_at else None
        data["primary_license_devices"] = len(primary.devices) if primary.devices else 0
        data["primary_license_max_devices"] = primary.plan.max_devices if primary.plan else 1
    else:
        data["primary_license_key"] = None
        data["primary_license_status"] = "unlicensed"
        data["primary_license_expiry"] = None
        data["primary_license_devices"] = 0
        data["primary_license_max_devices"] = 0

    return data


def _serialize_license(license_obj: License) -> dict:
    """Serialize a License ORM model."""
    return LicenseResponse.model_validate(
        license_obj,
        from_attributes=True,
    ).model_dump()



@router.get(
    "",
    response_model=SuccessResponse,
    status_code=status.HTTP_200_OK,
    summary="List Customers",
    description="Retrieve customers with optional filters. Authenticated admins only.",
)
async def list_customers(
    db: Annotated[Session, Depends(get_db)],
    current_admin: Annotated[AdminUser, Depends(get_current_admin)],
    search: str | None = Query(None, description="Search by name or email"),
    email: str | None = Query(None, description="Filter by email"),
) -> SuccessResponse:
    customers = CustomerService.list_customers(
        db,
        search=search,
        email=email,
    )

    return success_response(
        "Customers retrieved successfully.",
        data={"customers": [_serialize_customer(customer) for customer in customers]},
    )


@router.get(
    "/search",
    response_model=SuccessResponse,
    status_code=status.HTTP_200_OK,
    summary="Search Customers",
    description="Search customers by name or email. Authenticated admins only.",
)
async def search_customers(
    q: Annotated[str, Query(..., min_length=1, description="Search query")],
    db: Annotated[Session, Depends(get_db)],
    current_admin: Annotated[AdminUser, Depends(get_current_admin)],
) -> SuccessResponse:
    customers = CustomerService.search_customers(db, q)
    return success_response(
        "Customers searched successfully.",
        data={"customers": [_serialize_customer(customer) for customer in customers]},
    )


@router.get(
    "/{customer_id}",
    response_model=SuccessResponse,
    status_code=status.HTTP_200_OK,
    summary="Get Customer",
    description="Retrieve a specific customer by ID. Authenticated admins only.",
)
async def get_customer(
    customer_id: int,
    db: Annotated[Session, Depends(get_db)],
    current_admin: Annotated[AdminUser, Depends(get_current_admin)],
) -> SuccessResponse:
    customer = CustomerService.get_customer(db, customer_id)
    return success_response(
        "Customer retrieved successfully.",
        data={"customer": _serialize_customer(customer)},
    )


@router.post(
    "",
    response_model=SuccessResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create Customer",
    description="Create a new customer. Admin or Owner only.",
)
async def create_customer(
    customer_data: CustomerCreate,
    db: Annotated[Session, Depends(get_db)],
    current_admin: Annotated[AdminUser, Depends(require_admin_or_owner)],
) -> SuccessResponse:
    customer = CustomerService.create_customer(
        db,
        name=customer_data.name,
        email=customer_data.email,
        phone=customer_data.phone,
        notes=customer_data.notes,
    )
    return success_response(
        "Customer created successfully.",
        data={"customer": _serialize_customer(customer)},
    )


@router.put(
    "/{customer_id}",
    response_model=SuccessResponse,
    status_code=status.HTTP_200_OK,
    summary="Update Customer",
    description="Update an existing customer. Admin or Owner only.",
)
async def update_customer(
    customer_id: int,
    customer_data: CustomerUpdate,
    db: Annotated[Session, Depends(get_db)],
    current_admin: Annotated[AdminUser, Depends(require_admin_or_owner)],
) -> SuccessResponse:
    customer = CustomerService.update_customer(
        db,
        customer_id,
        name=customer_data.name,
        email=customer_data.email,
        phone=customer_data.phone,
        notes=customer_data.notes,
    )
    return success_response(
        "Customer updated successfully.",
        data={"customer": _serialize_customer(customer)},
    )


@router.delete(
    "/{customer_id}",
    response_model=SuccessResponse,
    status_code=status.HTTP_200_OK,
    summary="Delete Customer",
    description="Delete a customer. Admin or Owner only.",
)
async def delete_customer(
    customer_id: int,
    db: Annotated[Session, Depends(get_db)],
    current_admin: Annotated[AdminUser, Depends(require_admin_or_owner)],
) -> SuccessResponse:
    CustomerService.delete_customer(
        db,
        customer_id,
        admin_username=current_admin.username,
        admin_id=current_admin.id,
    )
    logger.info(
        "Admin '%s' (id=%s) deleted customer id=%s at %s - Result: success",
        current_admin.username,
        current_admin.id,
        customer_id,
        get_current_time().isoformat(),
    )
    return success_response(
        "Customer deleted successfully.",
        data={"customer_id": customer_id},
    )


@router.get(
    "/{customer_id}/licenses",
    response_model=SuccessResponse,
    status_code=status.HTTP_200_OK,
    summary="Get Customer Licenses",
    description="Retrieve all licenses belonging to a customer. Authenticated admins only.",
)
async def get_customer_licenses(
    customer_id: int,
    db: Annotated[Session, Depends(get_db)],
    current_admin: Annotated[AdminUser, Depends(get_current_admin)],
) -> SuccessResponse:
    licenses = CustomerService.get_customer_licenses(db, customer_id)
    return success_response(
        "Customer licenses retrieved successfully.",
        data={
            "licenses": [_serialize_license(license_obj) for license_obj in licenses],
            "count": len(licenses),
        },
    )
