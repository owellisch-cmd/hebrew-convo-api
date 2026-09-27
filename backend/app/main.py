from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.database import Base, engine
from app.routers import auth, expenses, family, pathways, plans, practice, recommend

Base.metadata.create_all(bind=engine)

app = FastAPI(title="Health Insurance Advisor API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(family.router)
app.include_router(expenses.router)
app.include_router(plans.router)
app.include_router(pathways.router)
app.include_router(recommend.router)
app.include_router(practice.router)


@app.get("/health")
def health():
    return {"status": "ok"}
