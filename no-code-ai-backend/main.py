# This is the main entry point of your FastAPI app

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.responses import RedirectResponse

# Import your route modules (organized by feature)
from backend.mixes import create_mix
from backend.mixes import upload_content
from backend.mixes import map_fields
from backend.mixes import preview_content
from backend.mixes import generate_recommendations
from backend.mixes import list_mixes
from backend.mixes import business_rules
from backend.mixes import simulate_watch_data
from backend.mixes import get_mix
from backend.routes import users
from backend.routes import user_activity

# Import database setup
from backend.database import Base, engine
from backend.routes import user_activity



# Create the FastAPI app
app = FastAPI()

# Add CORS middleware to allow requests from your frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allows all origins. For production, specify your frontend URL
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


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
app.include_router(get_mix.router, prefix="/mixes")
app.include_router(business_rules.router, prefix="/mixes")
app.include_router(simulate_watch_data.router, prefix="/mixes")


# Register the /users routes with the FastAPI app
app.include_router(users.router)
app.include_router(user_activity.router)

# Create all database tables if they don't exist yet
Base.metadata.create_all(bind=engine)

for route in app.routes:
    print(route.path)

