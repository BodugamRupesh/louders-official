"""
Plan Service for LOUD Platform Licensing System.

Handles plan lifecycle operations including create, retrieve, update,
status management, deletion, search, and validation.
"""

from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from app.constants import (
    LICENSE_STATUS_ACTIVE,
    PLAN_STATUS_ACTIVE,
    PLAN_STATUS_RETIRED,
    PLAN_STATUSES,
)
from app.exceptions import (
    DatabaseError,
    InvalidDataError,
    PlanInUseException,
    PlanNotFoundError,
)
from app.models import License, Plan


class PlanService:
    """Service for handling subscription plan operations."""

    @staticmethod
    def _validate_name(name: str) -> str:
        if not name or not name.strip():
            raise InvalidDataError("Plan name cannot be empty")
        return name.strip().title()

    @staticmethod
    def _validate_fields(
        duration_days: int | None = None,
        max_devices: int | None = None,
        price: float | None = None
    ) -> None:
        if duration_days is not None and duration_days < 1:
            raise InvalidDataError("Plan duration_days must be at least 1")

        if max_devices is not None and max_devices < 1:
            raise InvalidDataError("Plan max_devices must be at least 1")

        if price is not None and price < 0:
            raise InvalidDataError("Plan price must be greater than or equal to 0")

    @staticmethod
    def _validate_status(status: str) -> str:
        if status not in PLAN_STATUSES:
            raise InvalidDataError(
                f"Plan status must be one of: {', '.join(PLAN_STATUSES)}"
            )
        return status

    @staticmethod
    def get_plan_by_name(db: Session, name: str) -> Plan | None:
        if not name or not name.strip():
            return None
        return db.query(Plan).filter(Plan.name == name.strip()).first()

    @staticmethod
    def create_plan(
        db: Session,
        name: str,
        duration_days: int,
        max_devices: int,
        price: float,
        status: str = PLAN_STATUS_ACTIVE
    ) -> Plan:
        """
        Create a new subscription plan.

        Args:
            db: SQLAlchemy database session.
            name: Name of the plan.
            duration_days: Duration of the plan in days.
            max_devices: Maximum devices allowed for the plan.
            price: Plan price.
            status: Plan status.

        Returns:
            Created Plan model instance.

        Raises:
            InvalidDataError: If input data is invalid.
            DatabaseError: If database operation fails.
        """
        name = PlanService._validate_name(name)
        PlanService._validate_fields(
            duration_days=duration_days,
            max_devices=max_devices,
            price=price,
        )
        status = PlanService._validate_status(status)

        try:
            existing = PlanService.get_plan_by_name(db, name)
            if existing is not None:
                raise InvalidDataError(f"Plan with name '{name}' already exists")

            plan = Plan(
                name=name,
                duration_days=duration_days,
                max_devices=max_devices,
                price=price,
                status=status
            )

            db.add(plan)
            db.commit()
            db.refresh(plan)

            return plan

        except (InvalidDataError, PlanNotFoundError):
            raise
        except IntegrityError:
            db.rollback()
            raise InvalidDataError(f"Plan with name '{name}' already exists")
        except SQLAlchemyError as exc:
            db.rollback()
            raise DatabaseError(
                f"Failed to create plan: {exc}"
            ) from exc

    @staticmethod
    def get_plan(db: Session, plan_id: int) -> Plan:
        """
        Retrieve a plan by ID.

        Args:
            db: SQLAlchemy database session.
            plan_id: Plan ID.

        Returns:
            Plan model instance.

        Raises:
            PlanNotFoundError: If plan does not exist.
        """
        plan = db.query(Plan).filter(Plan.id == plan_id).first()

        if plan is None:
            raise PlanNotFoundError(f"Plan with ID {plan_id} not found")

        return plan

    @staticmethod
    def list_plans(
        db: Session,
        page: int = 1,
        page_size: int = 20,
        active_only: bool = False
    ) -> list[Plan]:
        """
        List plans with optional pagination and active-only filtering.

        Args:
            db: SQLAlchemy database session.
            page: Page number (1-indexed).
            page_size: Number of items per page.
            active_only: If true, only return active plans.

        Returns:
            List of Plan model instances.
        """
        if page < 1 or page_size < 1:
            raise InvalidDataError("Page and page_size must be positive integers")

        query = db.query(Plan)
        if active_only:
            query = query.filter(Plan.status == PLAN_STATUS_ACTIVE)

        return (
            query.order_by(Plan.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
            .all()
        )

    @staticmethod
    def search_plans(db: Session, query_text: str) -> list[Plan]:
        """
        Search plans by name.

        Args:
            db: SQLAlchemy database session.
            query_text: Search text.

        Returns:
            List of matching Plan model instances.
        """
        if not query_text or not query_text.strip():
            return []
        return (
            db.query(Plan)
            .filter(
                Plan.name.ilike(f"%{query_text.strip()}%")
            )
            .order_by(Plan.created_at.desc())
            .all()
        )
    @staticmethod
    def update_plan(
        db: Session,
        plan_id: int,
        name: str | None = None,
        duration_days: int | None = None,
        max_devices: int | None = None,
        price: float | None = None,
        status: str | None = None
    ) -> Plan:
        """
        Update an existing plan.

        Args:
            db: SQLAlchemy database session.
            plan_id: Plan ID.
            name: Optional new name.
            duration_days: Optional new duration days.
            max_devices: Optional new max devices.
            price: Optional new price.
            status: Optional new status.

        Returns:
            Updated Plan model instance.

        Raises:
            PlanNotFoundError: If plan does not exist.
            InvalidDataError: If provided values are invalid.
            DatabaseError: If database operation fails.
        """
        plan = PlanService.get_plan(db, plan_id)

        if name is not None:
            name = PlanService._validate_name(name)
            existing = PlanService.get_plan_by_name(db, name)
            if existing and existing.id != plan_id:
                raise InvalidDataError(f"Plan with name '{name}' already exists")
            plan.name = name

        PlanService._validate_fields(
            duration_days=duration_days,
            max_devices=max_devices,
            price=price,
        )

        if duration_days is not None:
            plan.duration_days = duration_days

        if max_devices is not None:
            plan.max_devices = max_devices

        if price is not None:
            plan.price = price

        if status is not None:
            plan.status = PlanService._validate_status(status)

        try:
            db.commit()
            db.refresh(plan)
            return plan

        except IntegrityError:
            db.rollback()
            raise InvalidDataError(f"Plan with name '{name}' already exists")
        except SQLAlchemyError as exc:
            db.rollback()
            raise DatabaseError(f"Failed to update plan: {str(exc)}")

    @staticmethod
    def set_plan_status(db: Session, plan_id: int, status: str) -> Plan:
        """
        Update only the status of a plan.

        Args:
            db: SQLAlchemy database session.
            plan_id: Plan ID.
            status: New status value.

        Returns:
            Updated Plan model instance.

        Raises:
            PlanNotFoundError: If plan does not exist.
            InvalidDataError: If status is invalid.
            DatabaseError: If database operation fails.
        """
        status = PlanService._validate_status(status)

        plan = PlanService.get_plan(db, plan_id)
        plan.status = status

        try:
            db.commit()
            db.refresh(plan)
            return plan

        except SQLAlchemyError as exc:
            db.rollback()
            raise DatabaseError(f"Failed to update plan status: {str(exc)}")

    @staticmethod
    def delete_plan(db: Session, plan_id: int) -> Plan:
        """
        Retire an existing plan by setting its status to retired.

        Args:
            db: SQLAlchemy database session.
            plan_id: Plan ID.

        Returns:
            Updated Plan model instance.

        Raises:
            PlanNotFoundError: If plan does not exist.
            PlanInUseException: If referenced by active licenses.
            DatabaseError: If database operation fails.
        """
        plan = PlanService.get_plan(db, plan_id)

        if db.query(License).filter(
            License.plan_id == plan_id,
            License.status == LICENSE_STATUS_ACTIVE
        ).first():
            raise PlanInUseException(
                f"Plan with ID {plan_id} cannot be retired because it is referenced by active licenses"
            )

        if plan.status == PLAN_STATUS_RETIRED:
            return plan

        plan.status = PLAN_STATUS_RETIRED

        try:
            db.commit()
            db.refresh(plan)
            return plan

        except SQLAlchemyError as exc:
            db.rollback()
            raise DatabaseError(f"Failed to retire plan: {str(exc)}") from exc

    @staticmethod
    def validate_plan(db: Session, plan_id: int) -> Plan:
        """
        Validate that a plan exists and is active.

        Args:
            db: SQLAlchemy database session.
            plan_id: Plan ID.

        Returns:
            Active Plan model instance.

        Raises:
            PlanNotFoundError: If plan does not exist.
            InvalidDataError: If plan is not active.
        """
        plan = PlanService.get_plan(db, plan_id)

        if plan.status != PLAN_STATUS_ACTIVE:
            raise InvalidDataError(f"Plan is not active (status: {plan.status})")

        return plan
