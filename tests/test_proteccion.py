"""Parte 3: las mutaciones y consultas existentes exigen permiso antes de escribir."""
from ingresos.database import SessionLocal
from ingresos.models import (
    AccountModel, CompanyUserRoleModel, ConceptModel, RolePermissionModel,
    TransactionModel, UserModel,
)

from .conftest import crear_empresa, crear_miembro, falla, gql, id_rol, movimiento, ok

CREAR_CUENTA = 'mutation($i:CreateAccountInput!){ createAccount(input:$i){ id name } }'
ASIGNAR_ROL = 'mutation($i:AssignRoleInput!){ assignRole(input:$i){ role{code} isActive } }'


def contar(modelo, **filtros) -> int:
    db = SessionLocal()
    try:
        return db.query(modelo).filter_by(**filtros).count()
    finally:
        db.close()


def test_capturista_registra_movimiento(empresa):
    r = movimiento(empresa["capturista"], empresa["cuenta"], empresa["concepto"], 250.5)
    assert r.errors is None
    assert r.data["createTransaction"]["amount"] == 250.5
    assert r.data["createTransaction"]["companyUserId"] == empresa["capturista"]
    assert contar(TransactionModel) == 1


def test_consulta_no_registra_y_no_queda_fila(empresa):
    r = movimiento(empresa["consulta"], empresa["cuenta"], empresa["concepto"])
    assert r.errors and "transactions.write" in r.errors[0].message
    assert contar(TransactionModel) == 0


def test_monto_debe_ser_mayor_que_cero(empresa):
    r = movimiento(empresa["capturista"], empresa["cuenta"], empresa["concepto"], 0)
    assert r.errors and "mayor que cero" in r.errors[0].message
    assert contar(TransactionModel) == 0


def test_concepto_debe_estar_permitido_en_la_cuenta(empresa):
    otro = ok('mutation($i:CreateConceptInput!){ createConcept(input:$i){ id } }',
              {"i": {"actorCompanyUserId": empresa["contador"], "name": "Renta",
                     "type": "EXPENSE"}})["createConcept"]["id"]
    r = movimiento(empresa["capturista"], empresa["cuenta"], otro)
    assert r.errors and "no está permitido" in r.errors[0].message


def test_contador_crea_cuenta_y_capturista_no(empresa):
    cuentas_antes = contar(AccountModel)
    ok(CREAR_CUENTA, {"i": {"actorCompanyUserId": empresa["contador"], "name": "Banco"}})
    assert contar(AccountModel) == cuentas_antes + 1
    msg = falla(CREAR_CUENTA, {"i": {"actorCompanyUserId": empresa["capturista"], "name": "X"}})
    assert "accounts.write" in msg
    assert contar(AccountModel) == cuentas_antes + 1


def test_assign_role_cambia_capturista_a_contador(empresa):
    cap = empresa["capturista"]
    assert "accounts.write" in falla(CREAR_CUENTA, {"i": {"actorCompanyUserId": cap, "name": "X"}})
    r = ok(ASIGNAR_ROL, {"i": {"actorCompanyUserId": empresa["admin"],
                               "companyUserId": cap, "roleId": id_rol("CONTADOR")}})
    assert r["assignRole"] == {"role": {"code": "CONTADOR"}, "isActive": True}
    ok(CREAR_CUENTA, {"i": {"actorCompanyUserId": cap, "name": "Ahora sí"}})
    assert contar(CompanyUserRoleModel, company_user_id=int(cap), is_active=True) == 1
    assert contar(CompanyUserRoleModel, company_user_id=int(cap)) == 2  # el historial queda


def test_solo_roles_write_asigna_roles(empresa):
    msg = falla(ASIGNAR_ROL, {"i": {"actorCompanyUserId": empresa["contador"],
                                    "companyUserId": empresa["capturista"],
                                    "roleId": id_rol("CONSULTA")}})
    assert "roles.write" in msg


