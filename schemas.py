from pydantic import BaseModel


class ActivateRequest(BaseModel):
    license_key: str
    device_id: str


class VerifyRequest(BaseModel):
    license_key: str
    device_id: str


class CreateLicenseRequest(BaseModel):
    customer_name: str
    discord_username: str
    email: str
    plan: str
    days: int
    notes: str = ""


class ExtendLicenseRequest(BaseModel):
    license_key: str
    days: int


class RevokeLicenseRequest(BaseModel):
    license_key: str