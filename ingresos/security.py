"""Contraseñas, token de login y la regla que el resolver consulta antes de escribir."""
import hashlib
import hmac
import os
import secrets
from datetime import datetime, timedelta, timezone

import jwt
from sqlalchemy.orm import Session

from .models import (
    CompanyUserModel, CompanyUserRoleModel, PermissionModel, RoleModel,
    RolePermissionModel,
)

SECRET_KEY = os.getenv("SECRET_KEY", "cambia-esta-clave-en-tu-env-por-una-larga-y-aleatoria")
TOKEN_HORAS = 8
_ITERACIONES = 200_000


def hash_password(password: str) -> str:
    sal = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), sal.encode(), _ITERACIONES)
    return f"pbkdf2_sha256${_ITERACIONES}${sal}${digest.hex()}"


def verify_password(password: str, guardado: str) -> bool:
    try:
        _, iteraciones, sal, esperado = guardado.split("$")
        digest = hashlib.pbkdf2_hmac("sha256", password.encode(), sal.encode(), int(iteraciones))
    except ValueError:
        return False
    return hmac.compare_digest(digest.hex(), esperado)


def crear_token(user_id: int) -> str:
    expira = datetime.now(timezone.utc) + timedelta(hours=TOKEN_HORAS)
    return jwt.encode({"sub": str(user_id), "exp": expira}, SECRET_KEY, algorithm="HS256")


def exigir_permiso(db: Session, company_user_id: int, codigo: str) -> None:
    """membresía -> rol activo -> permisos activos del rol -> ¿está el código?

    Si el permiso falta lanza PermissionError y el resolver no llega al commit.
    Un rol desactivado no concede permisos.
    """
    asignacion = (
        db.query(CompanyUserRoleModel)
        .filter(
            CompanyUserRoleModel.company_user_id == company_user_id,
            CompanyUserRoleModel.is_active.is_(True),
        )
        .first()
    )
    if asignacion is None:
        raise PermissionError("La membresía no tiene un rol activo")
    permitido = (
        db.query(RolePermissionModel)
        .join(PermissionModel, RolePermissionModel.permission_id == PermissionModel.id)
        .join(RoleModel, RolePermissionModel.role_id == RoleModel.id)
        .filter(
            RolePermissionModel.role_id == asignacion.role_id,
            RolePermissionModel.is_active.is_(True),
            PermissionModel.code == codigo,
            PermissionModel.is_active.is_(True),
            RoleModel.is_active.is_(True),
        )
        .first()
    )
    if permitido is None:
        raise PermissionError(f"El rol no tiene el permiso {codigo}")


def exigir(db: Session, actor_company_user_id, codigo: str) -> CompanyUserModel:
    """Valida la membresía del actor, exige el permiso y devuelve la membresía.

    La empresa del actor es la frontera de datos: todo se filtra por ella.
    """
    try:
        actor_id = int(actor_company_user_id)
    except (TypeError, ValueError):
        raise ValueError("actorCompanyUserId inválido")
    actor = db.get(CompanyUserModel, actor_id)
    if actor is None or not actor.is_active or not actor.company.is_active:
        raise PermissionError("La membresía no existe o no está activa")
    exigir_permiso(db, actor_id, codigo)
    return actor
