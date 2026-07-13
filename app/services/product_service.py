"""
Product Service for LOUD Platform Licensing System.

Handles:
- Product creation, update, deletion
- Product retrieval and search
- API key generation and management
- Product status management
"""

from itertools import product

from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from app.constants import (
    PRODUCT_STATUS_ACTIVE,
    PRODUCT_STATUS_ARCHIVED,
    PRODUCT_STATUSES,
)
from app.exceptions import (
    DatabaseError,
    DuplicateProductError,
    InvalidDataError,
    InvalidProductKeyError,
    ProductNotFoundError,
)
from app.models import License, Product, generate_product_api_key

class ProductService:
    """Service for handling product operations."""

    @staticmethod
    def generate_api_key() -> str:
        """
        Generate a unique product API key.
        
        Format: lp_prod_xxxxxxxxxxxxxxxx
        
        Returns:
            Generated API key string.
        """
        return generate_product_api_key()

    @staticmethod
    def _validate_name(name: str) -> str:
        if not name or not name.strip():
            raise InvalidDataError("Product name cannot be empty")
        return name.strip()

    @staticmethod
    def _validate_slug(slug: str) -> str:
        if not slug or not slug.strip():
            raise InvalidDataError("Product slug cannot be empty")
        return slug.strip().lower()

    @staticmethod
    def _validate_status(status: str) -> str:
        if status not in PRODUCT_STATUSES:
            raise InvalidDataError(
                f"Product status must be one of: {', '.join(PRODUCT_STATUSES)}"
            )
        return status

    @staticmethod
    def _validate_version(version: str | None) -> str | None:
        if version is not None and not version.strip():
            raise InvalidDataError("Product version cannot be empty")
        return version.strip() if version is not None else None

    @staticmethod
    def create_product(
        db: Session,
        name: str,
        slug: str,
        description: str | None = None,
        version: str = "1.0.0",
    ) -> Product:
        """
        Create a new product.
        
        Args:
            db: SQLAlchemy database session.
            name: Product name.
            slug: URL-friendly slug (must be unique).
            description: Optional product description.
            version: Product version.
            
        Returns:
            Created Product model instance.
            
        Raises:
            DuplicateProductError: If slug already exists.
            InvalidDataError: If data is invalid.
            DatabaseError: If database operation fails.
        """
        name = ProductService._validate_name(name)
        slug = ProductService._validate_slug(slug)
        version = ProductService._validate_version(version) or "1.0.0"

        try:
            existing = db.query(Product).filter(
                Product.slug == slug
            ).first()

            if existing:
                raise DuplicateProductError(f"Product with slug '{slug}' already exists")

            api_key = ProductService.generate_api_key()

            product = Product(
                name=name,
                slug=slug,
                api_key=api_key,
                description=description,
                version=version,
                status=PRODUCT_STATUS_ACTIVE
            )
            
            print(f"[DEBUG] Product before commit: {product.__dict__}")
            print(f"[DEBUG]   created_at={product.created_at}, id={product.id}")
            
            db.add(product)
            db.commit()
            
            print(f"[DEBUG] Product after commit: {product.__dict__}")
            print(f"[DEBUG]   created_at={product.created_at}, id={product.id}")
            
            db.refresh(product)
            
            print(f"[DEBUG] Product after refresh: {product.__dict__}")
            print(f"[DEBUG]   created_at={product.created_at} (type: {type(product.created_at)})")
            
            if product.created_at is None:
                print(f"[ERROR] ⚠️  CRITICAL: created_at is STILL NULL after refresh!")
                print(f"[ERROR] This indicates DATABASE DEFAULT is missing.")
                print(f"[ERROR] Run Alembic migration: alembic upgrade head")
            else:
                print(f"[SUCCESS] ✓ created_at populated from database default: {product.created_at}")
            
            return product
            
        except IntegrityError as exc:
            db.rollback()
            raise DuplicateProductError("Product with this slug or API key already exists") from exc
        except SQLAlchemyError as exc:
            db.rollback()
            raise DatabaseError(
                f"Failed to create product: {exc}"
            ) from exc

    @staticmethod
    def get_product(db: Session, product_id: int) -> Product:
        """
        Get product by ID.
        
        Args:
            db: SQLAlchemy database session.
            product_id: Product ID.
            
        Returns:
            Product model instance.
            
        Raises:
            ProductNotFoundError: If product doesn't exist.
        """
        product = db.query(Product).filter(
            Product.id == product_id
        ).first()
        
        if product is None:
            raise ProductNotFoundError(f"Product with ID {product_id} not found")
        
        return product

    @staticmethod
    def get_product_by_slug(db: Session, slug: str) -> Product:
        """
        Get product by slug.
        
        Args:
            db: SQLAlchemy database session.
            slug: Product slug.
            
        Returns:
            Product model instance.
            
        Raises:
            ProductNotFoundError: If product doesn't exist.
        """
        product = db.query(Product).filter(
            Product.slug == slug
        ).first()
        
        if not product:
            raise ProductNotFoundError(f"Product with slug '{slug}' not found")
        
        return product

    @staticmethod
    def get_product_by_api_key(db: Session, api_key: str) -> Product:
        """
        Get product by API key.
        
        Args:
            db: SQLAlchemy database session.
            api_key: Product API key.
            
        Returns:
            Product model instance.
            
        Raises:
            ProductNotFoundError: If product doesn't exist.
        """
        product = db.query(Product).filter(
            Product.api_key == api_key
        ).first()
        
        if not product:
            raise ProductNotFoundError(f"Product with API key '{api_key}' not found")
        
        return product

    @staticmethod
    def update_product(
        db: Session,
        product_id: int,
        name: str | None = None,
        description: str | None = None,
        version: str | None = None,
        status: str | None = None
    ) -> Product:
        """
        Update a product.
        
        Args:
            db: SQLAlchemy database session.
            product_id: Product ID.
            name: New product name.
            description: New product description.
            version: New product version.
            status: New product status.
            
        Returns:
            Updated Product model instance.
            
        Raises:
            ProductNotFoundError: If product doesn't exist.
            DatabaseError: If database operation fails.
        """
        try:
            product = ProductService.get_product(db, product_id)
            
            if name is not None:
                product.name = ProductService._validate_name(name)

            if description is not None:
                product.description = description

            if version is not None:
                product.version = ProductService._validate_version(version)

            if status is not None:
                product.status = ProductService._validate_status(status)

            db.commit()
            db.refresh(product)

            return product
            
        except ProductNotFoundError:
            raise
        except SQLAlchemyError as exc:
            db.rollback()
            raise DatabaseError(
                f"Failed to update product: {exc}"
            ) from exc

    @staticmethod
    def delete_product(db: Session, product_id: int) -> bool:
        """
        Delete a product (soft delete via status).
        
        Args:
            db: SQLAlchemy database session.
            product_id: Product ID.
            
        Returns:
            True if product deleted successfully.
            
        Raises:
            ProductNotFoundError: If product doesn't exist.
            DatabaseError: If database operation fails.
        """
        try:
            product = ProductService.get_product(db, product_id)
            
            product.status = PRODUCT_STATUS_ARCHIVED

            db.commit()
            db.refresh(product)

            return True
            
        except ProductNotFoundError:
            raise
        except SQLAlchemyError as exc:
            db.rollback()
            raise DatabaseError(
                f"Failed to delete product: {exc}"
            ) from exc

    @staticmethod
    def list_products(db: Session, active_only: bool = True) -> list[Product]:
        """
        List all products.
        
        Args:
            db: SQLAlchemy database session.
            active_only: If True, only return active products.
            
        Returns:
            List of Product model instances.
        """
        query = db.query(Product)

        if active_only:
            query = query.filter(Product.status == PRODUCT_STATUS_ACTIVE)

        return query.order_by(Product.created_at.desc()).all()

    @staticmethod
    def search_products(db: Session, query_str: str) -> list[Product]:
        """
        Search products by name or slug.
        
        Args:
            db: SQLAlchemy database session.
            query_str: Search query string.
            
        Returns:
            List of matching Product model instances.
        """
        return db.query(Product).filter(
            (Product.name.ilike(f"%{query_str}%")) |
            (Product.slug.ilike(f"%{query_str}%"))
        ).order_by(Product.created_at.desc()).all()

    @staticmethod
    def set_product_status(db: Session, product_id: int, status: str) -> Product:
        """
        Update only the status of a product.

        Args:
            db: SQLAlchemy database session.
            product_id: Product ID.
            status: New product status.

        Returns:
            Updated Product model instance.

        Raises:
            ProductNotFoundError: If product doesn't exist.
            InvalidDataError: If status is invalid.
            DatabaseError: If database operation fails.
        """
        status = ProductService._validate_status(status)

        product = ProductService.get_product(db, product_id)
        product.status = status

        try:
            db.commit()
            db.refresh(product)
            return product

        except SQLAlchemyError as exc:
            db.rollback()
            raise DatabaseError(
                f"Failed to update product status: {exc}"
            ) from exc

    @staticmethod
    def activate_product(db: Session, product_id: int) -> Product:
        """
        Activate a product.
        
        Args:
            db: SQLAlchemy database session.
            product_id: Product ID.
            
        Returns:
            Updated Product model instance.
            
        Raises:
            ProductNotFoundError: If product doesn't exist.
            DatabaseError: If database operation fails.
        """
        return ProductService.update_product(db, product_id, status=PRODUCT_STATUS_ACTIVE)

    @staticmethod
    def deactivate_product(db: Session, product_id: int) -> Product:
        """
        Deactivate a product.
        
        Args:
            db: SQLAlchemy database session.
            product_id: Product ID.
            
        Returns:
            Updated Product model instance.
            
        Raises:
            ProductNotFoundError: If product doesn't exist.
            DatabaseError: If database operation fails.
        """
        return ProductService.update_product(db, product_id, status=PRODUCT_STATUS_ARCHIVED)

    @staticmethod
    def regenerate_api_key(db: Session, product_id: int) -> str:
        """
        Regenerate API key for a product.
        
        Args:
            db: SQLAlchemy database session.
            product_id: Product ID.
            
        Returns:
            New API key string.
            
        Raises:
            ProductNotFoundError: If product doesn't exist.
            DatabaseError: If database operation fails.
        """
        try:
            product = ProductService.get_product(db, product_id)
            while True:
                api_key = ProductService.generate_api_key()

                exists = db.query(Product).filter(
                     Product.api_key == api_key
                ).first()

                if exists is None:
                    break

            product.api_key = api_key

            db.commit()
            db.refresh(product)
            
            print("=" * 60)
            print("Product ID:", product.id)
            print("Product created_at:", product.created_at)
            print("Product api_key:", product.api_key)
            print("Product __dict__:", product.__dict__)
            print("=" * 60)

            return product.api_key

        except ProductNotFoundError:
            raise
        except SQLAlchemyError as exc:
            db.rollback()
            raise DatabaseError(
                 f"Failed to regenerate API key: {exc}"
            ) from exc

    @staticmethod
    def validate_api_key(db: Session, api_key: str) -> Product:
        """
        Validate an API key and return the associated product.

        Args:
            db: SQLAlchemy database session.
            api_key: Product API key to validate.

        Returns:
            Product model instance.

        Raises:
            InvalidProductKeyError: If API key is invalid or missing.
            ProductNotFoundError: If no product matches the API key.
        """
        if not api_key or not api_key.strip():
            raise InvalidProductKeyError("Product API key is required")

        product = db.query(Product).filter(Product.api_key == api_key.strip()).first()

        if not product:
            raise InvalidProductKeyError(f"Product with API key '{api_key}' not found")

        if product.status != PRODUCT_STATUS_ACTIVE:
            raise InvalidProductKeyError(
                f"Product is not active (status: {product.status})"
            )

        return product

    @staticmethod
    def get_license_count(db: Session, product_id: int) -> int:
        """
        Get number of licenses for a product.
        
        Args:
            db: SQLAlchemy database session.
            product_id: Product ID.
            
        Returns:
            Number of licenses.
            
        Raises:
            ProductNotFoundError: If product doesn't exist.
        """
        ProductService.get_product(db, product_id)

        return (
            db.query(License)
            .filter(License.product_id == product_id)
            .count()
        )