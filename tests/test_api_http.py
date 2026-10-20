"""Prueba de humo por HTTP: la app arranca (crea tablas, siembra) y /graphql responde."""
from fastapi.testclient import TestClient

from ingresos.main import app


def test_graphql_por_http_y_reinicio_sin_duplicados():
    for _ in range(2):  # dos arranques seguidos = reinicio del servidor
        with TestClient(app) as cliente:
            r = cliente.post("/graphql", json={"query": "{ roles { code } permissions { code } }"})
            assert r.status_code == 200
            data = r.json()["data"]
            assert [x["code"] for x in data["roles"]] == [
                "ADMINISTRADOR", "CONTADOR", "CAPTURISTA", "CONSULTA"]
            assert len(data["permissions"]) == 10
