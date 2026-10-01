"""
Customer Service for LOUD Platform Licensing System.

Handles:
- Customer creation, update, deletion
- Customer retrieval and search
- Customer data management
- License retrieval for customers
"""

import logging
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from app.exceptions import (
    CustomerNotFoundError,
    DatabaseError,
    DuplicateCustomerError,
    InvalidDataError,
)
from app.models import Customer, License, Device, ActivityLog
from app.utils.datetime_utils import get_current_time

logger = logging.getLogger(__name__)


class CustomerService:
    """Service for handling customer operations."""


    @staticmethod
    def _validate_name(name: str) -> str:
        """Validate and normalize customer name."""
        if not name or not name.strip():
            raise InvalidDataError("Customer name cannot be empty.")
        return name.strip()

    @staticmethod
    def _clean_optional(value: str | None) -> str | None:
        """Normalize optional string fields."""
        if value is None:
            return None

        value = value.strip().lower()
        return value or None

    @staticmethod
    def create_customer(
        db: Session,
        name: str,
        email: str | None = None,
        phone: str | None = None,
        notes: str | None = None,
    ) -> Customer:
        """
        Create a new customer.
        """

        name = CustomerService._validate_name(name)
        email = CustomerService._clean_optional(email)
        phone = CustomerService._clean_optional(phone)
        notes = CustomerService._clean_optional(notes)

        if email is None:
            raise InvalidDataError("Customer email cannot be empty.")

        try:
            email = email.strip().lower()
            existing_email = (
                db.query(Customer)
                .filter(Customer.email == email)
                .first()
            )

            if existing_email is not None:
                raise DuplicateCustomerError(
                    f"Customer with email '{email}' already exists."
                )

            customer = Customer(
                name=name,
                email=email,
                phone=phone,
                notes=notes,
            )

            db.add(customer)
            db.commit()
            db.refresh(customer)

            return customer

        except (DuplicateCustomerError, InvalidDataError):
            raise

        except IntegrityError:
            db.rollback()
            raise DuplicateCustomerError(
                "Customer with this email already exists."
            )

        except SQLAlchemyError as exc:
            db.rollback()
            raise DatabaseError(
                f"Failed to create customer: {exc}"
            ) from exc

    @staticmethod
    def get_customer(
        db: Session,
        customer_id: int,
    ) -> Customer:
        """Get customer by ID."""

        customer = (
            db.query(Customer)
            .filter(Customer.id == customer_id)
            .first()
        )

        if customer is None:
            raise CustomerNotFoundError(
                f"Customer with ID {customer_id} not found."
            )

        return customer

    @staticmethod
    def get_customer_by_email(
        db: Session,
        email: str,
    ) -> Customer:
        """Get customer by email."""

        email = CustomerService._clean_optional(email)

        customer = (
            db.query(Customer)
            .filter(Customer.email == email)
            .first()
        )

        if customer is None:
            raise CustomerNotFoundError(
                f"Customer with email '{email}' not found."
            )

        return customer

    @staticmethod
    def update_customer(
        db: Session,
        customer_id: int,
        name: str | None = None,
        email: str | None = None,
        phone: str | None = None,
        notes: str | None = None,
    ) -> Customer:
        """
        Update an existing customer.
        """

        try:
            customer = CustomerService.get_customer(
                db,
                customer_id,
            )

            if name is not None:
                customer.name = CustomerService._validate_name(name)

            if email is not None:
                email = CustomerService._clean_optional(email)

                if email is None:
                    raise InvalidDataError("Customer email cannot be empty.")

                existing = (
                    db.query(Customer)
                    .filter(
                        Customer.email == email,
                        Customer.id != customer_id,
                    )
                    .first()
                )

                if existing is not None:
                    raise DuplicateCustomerError(
                        f"Email '{email}' is already taken."
                    )

                customer.email = email

            if phone is not None:
                customer.phone = CustomerService._clean_optional(phone)

            if notes is not None:
                customer.notes = CustomerService._clean_optional(notes)

            db.commit()
            db.refresh(customer)

            return customer

        except (
            CustomerNotFoundError,
            DuplicateCustomerError,
            InvalidDataError,
        ):
            raise

        except SQLAlchemyError as exc:
            db.rollback()
            raise DatabaseError(
                f"Failed to update customer: {exc}"
            ) from exc
        
    @staticmethod
    def delete_customer(
        db: Session,
        customer_id: int,
        admin_username: str | None = None,
        admin_id: int | None = None,
    ) -> bool:
        """
        Delete a customer and safely clean up their associated records.

        Args:
            db: SQLAlchemy database session.
            customer_id: Customer ID.
            admin_username: Optional username of admin executing deletion.
            admin_id: Optional ID of admin executing deletion.

        Returns:
            True if deleted successfully.
        """
        try:
            customer = CustomerService.get_customer(
                db,
                customer_id,
            )

            customer_email = customer.email
            customer_name = customer.name

            # Explicitly clean up all associated licenses, devices, and activity logs
            licenses = db.query(License).filter(License.customer_id == customer.id).all()
            for lic in licenses:
                db.query(Device).filter(Device.license_id == lic.id).delete()
                db.query(ActivityLog).filter(ActivityLog.license_id == lic.id).delete()
                db.delete(lic)

            db.delete(customer)
            db.commit()

            logger.info(
                "Customer deleted successfully: customer_id=%s | name='%s' | email='%s' | admin='%s' (id=%s) | timestamp=%s",
                customer_id,
                customer_name,
                customer_email,
                admin_username or "system",
                admin_id,
                get_current_time().isoformat(),
            )

            return True

        except CustomerNotFoundError:
            raise

        except SQLAlchemyError as exc:
            db.rollback()
            raise DatabaseError(
                f"Failed to delete customer: {exc}"
            ) from exc


    @staticmethod
    def list_customers(
        db: Session,
        search: str | None = None,
        email: str | None = None,
    ) -> list[Customer]:
        """
        List customers with optional filters.
        """

        search = CustomerService._clean_optional(search)
        email = CustomerService._clean_optional(email)

        query = db.query(Customer)

        if search:
            query = query.filter(
                (Customer.name.ilike(f"%{search}%"))
                | (Customer.email.ilike(f"%{search}%"))
            )

        elif email is not None:
            query = query.filter(
                Customer.email == email
            )

        return (
            query.order_by(
                Customer.created_at.desc()
            ).all()
        )

    @staticmethod
    def search_customers(
        db: Session,
        query_str: str,
    ) -> list[Customer]:
        """
        Search customers.
        """

        query_str = CustomerService._clean_optional(query_str)

        if not query_str:
            return []

        return (
            db.query(Customer)
            .filter(
                (Customer.name.ilike(f"%{query_str}%"))
                | (Customer.email.ilike(f"%{query_str}%"))
            )
            .order_by(Customer.created_at.desc())
            .all()
        )

    @staticmethod
    def get_customer_licenses(
        db: Session,
        customer_id: int,
    ) -> list[License]:
        """
        Get all licenses belonging to a customer.
        """

        customer = CustomerService.get_customer(db, customer_id)
        return list(customer.licenses)

    @staticmethod
    def get_license_count(
        db: Session,
        customer_id: int,
    ) -> int:
        """
        Get total licenses for a customer.
        """

        customer = CustomerService.get_customer(
            db,
            customer_id,
        )

        return len(customer.licenses)