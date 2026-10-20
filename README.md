# Sistema General de Ingresos — Unidad II · Actividad 3: Gestión de roles y permisos

**Autor:** Luis Edwuard Chay Ascorra · TSU en Desarrollo e Innovación de Software
**Materia:** Fundamentos de Arquitectura de Software y Desarrollo Backend

Seguridad basada en roles (RBAC, variante plana) sobre el Sistema General de Ingresos:
**Python + FastAPI + Strawberry (GraphQL en `/graphql`) + SQLAlchemy + MySQL + Docker Compose**.

La regla de la unidad: antes de escribir, el resolver recorre

```
membresía (CompanyUser) → rol activo → permisos activos de ese rol → ¿está el código que pide la operación?
```

Si el permiso falta, se lanza el error y **no hay commit**.

---

## 1. Estructura

```
unidad2_actividad3_edwuard_chay/
├── ingresos/
│   ├── database.py      # engine, sesión por operación, espera a MySQL
│   ├── models.py        # tablas (empresa, usuarios, cuentas... + roles y permisos)
│   ├── schema.py        # tipos, queries y mutations de GraphQL
│   ├── security.py      # hash de contraseña, token, exigir_permiso()
│   ├── seed.py          # 4 roles, 10 permisos y la matriz (solo si están vacíos)
│   └── main.py          # FastAPI + /graphql; crea tablas y siembra al arrancar
├── tests/               # 23 pruebas automáticas (SQLite en memoria, sin Docker)
├── consultas/
│   ├── pruebas.graphql  # operaciones para pegar en GraphiQL
│   └── verificacion.sql # SELECT para comparar MySQL contra la matriz
├── scripts/preparar_evidencias.py   # crea datos demo e imprime las consultas con tus ids
├── evidencias/          # aquí guardas tus capturas (ver evidencias.md)
├── evidencias.md        # qué ejecutar, qué debe salir y cómo nombrar cada captura
├── Dockerfile · docker-compose.yml · .env.example · requirements.txt · .gitignore
```

Las tablas se crean al arrancar con `Base.metadata.create_all` (no borra filas). No se usa Alembic.

## 2. Requisitos (Windows)

- Docker Desktop abierto y en estado *Running*.
- VS Code (opcional, para editar).
- Python 3.12 **solo** si quieres correr las pruebas automáticas fuera de Docker.

## 3. Levantar el proyecto

Abre PowerShell dentro de la carpeta del proyecto:

```powershell
Copy-Item .env.example .env
notepad .env          # cambia las claves; usa solo letras y números en las contraseñas
docker compose up --build -d
docker compose ps     # db: healthy, api: running
```

Abre **http://localhost:8000/graphql** (GraphiQL). Ver logs: `docker compose logs -f api`.

Detener: `docker compose down` (conserva datos) · borrar todo: `docker compose down -v`.

## 4. Datos de demostración y evidencias

```powershell
docker compose exec api python scripts/preparar_evidencias.py
```

Imprime tus ids reales y todas las consultas listas para pegar en GraphiQL. La guía de capturas está en
[`evidencias.md`](evidencias.md).

## 5. Pruebas automáticas

```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1      # si PowerShell bloquea scripts: Set-ExecutionPolicy -Scope Process Bypass
pip install -r requirements.txt
python -m pytest -q              # esperado: 23 passed
```

Usan SQLite en memoria, así que no necesitan Docker ni MySQL.

## 6. Flujo de uso (resumen)

1. `createCompany` → `createCompanyAdmin` (isAdmin = true **y** rol `ADMINISTRADOR`; un segundo admin falla).
2. El administrador usa `createCompanyUser` y luego `assignRole` para dar puesto a cada usuario.
3. Cada operación protegida recibe `actorCompanyUserId` (la membresía con la que pruebas en GraphiQL).
4. `queries`: `companyUsers`, `accounts`, `concepts`, `transactions` exigen su permiso `.read`.

Permisos exigidos: `createCompanyUser`/`deactivateCompanyUser` → `company.users.write` · `createAccount` →
`accounts.write` · `createConcept`/`assignConceptToAccount` → `concepts.write` · `createTransaction` →
`transactions.write` · `assignRole`/`assignPermissionToRole`/`removePermissionFromRole` → `roles.write`.

## 7. Decisiones y límites (leer antes de entregar)

- **No se recibió el proyecto base del equipo**, solo el PDF. Se reconstruyó una base mínima (empresa, usuarios,
  membresías, cuentas, conceptos, movimientos, login) con las reglas que describe el documento. Si tu equipo ya
  tiene ese código, conserva el tuyo y copia `seed.py`, `security.py`, las tablas de roles/permisos de
  `models.py` y los resolvers protegidos de `schema.py`.
- Siguiendo el documento, **no** piden `actorCompanyUserId`: `createCompany`, `createCompanyAdmin`, `login`,
  `createRole`, `deactivateRole`, `createPermission` y las consultas `roles`, `role`, `permissions`,
  `rolePermissions` (sus firmas no llevan actor). La identidad por token llega en la siguiente actividad.
- `removePermissionFromRole` recibe además `actorCompanyUserId` y exige `roles.write`, porque el catálogo de
  permisos dice que ese permiso cubre "asignar o quitar permisos de un rol".
- Un rol desactivado no concede permisos y una membresía desactivada ya no opera.
- `createCompanyUser` crea la membresía sin rol; hasta que el administrador ejecute `assignRole`, esa
  membresía recibe "La membresía no tiene un rol activo".
- Los datos de cada empresa se filtran por la empresa del actor; un id de otra empresa responde "no existe en esta empresa".
- Los montos en GraphQL son `Float`; en la base se guardan como `DECIMAL(14,2)`.

## 8. Qué se probó y qué no

- Probado: 23 pruebas automáticas (SQLite) y el flujo completo por HTTP contra un servidor MariaDB 10.11
  (compatible con MySQL): siembra, matriz, las 10 evidencias y reinicios sin duplicar roles.
- **No probado en el entorno de desarrollo:** `docker compose up` (no había Docker disponible) ni la imagen
  `mysql:8.0`. Verifícalo en tu equipo con los comandos de la sección 3.

## 9. Problemas frecuentes

| Síntoma | Solución |
|---|---|
| `port is already allocated` (3306/3307) | Cambia `MYSQL_HOST_PORT` en `.env` y repite `docker compose up -d`. |
| `port 8000 already in use` | Cierra el otro proceso o cambia `"8000:8000"` en `docker-compose.yml`. |
| `api` reinicia en bucle | `docker compose logs api`; revisa que `.env` exista y no tenga símbolos raros en las contraseñas. |
| Cambié la contraseña de MySQL y falla | El volumen conserva la anterior: `docker compose down -v` y vuelve a levantar. |
| GraphiQL no abre | Confirma `docker compose ps` y entra a `http://localhost:8000/graphql`. |
