"""API: FastAPI + Strawberry GraphQL en /graphql."""
from contextlib import asynccontextmanager

from fastapi import FastAPI
from strawberry.fastapi import GraphQLRouter

from . import models  # noqa: F401  (registra las tablas en Base)
from .database import Base, SessionLocal, engine, esperar_base
from .schema import schema
from .seed import sembrar


@asynccontextmanager
async def lifespan(app: FastAPI):
    esperar_base()
    Base.metadata.create_all(bind=engine)  # no borra filas existentes
    db = SessionLocal()
    try:
        sembrar(db)  # solo inserta si las tablas / el rol están vacíos
    finally:
        db.close()
    yield


app = FastAPI(title="Sistema General de Ingresos", lifespan=lifespan)
app.include_router(GraphQLRouter(schema), prefix="/graphql")
