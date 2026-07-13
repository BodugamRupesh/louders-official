"""
Plans Router for LOUD Platform Licensing System.

Endpoints:
- GET /api/v1/plans - List plans
- GET /api/v1/plans/{plan_id} - Get plan by ID
- POST /api/v1/plans - Create plan
- PUT /api/v1/plans/{plan_id} - Update plan
- PATCH /api/v1/plans/{plan_id}/status - Update plan status
- DELETE /api/v1/plans/{plan_id} - Delete plan
"""

from typing import Annotated

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session
from app.constants import PLAN_STATUS_RETIRED
from app.database import get_db
from app.dependencies import get_current_admin, require_admin_or_owner, require_owner
from app.models import AdminUser
from app.schemas import PlanCreate, PlanResponse, PlanStatusUpdate, PlanUpdate, SuccessResponse
from app.services.plan_service import PlanService


router = APIRouter(
    prefix="/api/v1/plans",
    tags=["Plans"]
)


@router.post(
    "",
    response_model=SuccessResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create Plan",
    description="Create a new subscription plan. Admin or Owner only."
)
async def create_plan(
    plan_data: PlanCreate,
    db: Annotated[Session, Depends(get_db)],
    current_admin: Annotated[AdminUser, Depends(require_admin_or_owner)]
) -> SuccessResponse:
    """
    Create a new subscription plan.
    """
    plan = PlanService.create_plan(
        db,
        name=plan_data.name,
        duration_days=plan_data.duration_days,
        max_devices=plan_data.max_devices,
        price=plan_data.price,
        status=plan_data.status,
    )

    return SuccessResponse(
        success=True,
        message="Plan created successfully.",
        data={"plan": PlanResponse.model_validate(
                            plan,
                            from_attributes=True,
                        )     
                }
    )


@router.get(
    "",
    response_model=SuccessResponse,
    status_code=status.HTTP_200_OK,
    summary="List Plans",
    description="Retrieve all subscription plans."
)
async def list_plans(
    db: Annotated[Session, Depends(get_db)],
    current_admin: Annotated[AdminUser, Depends(get_current_admin)],
    active_only: bool = Query(False, description="Filter active plans only"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, description="Page size"),
) -> SuccessResponse:
    """
    Retrieve all subscription plans.
    """
    plans = PlanService.list_plans(
        db,
        page=page,
        page_size=page_size,
        active_only=active_only,
    )

    return SuccessResponse(
        success=True,
        message="Plans retrieved successfully.",
        data={
            "plans": [PlanResponse.model_validate(
                            plan,
                            from_attributes=True,
                        ) for plan in plans],
            "page": page,
            "page_size": page_size,
            "count": len(plans),
            "has_more": len(plans) == page_size,
        }
    )


@router.get(
    "/search/query",
    response_model=SuccessResponse,
    status_code=status.HTTP_200_OK,
    summary="Search Plans",
    description="Search plans by name."
)
async def search_plans(
    q: Annotated[str, Query(..., min_length=1, description="Search query")],
    db: Annotated[Session, Depends(get_db)],
    current_admin: Annotated[AdminUser, Depends(get_current_admin)]
) -> SuccessResponse:
    """
    Search plans by name.
    """
    plans = PlanService.search_plans(db, q)

    return SuccessResponse(
        success=True,
        message="Plans searched successfully.",
        data={"plans": [PlanResponse.model_validate(
                            plan,
                            from_attributes=True,
                        ) for plan in plans]}
    )


@router.get(
    "/{plan_id}",
    response_model=SuccessResponse,
    status_code=status.HTTP_200_OK,
    summary="Get Plan",
    description="Retrieve a specific subscription plan by ID."
)
async def get_plan(
    plan_id: int,
    db: Annotated[Session, Depends(get_db)],
    current_admin: Annotated[AdminUser, Depends(get_current_admin)]
) -> SuccessResponse:
    """
    Retrieve a specific subscription plan by ID.
    """
    plan = PlanService.get_plan(db, plan_id)

    return SuccessResponse(
        success=True,
        message="Plan retrieved successfully.",
        data={"plan": PlanResponse.model_validate(
                            plan,
                            from_attributes=True,
                    )
            }
    )


@router.put(
    "/{plan_id}",
    response_model=SuccessResponse,
    status_code=status.HTTP_200_OK,
    summary="Update Plan",
    description="Update a subscription plan. Admin or Owner only."
)
async def update_plan(
    plan_id: int,
    plan_data: PlanUpdate,
    db: Annotated[Session, Depends(get_db)],
    current_admin: Annotated[AdminUser, Depends(require_admin_or_owner)]
) -> SuccessResponse:
    """
    Update a subscription plan.
    """
    plan = PlanService.update_plan(
        db,
        plan_id,
        name=plan_data.name,
        duration_days=plan_data.duration_days,
        max_devices=plan_data.max_devices,
        price=plan_data.price,
        status=plan_data.status,
    )

    return SuccessResponse(
        success=True,
        message="Plan updated successfully.",
        data={"plan": PlanResponse.model_validate(
                            plan,
                            from_attributes=True,
                    )
        }
    )


@router.patch(
    "/{plan_id}/status",
    response_model=SuccessResponse,
    status_code=status.HTTP_200_OK,
    summary="Update Plan Status",
    description="Update only the status of a subscription plan. Admin or Owner only."
)
async def patch_plan_status(
    plan_id: int,
    status_update: PlanStatusUpdate,
    db: Annotated[Session, Depends(get_db)],
    current_admin: Annotated[AdminUser, Depends(require_admin_or_owner)]
) -> SuccessResponse:
    """
    Update only the status of a specific plan.
    """
    plan = PlanService.set_plan_status(db, plan_id, status_update.status)

    return SuccessResponse(
        success=True,
        message="Plan status updated successfully.",
        data={"plan": PlanResponse.model_validate(
                            plan,
                            from_attributes=True,
        )}
    )


@router.delete(
    "/{plan_id}",
    response_model=SuccessResponse,
    status_code=status.HTTP_200_OK,
    summary="Delete Plan",
    description="Delete a subscription plan. Owner only."
)
async def delete_plan(
    plan_id: int,
    db: Annotated[Session, Depends(get_db)],
    current_admin: Annotated[AdminUser, Depends(require_owner)]
) -> SuccessResponse:
    """
    Delete a subscription plan.
    """
    plan = PlanService.delete_plan(db, plan_id)

    return SuccessResponse(
        success=True,
        message="Plan retired successfully.",
        data={
            "plan": PlanResponse.model_validate(
                plan,
                from_attributes=True,
            )
        },
    )


