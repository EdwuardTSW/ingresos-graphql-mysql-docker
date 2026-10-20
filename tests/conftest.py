"""Las pruebas usan SQLite en memoria: no necesitan Docker ni MySQL."""
import os

os.environ["DATABASE_URL"] = "sqlite://"
os.environ["SECRET_KEY"] = "clave-solo-para-pruebas-con-longitud-suficiente-123456"

import pytest  # noqa: E402

from ingresos import models  # noqa: E402,F401
from ingresos.database import Base, SessionLocal, engine  # noqa: E402
from ingresos.schema import schema  # noqa: E402
from ingresos.seed import sembrar  # noqa: E402


@pytest.fixture(autouse=True)
def base_limpia():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        sembrar(db)
    finally:
        db.close()
    yield


def gql(consulta: str, variables: dict | None = None):
    return schema.execute_sync(consulta, variable_values=variables or {})


def ok(consulta: str, variables: dict | None = None) -> dict:
    r = gql(consulta, variables)
    assert r.errors is None, [e.message for e in r.errors]
    return r.data


def falla(consulta: str, variables: dict | None = None) -> str:
    r = gql(consulta, variables)
    assert r.errors, "Se esperaba un error y la operación se aceptó"
    return r.errors[0].message


ROLES_Q = "query { roles { id code } }"


def id_rol(codigo: str) -> str:
    return next(r["id"] for r in ok(ROLES_Q)["roles"] if r["code"] == codigo)


def crear_empresa(nombre: str, correo_admin: str) -> str:
    """Crea empresa + administrador principal y devuelve el id de su membresía."""
    empresa = ok('mutation($n:String!){ createCompany(name:$n){ id } }', {"n": nombre})
    admin = ok(
        """mutation($i: CreateCompanyAdminInput!){
             createCompanyAdmin(input:$i){ id isAdmin role { code } } }""",
        {"i": {"companyId": empresa["createCompany"]["id"], "name": "Admin",
               "email": correo_admin, "password": "Secreta123"}},
    )
    return admin["createCompanyAdmin"]["id"]


def crear_miembro(actor: str, correo: str, rol: str) -> str:
    miembro = ok(
        """mutation($i: CreateCompanyUserInput!){
             createCompanyUser(input:$i){ id } }""",
        {"i": {"actorCompanyUserId": actor, "name": correo.split("@")[0],
               "email": correo, "password": "Secreta123"}},
    )["createCompanyUser"]["id"]
    ok(
        """mutation($i: AssignRoleInput!){ assignRole(input:$i){ id } }""",
        {"i": {"actorCompanyUserId": actor, "companyUserId": miembro, "roleId": id_rol(rol)}},
    )
    return miembro


@pytest.fixture
def empresa():
    """Empresa A con un miembro por rol, una cuenta y un concepto asignado."""
    admin = crear_empresa("Empresa A", "admin@a.com")
    datos = {
        "admin": admin,
        "contador": crear_miembro(admin, "contador@a.com", "CONTADOR"),
        "capturista": crear_miembro(admin, "capturista@a.com", "CAPTURISTA"),
        "consulta": crear_miembro(admin, "consulta@a.com", "CONSULTA"),
    }
    cuenta = ok(
        'mutation($i:CreateAccountInput!){ createAccount(input:$i){ id } }',
        {"i": {"actorCompanyUserId": datos["contador"], "name": "Caja"}},
    )["createAccount"]["id"]
    concepto = ok(
        'mutation($i:CreateConceptInput!){ createConcept(input:$i){ id } }',
        {"i": {"actorCompanyUserId": datos["contador"], "name": "Ventas", "type": "INCOME"}},
    )["createConcept"]["id"]
    ok(
        'mutation($i:AssignConceptToAccountInput!){ assignConceptToAccount(input:$i){ id } }',
        {"i": {"actorCompanyUserId": datos["contador"], "accountId": cuenta, "conceptId": concepto}},
    )
    datos.update(cuenta=cuenta, concepto=concepto)
    return datos


def movimiento(actor: str, cuenta: str, concepto: str, monto: float = 100.0):
    return gql(
        """mutation($i: CreateTransactionInput!){
             createTransaction(input:$i){ id amount type companyUserId } }""",
        {"i": {"actorCompanyUserId": actor, "accountId": cuenta, "conceptId": concepto,
               "type": "INCOME", "amount": monto, "description": "prueba"}},
    )
