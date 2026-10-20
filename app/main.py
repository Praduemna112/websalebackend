from fastapi import FastAPI

from app.routers.products import router as products_router
from app.users.router import router as users_router


app = FastAPI(title="Demo API", version="1.0.0")
app.include_router(products_router, prefix="/api/v1")
app.include_router(users_router, prefix="/api/v1")


@app.get("/health", tags=["health"])
def health_check() -> dict[str, str]:
    return {"status": "ok"}
