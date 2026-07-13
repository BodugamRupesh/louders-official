"""
Activity logging service for tracking license operations.
"""

from app.utils.datetime_utils import get_current_time
from typing import Optional

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.exceptions import DatabaseError
from app.models import ActivityLog


class ActivityLogService:
    """Service for logging license activities."""
    
    # Activity action constants
    ACTION_LICENSE_ACTIVATED = "license_activated"
    ACTION_LICENSE_VERIFIED = "license_verified"
    ACTION_LICENSE_EXTENDED = "license_extended"
    ACTION_DEVICE_REGISTERED = "device_registered"
    ACTION_DEVICE_HEARTBEAT = "device_heartbeat"
    ACTION_DEVICE_RESET = "device_reset"
    ACTION_LICENSE_REVOKED = "license_revoked"
    ACTION_LICENSE_SUSPENDED = "license_suspended"
    
    @staticmethod
    def log_activity(
        db: Session,
        license_id: int,
        action: str,
        ip_address: Optional[str] = None,
        browser: Optional[str] = None,
        additional_data: Optional[dict] = None,
    ) -> ActivityLog:
        """
        Log an activity for a license.
        
        Args:
            db: Database session
            license_id: License ID
            action: Action type (use ACTION_* constants)
            ip_address: Client IP address
            browser: Browser type
            additional_data: Additional context (stored as notes)
        
        Returns:
            Created ActivityLog object
        """
        
        notes = ""
        if additional_data:
            notes = str(additional_data)
        
        activity = ActivityLog(
            license_id=license_id,
            action=action,
            ip_address=ip_address,
            browser=browser,
            timestamp=get_current_time(),
            notes=notes,
        )
        
        try:
            db.add(activity)
            db.commit()
            db.refresh(activity)
            return activity
        except SQLAlchemyError as exc:
            db.rollback()
            raise DatabaseError(f"Failed to log activity: {exc}") from exc
    
    @staticmethod
    def get_license_activity_history(
        db: Session,
        license_id: int,
        limit: int = 100,
        offset: int = 0,
    ) -> tuple[list[ActivityLog], int]:
        """
        Get activity history for a license.
        
        Args:
            db: Database session
            license_id: License ID
            limit: Maximum number of records to return
            offset: Number of records to skip
        
        Returns:
            Tuple of (activity_logs, total_count)
        """
        
        query = db.query(ActivityLog).filter(ActivityLog.license_id == license_id)
        total_count = query.count()
        
        activities = query.order_by(ActivityLog.timestamp.desc()).offset(offset).limit(limit).all()
        
        return activities, total_count
    
    @staticmethod
    def get_product_activity_stats(
        db: Session,
        product_id: int,
        days: int = 30,
    ) -> dict:
        """
        Get activity statistics for a product.
        
        Args:
            db: Database session
            product_id: Product ID
            days: Number of days to look back
        
        Returns:
            Dictionary with activity statistics
        """
        from app.models import License
        from datetime import timedelta
        
        cutoff_date = get_current_time() - timedelta(days=days)
        
        # Get activity logs for this product's licenses
        activities = (
            db.query(ActivityLog)
            .join(License, ActivityLog.license_id == License.id)
            .filter(
                License.product_id == product_id,
                ActivityLog.timestamp >= cutoff_date,
            )
            .all()
        )
        
        # Count by action
        stats = {
            "total_activities": len(activities),
            "by_action": {},
            "by_day": {},
        }
        
        for activity in activities:
            # Count by action
            action = activity.action
            stats["by_action"][action] = stats["by_action"].get(action, 0) + 1
            
            # Count by day
            day = activity.timestamp.date().isoformat()
            stats["by_day"][day] = stats["by_day"].get(day, 0) + 1
        
        return stats
