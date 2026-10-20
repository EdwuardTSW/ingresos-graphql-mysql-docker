"""Datos iniciales: 4 roles, 10 permisos y la matriz del documento.

Cada paso solo inserta si su tabla (o el rol) está vacío, así un reinicio
no duplica nada.
"""
from sqlalchemy.orm import Session

from .models import PermissionModel, RoleModel, RolePermissionModel

ROLES = [
    ("ADMINISTRADOR", "Administrador", "Administrador principal de la empresa"),
    ("CONTADOR", "Contador", "Arma cuentas y conceptos y registra movimientos"),
    ("CAPTURISTA", "Capturista", "Registra ingresos y egresos"),
    ("CONSULTA", "Consulta", "Solo lee"),
]

PERMISOS = [
    ("company.users.read", "Ver usuarios de la empresa", "Ver las membresías de la empresa"),
    ("company.users.write", "Administrar usuarios", "Crear usuarios y desactivar membresías"),
    ("accounts.read", "Consultar cuentas", "Consultar cuentas"),
    ("accounts.write", "Crear cuentas", "Crear cuentas"),
    ("concepts.read", "Consultar conceptos", "Consultar conceptos"),
    ("concepts.write", "Crear conceptos", "Crear conceptos y asignarlos a una cuenta"),
    ("transactions.read", "Consultar movimientos", "Consultar movimientos"),
    ("transactions.write", "Registrar movimientos", "Registrar un ingreso o un egreso"),
    ("roles.read", "Ver roles", "Ver roles y la matriz de permisos"),
    ("roles.write", "Administrar roles", "Asignar o quitar permisos de un rol y asignar un rol a una membresía"),
]

_TODOS = [codigo for codigo, _, _ in PERMISOS]

# Matriz del documento (filas = permisos, columnas = roles), leída por rol.
MATRIZ = {
    "ADMINISTRADOR": _TODOS,
    "CONTADOR": [
        "company.users.read",
        "accounts.read", "accounts.write",
        "concepts.read", "concepts.write",
        "transactions.read", "transactions.write",
        "roles.read",
    ],
    "CAPTURISTA": [
        "accounts.read", "concepts.read",
        "transactions.read", "transactions.write",
    ],
    "CONSULTA": [
        "company.users.read", "accounts.read",
        "concepts.read", "transactions.read",
    ],
}


def sembrar(db: Session) -> None:
    if db.query(RoleModel).count() == 0:
        for codigo, nombre, descripcion in ROLES:
            db.add(RoleModel(code=codigo, name=nombre, description=descripcion))
    if db.query(PermissionModel).count() == 0:
        for codigo, nombre, descripcion in PERMISOS:
            db.add(PermissionModel(code=codigo, name=nombre, description=descripcion))
    db.flush()

    roles = {r.code: r for r in db.query(RoleModel).all()}
    permisos = {p.code: p for p in db.query(PermissionModel).all()}
    for codigo_rol, codigos in MATRIZ.items():
        rol = roles.get(codigo_rol)
        if rol is None:
            continue
        if db.query(RolePermissionModel).filter_by(role_id=rol.id).count() == 0:
            for codigo in codigos:
                permiso = permisos.get(codigo)
                if permiso is not None:
                    db.add(RolePermissionModel(role_id=rol.id, permission_id=permiso.id))
    db.commit()