def test_assign_permission_to_role_rechaza_duplicados_y_remove_desactiva(empresa):
    asignar = 'mutation($i:AssignPermissionToRoleInput!){ assignPermissionToRole(input:$i){ isActive } }'
    quitar = """mutation($a:ID!,$r:ID!,$p:ID!){
        removePermissionFromRole(actorCompanyUserId:$a, roleId:$r, permissionId:$p) }"""
    permisos = ok("query { permissions { id code } }")["permissions"]
    pid = next(p["id"] for p in permisos if p["code"] == "accounts.write")
    rid = id_rol("CAPTURISTA")
    admin = empresa["admin"]
    entrada = {"i": {"actorCompanyUserId": admin, "roleId": rid, "permissionId": pid}}

    ok(asignar, entrada)
    assert "ya está asignado" in falla(asignar, entrada)
    assert contar(RolePermissionModel, role_id=int(rid), permission_id=int(pid)) == 1
    # Ahora el capturista sí puede crear cuentas
    ok(CREAR_CUENTA, {"i": {"actorCompanyUserId": empresa["capturista"], "name": "Nueva"}})

    assert ok(quitar, {"a": admin, "r": rid, "p": pid})["removePermissionFromRole"] is True
    assert contar(RolePermissionModel, role_id=int(rid), permission_id=int(pid)) == 1  # fila queda
    assert contar(RolePermissionModel, role_id=int(rid), permission_id=int(pid),
                  is_active=True) == 0
    assert "accounts.write" in falla(
        CREAR_CUENTA, {"i": {"actorCompanyUserId": empresa["capturista"], "name": "Otra"}})
    # Solo roles.write puede quitar permisos
    assert "roles.write" in falla(quitar, {"a": empresa["contador"], "r": rid, "p": pid})


def test_rol_desactivado_no_concede_permisos(empresa):
    ok("mutation($i:ID!){ deactivateRole(id:$i){ id } }", {"i": id_rol("CAPTURISTA")})
    r = movimiento(empresa["capturista"], empresa["cuenta"], empresa["concepto"])
    assert r.errors and "transactions.write" in r.errors[0].message


def test_consultas_exigen_read(empresa):
    sin_rol = ok(
        """mutation($i: CreateCompanyUserInput!){ createCompanyUser(input:$i){ id } }""",
        {"i": {"actorCompanyUserId": empresa["admin"], "name": "Sin rol",
               "email": "sinrol@a.com", "password": "x"}})["createCompanyUser"]["id"]
    for consulta in ("accounts{ id }", "concepts{ id }", "transactions{ id }",
                     "companyUsers{ id }"):
        q = "query($a:ID!){ %s }" % consulta.replace("{", "(actorCompanyUserId:$a){", 1)
        assert "rol activo" in falla(q, {"a": sin_rol})
        ok(q, {"a": empresa["consulta"]}) if consulta != "companyUsers{ id }" else None
    # capturista lee cuentas pero no usuarios (company.users.read)
    ok("query($a:ID!){ accounts(actorCompanyUserId:$a){ id } }", {"a": empresa["capturista"]})
    assert "company.users.read" in falla(
        "query($a:ID!){ companyUsers(actorCompanyUserId:$a){ id } }", {"a": empresa["capturista"]})


def test_usuarios_exigen_company_users_write(empresa):
    crear = """mutation($i: CreateCompanyUserInput!){ createCompanyUser(input:$i){ id } }"""
    entrada = {"i": {"actorCompanyUserId": empresa["contador"], "name": "N",
                     "email": "n@a.com", "password": "x"}}
    assert "company.users.write" in falla(crear, entrada)
    assert contar(UserModel, email="n@a.com") == 0
    desactivar = """mutation($a:ID!,$c:ID!){
        deactivateCompanyUser(actorCompanyUserId:$a, companyUserId:$c){ isActive } }"""
    assert "company.users.write" in falla(desactivar, {"a": empresa["contador"],
                                                       "c": empresa["consulta"]})
    r = ok(desactivar, {"a": empresa["admin"], "c": empresa["consulta"]})
    assert r["deactivateCompanyUser"]["isActive"] is False
    # una membresía desactivada ya no opera
    assert "no está activa" in falla("query($a:ID!){ accounts(actorCompanyUserId:$a){ id } }",
                                     {"a": empresa["consulta"]})


