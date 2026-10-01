"""
Products Router for LOUD Platform Licensing System.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_admin, require_admin_or_owner, require_owner
from app.models import (
    AdminUser,
    Product,
)
from app.schemas import ProductCreate, ProductResponse, ProductStatusUpdate, ProductUpdate, SuccessResponse
from app.services.product_service import ProductService
from app.utils.responses import success_response


router = APIRouter(
    prefix="/api/v1/products",
    tags=["Products"],
)


def _serialize_product(
    product: Product,
    include_api_key: bool = True,
) -> dict:
    payload = ProductResponse.model_validate(
        product,
        from_attributes=True,
    ).model_dump()

    if not include_api_key:
        payload.pop("api_key", None)

    return payload


@router.get(
    "",
    response_model=SuccessResponse,
    status_code=status.HTTP_200_OK,
    summary="List Products",
    description="Retrieve all products. Authenticated admins only.",
)
async def list_products(
    db: Annotated[Session, Depends(get_db)],
    current_admin: Annotated[AdminUser, Depends(get_current_admin)],
    active_only: bool = Query(False, description="Filter active products only"),
) -> SuccessResponse:
    products = ProductService.list_products(db, active_only=active_only)
    return success_response(
        "Products retrieved successfully.",
        data={
            "products": [_serialize_product(product) for product in products],
            "count": len(products),
        },
    )


@router.get(
    "/search",
    response_model=SuccessResponse,
    status_code=status.HTTP_200_OK,
    summary="Search Products",
    description="Search products by name or slug. Authenticated admins only.",
)
async def search_products(
    db: Annotated[Session, Depends(get_db)],
    current_admin: Annotated[AdminUser, Depends(get_current_admin)],
    q: str | None = Query(None, description="Search query"),
) -> SuccessResponse:
    if q and q.strip():
        products = ProductService.search_products(db, q.strip())
    else:
        products = ProductService.list_products(db, active_only=False)
    return success_response(
        "Products searched successfully.",
        data={
            "products": [_serialize_product(product) for product in products],
            "count": len(products),
        },
    )


@router.get(
    "/{product_id}",
    response_model=SuccessResponse,
    status_code=status.HTTP_200_OK,
    summary="Get Product",
    description="Retrieve a specific product by ID. Authenticated admins only.",
)
async def get_product(
    product_id: int,
    db: Annotated[Session, Depends(get_db)],
    current_admin: Annotated[AdminUser, Depends(get_current_admin)],
) -> SuccessResponse:
    product = ProductService.get_product(db, product_id)
    return success_response(
        "Product retrieved successfully.",
        data={"product": _serialize_product(product)},
    )


@router.post(
    "",
    response_model=SuccessResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create Product",
    description="Create a new product. Admin or Owner only.",
)
async def create_product(
    product_data: ProductCreate,
    db: Annotated[Session, Depends(get_db)],
    current_admin: Annotated[AdminUser, Depends(require_admin_or_owner)],
) -> SuccessResponse:
    product = ProductService.create_product(
        db,
        name=product_data.name,
        slug=product_data.slug,
        description=product_data.description,
        version=product_data.version,
    )
    return success_response(
        "Product created successfully.",
        data={"product": _serialize_product(product)},
    )


@router.put(
    "/{product_id}",
    response_model=SuccessResponse,
    status_code=status.HTTP_200_OK,
    summary="Update Product",
    description="Update an existing product. Admin or Owner only.",
)
async def update_product(
    product_id: int,
    product_data: ProductUpdate,
    db: Annotated[Session, Depends(get_db)],
    current_admin: Annotated[AdminUser, Depends(require_admin_or_owner)],
) -> SuccessResponse:
    product = ProductService.update_product(
        db,
        product_id,
        name=product_data.name,
        description=product_data.description,
        version=product_data.version,
        status=product_data.status,
    )
    return success_response(
        "Product updated successfully.",
        data={"product": _serialize_product(product)},
    )


@router.patch(
    "/{product_id}/status",
    response_model=SuccessResponse,
    status_code=status.HTTP_200_OK,
    summary="Update Product Status",
    description="Update a product status. Admin or Owner only.",
)
async def patch_product_status(
    product_id: int,
    status_update: ProductStatusUpdate,
    db: Annotated[Session, Depends(get_db)],
    current_admin: Annotated[AdminUser, Depends(require_admin_or_owner)],
) -> SuccessResponse:
    product = ProductService.set_product_status(db, product_id, status_update.status)
    return success_response(
        "Product status updated successfully.",
        data={"product": _serialize_product(product)},
    )


@router.delete(
    "/{product_id}",
    response_model=SuccessResponse,
    status_code=status.HTTP_200_OK,
    summary="Delete Product",
    description="Delete a product (archive). Owner only.",
)
async def delete_product(
    product_id: int,
    db: Annotated[Session, Depends(get_db)],
    current_admin: Annotated[AdminUser, Depends(require_owner)],
) -> SuccessResponse:
    ProductService.delete_product(db, product_id)
    return success_response(
        "Product archived successfully.",
        data={"product_id": product_id},
    )


@router.post(
    "/{product_id}/generate-api-key",
    response_model=SuccessResponse,
    status_code=status.HTTP_200_OK,
    summary="Generate API Key",
    description="Generate an API key for a product. Owner only.",
)
async def generate_api_key(
    product_id: int,
    db: Annotated[Session, Depends(get_db)],
    current_admin: Annotated[AdminUser, Depends(require_owner)],
) -> SuccessResponse:
    api_key = ProductService.regenerate_api_key(db, product_id)
    return success_response(
        "API key generated successfully.",
        data={"api_key": api_key},
    )


@router.post(
    "/{product_id}/regenerate-api-key",
    response_model=SuccessResponse,
    status_code=status.HTTP_200_OK,
    summary="Regenerate API Key",
    description="Regenerate the API key for a product. Owner only.",
)
async def regenerate_api_key(
    product_id: int,
    db: Annotated[Session, Depends(get_db)],
    current_admin: Annotated[AdminUser, Depends(require_owner)],
) -> SuccessResponse:
    api_key = ProductService.regenerate_api_key(db, product_id)
    return success_response(
        "API key regenerated successfully.",
        data={"api_key": api_key},
    )
