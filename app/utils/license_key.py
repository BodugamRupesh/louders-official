"""
License key generation utilities.
"""

import secrets
import string


def generate_license_key(prefix: str = "LP") -> str:
    """
    Generate a cryptographically secure license key.
    
    Format: PREFIX-XXXX-XXXX-XXXX
    Example: LP-K8Q2-M9X7-R4N1
    
    Args:
        prefix: License key prefix (default: "LP")
    
    Returns:
        Formatted license key string
    """
    chars = string.ascii_uppercase + string.digits
    
    # Generate 3 segments of 4 characters each
    segments = [
        ''.join(secrets.choice(chars) for _ in range(4))
        for _ in range(3)
    ]
    
    return f"{prefix}-{'-'.join(segments)}"