def test_conceptos_exigen_concepts_write(empresa):
    q = 'mutation($i:CreateConceptInput!){ createConcept(input:$i){ id } }'
    entrada = {"i": {"actorCompanyUserId": empresa["capturista"], "name": "X", "type": "EXPENSE"}}
    assert "concepts.write" in falla(q, entrada)
    assert contar(ConceptModel) == 1
    q2 = 'mutation($i:AssignConceptToAccountInput!){ assignConceptToAccount(input:$i){ id } }'
    assert "concepts.write" in falla(q2, {"i": {"actorCompanyUserId": empresa["capturista"],
                                                "accountId": empresa["cuenta"],
                                                "conceptId": empresa["concepto"]}})


def test_empresas_no_se_mezclan(empresa):
    admin_b = crear_empresa("Empresa B", "admin@b.com")
    contador_b = crear_miembro(admin_b, "contador@b.com", "CONTADOR")
    cuentas_b = ok("query($a:ID!){ accounts(actorCompanyUserId:$a){ id } }",
                   {"a": contador_b})["accounts"]
    assert cuentas_b == []
    # el contador de B no puede usar la cuenta/concepto de A
    r = movimiento(contador_b, empresa["cuenta"], empresa["concepto"])
    assert r.errors and "no existe en esta empresa" in r.errors[0].message
    # el administrador de B no puede cambiar el rol de una membresía de A
    msg = falla(ASIGNAR_ROL, {"i": {"actorCompanyUserId": admin_b,
                                    "companyUserId": empresa["capturista"],
                                    "roleId": id_rol("CONTADOR")}})
    assert "no existe en esta empresa" in msg
    # ni verla en company users
    visibles = ok("query($a:ID!){ companyUsers(actorCompanyUserId:$a){ id } }",
                  {"a": admin_b})["companyUsers"]
    assert empresa["capturista"] not in {u["id"] for u in visibles}


def test_login_y_user_sin_hash(empresa):
    r = ok('mutation{ login(email:"capturista@a.com", password:"Secreta123"){ token user{ email } } }')
    assert r["login"]["token"] and r["login"]["user"]["email"] == "capturista@a.com"
    assert "Credenciales" in falla('mutation{ login(email:"capturista@a.com", password:"mal"){ token } }')
    assert gql('mutation{ login(email:"capturista@a.com", password:"Secreta123"){ user{ passwordHash } } }').errors
    db = SessionLocal()
    try:
        u = db.query(UserModel).filter_by(email="capturista@a.com").one()
        assert u.password_hash.startswith("pbkdf2_sha256$") and "Secreta123" not in u.password_hash
    finally:
        db.close()


def test_saldo_suma_ingresos_y_resta_egresos(empresa):
    movimiento(empresa["capturista"], empresa["cuenta"], empresa["concepto"], 500)
    gasto = gql("""mutation($i:CreateTransactionInput!){ createTransaction(input:$i){ id } }""",
                {"i": {"actorCompanyUserId": empresa["capturista"], "accountId": empresa["cuenta"],
                       "conceptId": empresa["concepto"], "type": "EXPENSE", "amount": 120.25}})
    assert gasto.errors is None
    cuentas = ok("query($a:ID!){ accounts(actorCompanyUserId:$a){ balance } }",
                 {"a": empresa["consulta"]})["accounts"]
    assert cuentas[0]["balance"] == 379.75
