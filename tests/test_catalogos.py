"""Parte 1 y 2: roles, permisos, matriz y siembra idempotente."""
from ingresos.database import SessionLocal
from ingresos.models import (
    PermissionModel, RoleModel, RolePermissionModel,
)
from ingresos.seed import MATRIZ, sembrar

from .conftest import crear_empresa, falla, id_rol, ok

ROLES_ESPERADOS = {"ADMINISTRADOR", "CONTADOR", "CAPTURISTA", "CONSULTA"}
PERMISOS_ESPERADOS = {
    "company.users.read", "company.users.write", "accounts.read", "accounts.write",
    "concepts.read", "concepts.write", "transactions.read", "transactions.write",
    "roles.read", "roles.write",
}


def codigos_de_rol(codigo_rol: str) -> set:
    data = ok("query($r:ID!){ rolePermissions(roleId:$r){ permission { code } isActive } }",
              {"r": id_rol(codigo_rol)})
    assert all(p["isActive"] for p in data["rolePermissions"])
    return {p["permission"]["code"] for p in data["rolePermissions"]}


def test_roles_y_permisos_se_consultan():
    roles = ok("query { roles { code name isActive } }")["roles"]
    assert {r["code"] for r in roles} == ROLES_ESPERADOS
    permisos = ok("query { permissions { code } }")["permissions"]
    assert {p["code"] for p in permisos} == PERMISOS_ESPERADOS
    assert len(permisos) == 10


def test_reinicio_no_duplica():
    for _ in range(3):  # simula reinicios del servidor
        db = SessionLocal()
        try:
            sembrar(db)
            assert db.query(RoleModel).count() == 4
            assert db.query(PermissionModel).count() == 10
            assert db.query(RolePermissionModel).count() == 8 + 10 + 4 + 4
        finally:
            db.close()


def test_matriz_coincide_con_el_documento():
    for codigo_rol, esperados in MATRIZ.items():
        assert codigos_de_rol(codigo_rol) == set(esperados)
    assert codigos_de_rol("ADMINISTRADOR") == PERMISOS_ESPERADOS
    assert "transactions.write" in codigos_de_rol("CAPTURISTA")
    assert "accounts.write" not in codigos_de_rol("CAPTURISTA")
    assert not any(c.endswith(".write") for c in codigos_de_rol("CONSULTA"))
    contador = codigos_de_rol("CONTADOR")
    assert "company.users.write" not in contador and "roles.write" not in contador


def test_codigos_unicos():
    assert "Ya existe" in falla(
        'mutation{ createRole(input:{code:"CONTADOR", name:"X"}){ id } }')
    assert "Ya existe" in falla(
        'mutation{ createPermission(input:{code:"accounts.read", name:"X"}){ id } }')
    nuevo = ok('mutation{ createRole(input:{code:"AUDITOR", name:"Auditor"}){ code isActive } }')
    assert nuevo["createRole"] == {"code": "AUDITOR", "isActive": True}


def test_desactivar_rol_no_borra_la_fila():
    rid = id_rol("CONSULTA")
    assert ok("mutation($i:ID!){ deactivateRole(id:$i){ isActive } }", {"i": rid}
              )["deactivateRole"]["isActive"] is False
    db = SessionLocal()
    try:
        assert db.query(RoleModel).count() == 4
    finally:
        db.close()
    activos = ok("query { roles(activeOnly:true){ code } }")["roles"]
    assert "CONSULTA" not in {r["code"] for r in activos}


def test_admin_principal_tiene_isadmin_y_rol():
    admin = crear_empresa("Empresa A", "admin@a.com")
    datos = ok("query($a:ID!){ companyUsers(actorCompanyUserId:$a){ id isAdmin role{code} } }",
               {"a": admin})["companyUsers"]
    assert datos == [{"id": admin, "isAdmin": True, "role": {"code": "ADMINISTRADOR"}}]


def test_segundo_admin_de_la_misma_empresa_falla():
    ok('mutation{ createCompany(name:"Empresa A"){ id } }')
    ok("""mutation{ createCompanyAdmin(input:{companyId:"1", name:"A", email:"a@a.com",
         password:"x1"}){ id } }""")
    assert "administrador principal" in falla(
        """mutation{ createCompanyAdmin(input:{companyId:"1", name:"B", email:"b@a.com",
           password:"x2"}){ id } }""")
