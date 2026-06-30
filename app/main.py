from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.database import Base, engine

# Create database tables
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="LOUD License Server",
    version="2.0.0"
)

# Static Files
app.mount(
    "/static",
    StaticFiles(directory="app/static"),
    name="static"
)

# Templates
templates = Jinja2Templates(
    directory="app/templates"
)


@app.get("/")
def home():
    return {
        "status": "running",
        "version": "2.0.0",
        "message": "LOUD License Server API"
    }