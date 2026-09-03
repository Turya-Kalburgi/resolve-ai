from fastapi import FastAPI
from contextlib import asynccontextmanager
from app.database import engine, Base, SessionLocal
from app.routers import payments, risk, recovery, policy, workflow, metrics
from app.seed import seed_synthetic_payments

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize database tables
    Base.metadata.create_all(bind=engine)
    # Seed initial synthetic payment records
    db = SessionLocal()
    try:
        seed_synthetic_payments(db, count=25)
    finally:
        db.close()
    yield

app = FastAPI(
    title="Resolve AI - Payment Backend Service",
    version="1.0.0",
    description="Backend Payment API service supporting payment retrieval, risk detection, and diagnosis.",
    lifespan=lifespan
)

import os
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

app.include_router(payments.router)
app.include_router(risk.router)
app.include_router(recovery.router)
app.include_router(policy.router)
app.include_router(workflow.router)
app.include_router(metrics.router)

# Mount static web directory for Judge-Facing Dashboard
static_dir = os.path.join(os.path.dirname(__file__), "static")
if os.path.exists(static_dir):
    app.mount("/static", StaticFiles(directory=static_dir), name="static")

@app.get("/")
def read_root():
    """
    Serves the Judge-Facing ResolveAI Dashboard index.html.
    """
    index_file = os.path.join(static_dir, "index.html")
    if os.path.exists(index_file):
        return FileResponse(index_file)
    return {
        "service": "Resolve AI - Payment Backend Service",
        "status": "online",
        "docs": "/docs"
    }
