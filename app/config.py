import os
from dotenv import load_dotenv

load_dotenv()


class Settings:
    def __init__(self):
        self.APP_NAME = "LOUD License Server"
        self.VERSION = "2.0.0"

        self.DATABASE_URL = os.getenv(
            "DATABASE_URL",
            "sqlite:///./licenses.db"
        )

        self.SECRET_KEY = os.getenv(
            "SECRET_KEY",
            "CHANGE_THIS_TO_A_RANDOM_SECRET_KEY"
        )

        self.ADMIN_USERNAME = os.getenv(
            "ADMIN_USERNAME",
            "admin"
        )

        self.ADMIN_PASSWORD = os.getenv(
            "ADMIN_PASSWORD",
            "admin123"
        )


settings = Settings()