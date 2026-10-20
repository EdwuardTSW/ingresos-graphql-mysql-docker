"""Prepara datos de demostración contra la API ya levantada y imprime las
consultas listas para pegar en GraphiQL (con tus ids reales).

Uso (con la API corriendo en http://localhost:8000):
    docker compose exec api python scripts/preparar_evidencias.py
    # o, sin Docker para la API:  python scripts/preparar_evidencias.py

Es seguro repetirlo: cada ejecución crea una empresa nueva con correos únicos.
Solo usa la librería estándar de Python.
"""
import json
import os
import sys
import time
import unicodedata
import urllib.error
import urllib.request

URL = os.getenv("GRAPHQL_URL", "http://localhost:8000/graphql")


def gql(consulta: str, variables: dict | None = None) -> dict:
    cuerpo = json.dumps({"query": consulta, "variables": variables or {}}).encode()
    req = urllib.request.Request(URL, cuerpo, {"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.load(r)
    except urllib.error.URLError:
        sys.exit(f"No se pudo conectar a {URL}. Levanta la API primero (docker compose up -d).")


def ok(consulta: str, variables: dict | None = None) -> dict:
    r = gql(consulta, variables)
    if r.get("errors"):
        sys.exit(f"Error inesperado: {r['errors'][0]['message']}")
    return r["data"]


def main() -> None:
    sufijo = str(int(time.time()))
    roles = {r["code"]: r["id"] for r in ok("{ roles { id code } }")["roles"]}

    empresa = ok("mutation($n:String!){ createCompany(name:$n){ id } }",
                 {"n": f"Empresa Demo {sufijo}"})["createCompany"]["id"]
    admin = ok(
        "mutation($i:CreateCompanyAdminInput!){ createCompanyAdmin(input:$i){ id } }",
        {"i": {"companyId": empresa, "name": "Admin Demo",
               "email": f"admin{sufijo}@demo.com", "password": "Demo12345"}},
    )["createCompanyAdmin"]["id"]

    miembros = {"ADMINISTRADOR": admin}
    for codigo in ("CONTADOR", "CAPTURISTA", "CONSULTA"):
        mid = ok(
            "mutation($i:CreateCompanyUserInput!){ createCompanyUser(input:$i){ id } }",
            {"i": {"actorCompanyUserId": admin, "name": codigo.title(),
                   "email": f"{codigo.lower()}{sufijo}@demo.com", "password": "Demo12345"}},
        )["createCompanyUser"]["id"]
        ok("mutation($i:AssignRoleInput!){ assignRole(input:$i){ id } }",
           {"i": {"actorCompanyUserId": admin, "companyUserId": mid, "roleId": roles[codigo]}})
        miembros[codigo] = mid

    cuenta = ok("mutation($i:CreateAccountInput!){ createAccount(input:$i){ id } }",
                {"i": {"actorCompanyUserId": miembros["CONTADOR"], "name": "Caja"}})["createAccount"]["id"]
    concepto = ok("mutation($i:CreateConceptInput!){ createConcept(input:$i){ id } }",
                  {"i": {"actorCompanyUserId": miembros["CONTADOR"], "name": "Ventas",
                         "type": "INCOME"}})["createConcept"]["id"]
    ok("mutation($i:AssignConceptToAccountInput!){ assignConceptToAccount(input:$i){ id } }",
       {"i": {"actorCompanyUserId": miembros["CONTADOR"], "accountId": cuenta, "conceptId": concepto}})

    c = miembros
    texto = f"""
==================== DATOS DE DEMOSTRACIÓN ====================
Empresa id ........... {empresa}
Membresía ADMINISTRADOR  = {c['ADMINISTRADOR']}
Membresía CONTADOR ...... = {c['CONTADOR']}
Membresía CAPTURISTA .... = {c['CAPTURISTA']}   (la que se pasa de capturista a contador)
Membresía CONSULTA ...... = {c['CONSULTA']}
Cuenta id = {cuenta}    Concepto id = {concepto}
Rol id: CAPTURISTA = {roles['CAPTURISTA']}, CONSULTA = {roles['CONSULTA']}, CONTADOR = {roles['CONTADOR']}

Pega cada bloque en http://localhost:8000/graphql (uno por captura).

--- EV 1: roles
{{ roles {{ id code name isActive }} }}

--- EV 2: permissions
{{ permissions {{ id code name isActive }} }}

--- EV 3: rolePermissions del CAPTURISTA (incluye transactions.write, NO accounts.write)
{{ rolePermissions(roleId: "{roles['CAPTURISTA']}") {{ permission {{ code }} isActive }} }}

--- EV 4: rolePermissions de CONSULTA (ningún .write)
{{ rolePermissions(roleId: "{roles['CONSULTA']}") {{ permission {{ code }} isActive }} }}

--- EV 5: movimiento ACEPTADO (capturista)
mutation {{ createTransaction(input: {{ actorCompanyUserId: "{c['CAPTURISTA']}", accountId: "{cuenta}",
  conceptId: "{concepto}", type: INCOME, amount: 1500, description: "Venta de prueba" }}) {{
  id amount type companyUserId }} }}

--- EV 6: movimiento RECHAZADO (consulta)
mutation {{ createTransaction(input: {{ actorCompanyUserId: "{c['CONSULTA']}", accountId: "{cuenta}",
  conceptId: "{concepto}", type: INCOME, amount: 1500, description: "Debe rechazarse" }}) {{ id }} }}

--- EV 6b: la tabla no ganó esa fila (solo debe verse el movimiento del capturista)
{{ transactions(actorCompanyUserId: "{c['CONTADOR']}") {{ id companyUserId amount description }} }}

--- EV 7: createAccount ACEPTADO (contador)
mutation {{ createAccount(input: {{ actorCompanyUserId: "{c['CONTADOR']}", name: "Banco" }}) {{ id name }} }}

--- EV 8: createAccount RECHAZADO (capturista)
mutation {{ createAccount(input: {{ actorCompanyUserId: "{c['CAPTURISTA']}", name: "Cuenta pirata" }}) {{ id }} }}

--- EV 9: assignRole capturista -> contador (lo ejecuta el administrador)
mutation {{ assignRole(input: {{ actorCompanyUserId: "{c['ADMINISTRADOR']}", companyUserId: "{c['CAPTURISTA']}",
  roleId: "{roles['CONTADOR']}" }}) {{ isActive role {{ code }} companyUser {{ id role {{ code }} }} }} }}

--- EV 9b: ahora ese mismo usuario SÍ crea cuenta (repite EV 8 y debe aceptarse)
mutation {{ createAccount(input: {{ actorCompanyUserId: "{c['CAPTURISTA']}", name: "Cuenta del ex capturista" }}) {{ id name }} }}

--- EV 10: segundo administrador principal en la MISMA empresa (debe fallar)
mutation {{ createCompanyAdmin(input: {{ companyId: "{empresa}", name: "Otro Admin",
  email: "otro{sufijo}@demo.com", password: "Demo12345" }}) {{ id }} }}
===============================================================
"""
    # Sin acentos para que cualquier consola de Windows lo muestre bien.
    print(unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode())


if __name__ == "__main__":
    main()
