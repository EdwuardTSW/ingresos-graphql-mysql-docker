"""Conexión a la base de datos (MySQL por defecto, SQLite solo para pruebas)."""
import os
import time
from contextlib import contextmanager

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import declarative_base, sessionmaker
from sqlalchemy.pool import StaticPool

load_dotenv()

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "mysql+pymysql://ingresos_user:ingresos_pass@localhost:3307/ingresos",
)


def _crear_engine(url: str):
    if url.startswith("sqlite"):
        opciones = {"connect_args": {"check_same_thread": False}}
        if url in ("sqlite://", "sqlite:///:memory:"):
            opciones["poolclass"] = StaticPool
        return create_engine(url, **opciones)
    return create_engine(url, pool_pre_ping=True)


engine = _crear_engine(DATABASE_URL)
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)
Base = declarative_base()


@contextmanager
def get_session():
    """Sesión por operación. Si algo falla antes del commit, no se escribe nada."""
    db = SessionLocal()
    try:
        yield db
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def esperar_base(intentos: int = 30, espera: float = 2.0) -> None:
    """MySQL tarda unos segundos en aceptar conexiones al levantar Docker."""
    for _ in range(intentos):
        try:
            with engine.connect():
                return
        except OperationalError:
            time.sleep(espera)
    raise RuntimeError("No se pudo conectar a la base de datos")
