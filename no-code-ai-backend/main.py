# This is the main entry point of your FastAPI app

from fastapi import FastAPI
from starlette.responses import RedirectResponse

# Import your route modules (organized by feature)
from backend.mixes import create_mix
from backend.mixes import upload_content
from backend.mixes import map_fields
from backend.mixes import preview_content
from backend.mixes import generate_recommendations
from backend.mixes import list_mixes
from backend.routes import users
from backend.routes import user_activity

# Import database setup
from backend.database import Base, engine
from backend.routes import user_activity



# Create the FastAPI app
app = FastAPI()


# Lightweight root route: redirect to the OpenAPI docs so GET / doesn't 404
@app.get("/", include_in_schema=False)
def read_root():
    """Redirect root requests to the interactive docs."""
    return RedirectResponse(url="/docs")

# Register all routers so the endpoints are active
app.include_router(create_mix.router, prefix="/mixes")
app.include_router(upload_content.router, prefix="/mixes")
app.include_router(map_fields.router, prefix="/mixes")
app.include_router(preview_content.router, prefix="/mixes")
app.include_router(generate_recommendations.router, prefix="/mixes")
app.include_router(list_mixes.router, prefix="/mixes")


# Register the /users routes with the FastAPI app
app.include_router(users.router)
app.include_router(user_activity.router)

# Create all database tables if they don't exist yet
Base.metadata.create_all(bind=engine)

for route in app.routes:
    print(route.path)

