from fastapi import Header, HTTPException

ADMIN_TOKEN = "CHANGE_THIS_TO_A_LONG_RANDOM_SECRET"

def verify_admin_token(x_admin_token: str = Header(None)):
    if x_admin_token != ADMIN_TOKEN:
        raise HTTPException(
            status_code=401,
            detail="Unauthorized"
        )