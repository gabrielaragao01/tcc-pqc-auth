from fastapi import FastAPI  # pyright: ignore[reportMissingImports]

from src.api.routes import router

app = FastAPI(
    title="PQC Web Auth — TCC",
    description=(
        "Post-Quantum Cryptography authentication benchmarking. "
        "Compares classical (RSA/ECDSA), pure PQC (Kyber + Dilithium), "
        "and hybrid authentication modes."
    ),
    version="0.1.0",
)

app.include_router(router)


@app.get("/")
def read_root() -> dict[str, str]:
    return {"message": "PQC Auth API — Phase 1 active. Visit /docs for the API reference."}
