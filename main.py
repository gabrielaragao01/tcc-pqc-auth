from __future__ import annotations

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI  # pyright: ignore[reportMissingImports]

from src.api.routes import router as pqc_router
from src.api.auth_routes import router as auth_router
from src.api.pqc_auth_routes import router as pqc_auth_router
from src.api.hybrid_auth_routes import router as hybrid_auth_router
from src.db.database import init_db


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan: initialize SQLite database on startup."""
    init_db()
    yield


app = FastAPI(
    title="PQC Web Auth — TCC",
    description=(
        "Post-Quantum Cryptography authentication benchmarking. "
        "Compares classical (RSA/ECDSA), pure PQC (Kyber + Dilithium), "
        "and hybrid authentication modes."
    ),
    version="0.5.0",
    lifespan=lifespan,
)

app.include_router(pqc_router)
app.include_router(auth_router)
app.include_router(pqc_auth_router)
app.include_router(hybrid_auth_router)


@app.get("/")
def read_root() -> dict[str, str]:
    return {"message": "PQC Auth API — Phase 5 active. Visit /docs for the API reference."}
