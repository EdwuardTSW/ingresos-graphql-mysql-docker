"""Esquema GraphQL (Strawberry). El tipo GraphQL no es la tabla: el resolver traduce.

Regla de la unidad: antes de escribir (o de leer datos de la empresa) el
resolver llama a exigir_permiso. Si el permiso falta, se lanza el error y no
hay commit.
"""
from datetime import datetime
from decimal import ROUND_HALF_UP, Decimal
from enum import Enum
from typing import List, Optional

import strawberry
from sqlalchemy import func

from .database import get_session
from .models import (
    AccountConceptModel, AccountModel, CompanyModel, CompanyUserModel,
    CompanyUserRoleModel, ConceptModel, PermissionModel, RoleModel,
    RolePermissionModel, TransactionModel, UserModel,
)
from .security import crear_token, exigir, hash_password, verify_password


# ------------------------------------------------------------------ enums
@strawberry.enum
class TransactionType(Enum):
    INCOME = "INCOME"
    EXPENSE = "EXPENSE"


# ------------------------------------------------------------------ tipos
@strawberry.type
class Company:
    id: strawberry.ID
    name: str
    is_active: bool


@strawberry.type
class User:
    """No expone password_hash."""
    id: strawberry.ID
    name: str
    email: str
    is_active: bool


@strawberry.type
class Role:
    id: strawberry.ID
    code: str
    name: str
    description: Optional[str]
    is_active: bool


@strawberry.type
class Permission:
    id: strawberry.ID
    code: str
    name: str
    description: Optional[str]
    is_active: bool


@strawberry.type
class RolePermission:
    id: strawberry.ID
    role: Role
    permission: Permission
    is_active: bool


@strawberry.type
class CompanyUser:
    id: strawberry.ID
    company: Company
    user: User
    is_admin: bool
    is_active: bool
    role: Optional[Role]


@strawberry.type
class CompanyUserRole:
    id: strawberry.ID
    company_user: CompanyUser
    role: Role
    is_active: bool


@strawberry.type
class Account:
    id: strawberry.ID
    name: str
    is_active: bool
    balance: float


@strawberry.type
class Concept:
    id: strawberry.ID
    name: str
    type: TransactionType
    is_active: bool


@strawberry.type
class AccountConcept:
    id: strawberry.ID
    account: Account
    concept: Concept
    is_active: bool


@strawberry.type
class Transaction:
    id: strawberry.ID
    account_id: strawberry.ID
    concept_id: strawberry.ID
    company_user_id: strawberry.ID
    type: TransactionType
    amount: float
    description: Optional[str]
    created_at: datetime


@strawberry.type
class LoginPayload:
    token: str
    user: User


# ----------------------------------------------------------------- inputs
@strawberry.input
class CreateRoleInput:
    code: str
    name: str
    description: Optional[str] = None


@strawberry.input
class CreatePermissionInput:
    code: str
    name: str
    description: Optional[str] = None


@strawberry.input
class AssignPermissionToRoleInput:
    actor_company_user_id: strawberry.ID
    role_id: strawberry.ID
    permission_id: strawberry.ID


@strawberry.input
class AssignRoleInput:
    actor_company_user_id: strawberry.ID
    company_user_id: strawberry.ID
    role_id: strawberry.ID


@strawberry.input
class CreateCompanyAdminInput:
    company_id: strawberry.ID
    name: str
    email: str
    password: str


@strawberry.input
class CreateCompanyUserInput:
    actor_company_user_id: strawberry.ID
    name: str
    email: str
    password: str


@strawberry.input
class CreateAccountInput:
    actor_company_user_id: strawberry.ID
    name: str


@strawberry.input
class CreateConceptInput:
    actor_company_user_id: strawberry.ID
    name: str
    type: TransactionType


@strawberry.input
class AssignConceptToAccountInput:
    actor_company_user_id: strawberry.ID
    account_id: strawberry.ID
    concept_id: strawberry.ID


@strawberry.input
class CreateTransactionInput:
    actor_company_user_id: strawberry.ID
    account_id: strawberry.ID
    concept_id: strawberry.ID
    type: TransactionType
    amount: float
    description: Optional[str] = None


# ------------------------------------------------------------- utilidades
def _id(valor, nombre: str = "id") -> int:
    try:
        return int(valor)
    except (TypeError, ValueError):
        raise ValueError(f"{nombre} inválido")


def _texto(valor: str, nombre: str) -> str:
    limpio = (valor or "").strip()
    if not limpio:
        raise ValueError(f"{nombre} no puede estar vacío")
    return limpio


def _de_empresa(db, modelo, id_, company_id: int, nombre: str):
    """Obtiene un registro solo si pertenece a la empresa del actor."""
    obj = db.get(modelo, _id(id_, nombre))
    if obj is None or obj.company_id != company_id:
        raise ValueError(f"{nombre} no existe en esta empresa")
    return obj


# ------------------------------------------------------------- conversores
def _company(m: CompanyModel) -> Company:
    return Company(id=strawberry.ID(str(m.id)), name=m.name, is_active=m.is_active)


def _user(m: UserModel) -> User:
    return User(id=strawberry.ID(str(m.id)), name=m.name, email=m.email, is_active=m.is_active)


def _role(m: RoleModel) -> Role:
    return Role(id=strawberry.ID(str(m.id)), code=m.code, name=m.name,
                description=m.description, is_active=m.is_active)


def _permission(m: PermissionModel) -> Permission:
    return Permission(id=strawberry.ID(str(m.id)), code=m.code, name=m.name,
                      description=m.description, is_active=m.is_active)


def _role_permission(m: RolePermissionModel) -> RolePermission:
    return RolePermission(id=strawberry.ID(str(m.id)), role=_role(m.role),
                          permission=_permission(m.permission), is_active=m.is_active)


def _rol_activo(db, company_user_id: int) -> Optional[RoleModel]:
    asignacion = (
        db.query(CompanyUserRoleModel)
        .filter(CompanyUserRoleModel.company_user_id == company_user_id,
                CompanyUserRoleModel.is_active.is_(True))
        .first()
    )
    return asignacion.role if asignacion else None


def _company_user(db, m: CompanyUserModel) -> CompanyUser:
    rol = _rol_activo(db, m.id)
    return CompanyUser(
        id=strawberry.ID(str(m.id)), company=_company(m.company), user=_user(m.user),
        is_admin=m.is_admin, is_active=m.is_active,
        role=_role(rol) if rol else None,
    )


def _company_user_role(db, m: CompanyUserRoleModel) -> CompanyUserRole:
    return CompanyUserRole(id=strawberry.ID(str(m.id)),
                           company_user=_company_user(db, m.company_user),
                           role=_role(m.role), is_active=m.is_active)


def _saldo(db, account_id: int) -> float:
    total = Decimal("0")
    filas = db.query(TransactionModel.type, TransactionModel.amount).filter(
        TransactionModel.account_id == account_id)
    for tipo, monto in filas:
        total += Decimal(monto) if tipo == "INCOME" else -Decimal(monto)
    return float(total)


def _account(db, m: AccountModel) -> Account:
    return Account(id=strawberry.ID(str(m.id)), name=m.name, is_active=m.is_active,
                   balance=_saldo(db, m.id))


def _concept(m: ConceptModel) -> Concept:
    return Concept(id=strawberry.ID(str(m.id)), name=m.name,
                   type=TransactionType(m.type), is_active=m.is_active)


def _account_concept(db, m: AccountConceptModel) -> AccountConcept:
    return AccountConcept(id=strawberry.ID(str(m.id)), account=_account(db, m.account),
                          concept=_concept(m.concept), is_active=m.is_active)


def _transaction(m: TransactionModel) -> Transaction:
    return Transaction(
        id=strawberry.ID(str(m.id)), account_id=strawberry.ID(str(m.account_id)),
        concept_id=strawberry.ID(str(m.concept_id)),
        company_user_id=strawberry.ID(str(m.company_user_id)),
        type=TransactionType(m.type), amount=float(m.amount),
        description=m.description, created_at=m.created_at,
    )


# ------------------------------------------------------------------ Query
@strawberry.type
class Query:
    # --- catálogos de roles y permisos (firmas del documento)
    @strawberry.field
    def roles(self, active_only: Optional[bool] = None) -> List[Role]:
        with get_session() as db:
            consulta = db.query(RoleModel)
            if active_only:
                consulta = consulta.filter(RoleModel.is_active.is_(True))
            return [_role(r) for r in consulta.order_by(RoleModel.id).all()]

    @strawberry.field
    def role(self, id: strawberry.ID) -> Optional[Role]:
        with get_session() as db:
            m = db.get(RoleModel, _id(id))
            return _role(m) if m else None

    @strawberry.field
    def permissions(self, active_only: Optional[bool] = None) -> List[Permission]:
        with get_session() as db:
            consulta = db.query(PermissionModel)
            if active_only:
                consulta = consulta.filter(PermissionModel.is_active.is_(True))
            return [_permission(p) for p in consulta.order_by(PermissionModel.id).all()]

    @strawberry.field
    def role_permissions(self, role_id: strawberry.ID) -> List[RolePermission]:
        """Permisos activos de un rol."""
        with get_session() as db:
            filas = (
                db.query(RolePermissionModel)
                .filter(RolePermissionModel.role_id == _id(role_id, "roleId"),
                        RolePermissionModel.is_active.is_(True))
                .order_by(RolePermissionModel.id)
                .all()
            )
            return [_role_permission(f) for f in filas]

    # --- consultas protegidas con .read
    @strawberry.field
    def company_users(self, actor_company_user_id: strawberry.ID) -> List[CompanyUser]:
        with get_session() as db:
            actor = exigir(db, actor_company_user_id, "company.users.read")
            filas = (db.query(CompanyUserModel)
                     .filter(CompanyUserModel.company_id == actor.company_id)
                     .order_by(CompanyUserModel.id).all())
            return [_company_user(db, f) for f in filas]

    @strawberry.field
    def accounts(self, actor_company_user_id: strawberry.ID) -> List[Account]:
        with get_session() as db:
            actor = exigir(db, actor_company_user_id, "accounts.read")
            filas = (db.query(AccountModel)
                     .filter(AccountModel.company_id == actor.company_id)
                     .order_by(AccountModel.id).all())
            return [_account(db, f) for f in filas]

    @strawberry.field
    def concepts(self, actor_company_user_id: strawberry.ID) -> List[Concept]:
        with get_session() as db:
            actor = exigir(db, actor_company_user_id, "concepts.read")
            filas = (db.query(ConceptModel)
                     .filter(ConceptModel.company_id == actor.company_id)
                     .order_by(ConceptModel.id).all())
            return [_concept(f) for f in filas]

    @strawberry.field
    def transactions(self, actor_company_user_id: strawberry.ID) -> List[Transaction]:
        with get_session() as db:
            actor = exigir(db, actor_company_user_id, "transactions.read")
            filas = (db.query(TransactionModel)
                     .filter(TransactionModel.company_id == actor.company_id)
                     .order_by(TransactionModel.id).all())
            return [_transaction(f) for f in filas]


# --------------------------------------------------------------- Mutation
@strawberry.type
class Mutation:
    # --- base previa: empresa, administrador principal y login
    @strawberry.mutation
    def create_company(self, name: str) -> Company:
        with get_session() as db:
            empresa = CompanyModel(name=_texto(name, "name"))
            db.add(empresa)
            db.commit()
            return _company(empresa)

    @strawberry.mutation
    def create_company_admin(self, input: CreateCompanyAdminInput) -> CompanyUser:
        """isAdmin = true (solo uno por empresa) y además el rol ADMINISTRADOR."""
        with get_session() as db:
            empresa = db.get(CompanyModel, _id(input.company_id, "companyId"))
            if empresa is None or not empresa.is_active:
                raise ValueError("La empresa no existe o está inactiva")
            ya_hay = (db.query(CompanyUserModel)
                      .filter(CompanyUserModel.company_id == empresa.id,
                              CompanyUserModel.is_admin.is_(True)).first())
            if ya_hay is not None:
                raise ValueError("La empresa ya tiene un administrador principal")
            rol_admin = db.query(RoleModel).filter(RoleModel.code == "ADMINISTRADOR").first()
            if rol_admin is None or not rol_admin.is_active:
                raise ValueError("El rol ADMINISTRADOR no existe o está inactivo")
            email = _texto(input.email, "email").lower()
            if db.query(UserModel).filter(func.lower(UserModel.email) == email).first():
                raise ValueError("El correo ya está registrado")
            usuario = UserModel(name=_texto(input.name, "name"), email=email,
                                password_hash=hash_password(input.password))
            db.add(usuario)
            db.flush()
            membresia = CompanyUserModel(company_id=empresa.id, user_id=usuario.id, is_admin=True)
            db.add(membresia)
            db.flush()
            db.add(CompanyUserRoleModel(company_user_id=membresia.id, role_id=rol_admin.id))
            db.commit()
            return _company_user(db, membresia)

    @strawberry.mutation
    def login(self, email: str, password: str) -> LoginPayload:
        with get_session() as db:
            usuario = (db.query(UserModel)
                       .filter(func.lower(UserModel.email) == (email or "").strip().lower())
                       .first())
            if (usuario is None or not usuario.is_active
                    or not verify_password(password, usuario.password_hash)):
                raise ValueError("Credenciales inválidas")
            return LoginPayload(token=crear_token(usuario.id), user=_user(usuario))

    # --- roles (catálogo)
    @strawberry.mutation
    def create_role(self, input: CreateRoleInput) -> Role:
        with get_session() as db:
            codigo = _texto(input.code, "code")
            if db.query(RoleModel).filter(func.lower(RoleModel.code) == codigo.lower()).first():
                raise ValueError(f"Ya existe un rol con el código {codigo}")
            rol = RoleModel(code=codigo, name=_texto(input.name, "name"),
                            description=input.description)
            db.add(rol)
            db.commit()
            return _role(rol)

    @strawberry.mutation
    def deactivate_role(self, id: strawberry.ID) -> Role:
        """No hay borrado físico: el rol se desactiva."""
        with get_session() as db:
            rol = db.get(RoleModel, _id(id))
            if rol is None:
                raise ValueError("El rol no existe")
            rol.is_active = False
            db.commit()
            return _role(rol)

    # --- permisos (catálogo)
    @strawberry.mutation
    def create_permission(self, input: CreatePermissionInput) -> Permission:
        with get_session() as db:
            codigo = _texto(input.code, "code")
            if db.query(PermissionModel).filter(
                    func.lower(PermissionModel.code) == codigo.lower()).first():
                raise ValueError(f"Ya existe un permiso con el código {codigo}")
            permiso = PermissionModel(code=codigo, name=_texto(input.name, "name"),
                                      description=input.description)
            db.add(permiso)
            db.commit()
            return _permission(permiso)

    # --- permisos por rol (roles.write)
    @strawberry.mutation
    def assign_permission_to_role(self, input: AssignPermissionToRoleInput) -> RolePermission:
        with get_session() as db:
            exigir(db, input.actor_company_user_id, "roles.write")
            rol = db.get(RoleModel, _id(input.role_id, "roleId"))
            permiso = db.get(PermissionModel, _id(input.permission_id, "permissionId"))
            if rol is None or not rol.is_active:
                raise ValueError("El rol no existe o está inactivo")
            if permiso is None or not permiso.is_active:
                raise ValueError("El permiso no existe o está inactivo")
            pareja = (db.query(RolePermissionModel)
                      .filter(RolePermissionModel.role_id == rol.id,
                              RolePermissionModel.permission_id == permiso.id)
                      .first())
            if pareja is not None and pareja.is_active:
                raise ValueError("Ese permiso ya está asignado al rol")
            if pareja is None:
                pareja = RolePermissionModel(role_id=rol.id, permission_id=permiso.id)
                db.add(pareja)
            else:
                pareja.is_active = True  # reactiva la fila desactivada antes
            db.commit()
            return _role_permission(pareja)

    @strawberry.mutation
    def remove_permission_from_role(
        self, actor_company_user_id: strawberry.ID,
        role_id: strawberry.ID, permission_id: strawberry.ID,
    ) -> bool:
        """Desactiva la pareja; no borra la fila."""
        with get_session() as db:
            exigir(db, actor_company_user_id, "roles.write")
            pareja = (db.query(RolePermissionModel)
                      .filter(RolePermissionModel.role_id == _id(role_id, "roleId"),
                              RolePermissionModel.permission_id == _id(permission_id, "permissionId"),
                              RolePermissionModel.is_active.is_(True))
                      .first())
            if pareja is None:
                raise ValueError("Ese permiso no está activo en el rol")
            pareja.is_active = False
            db.commit()
            return True

    # --- rol de la membresía (roles.write)
    @strawberry.mutation
    def assign_role(self, input: AssignRoleInput) -> CompanyUserRole:
        """Deja un solo rol activo por membresía."""
        with get_session() as db:
            actor = exigir(db, input.actor_company_user_id, "roles.write")
            membresia = _de_empresa(db, CompanyUserModel, input.company_user_id,
                                    actor.company_id, "companyUserId")
            if not membresia.is_active:
                raise ValueError("La membresía está inactiva")
            rol = db.get(RoleModel, _id(input.role_id, "roleId"))
            if rol is None or not rol.is_active:
                raise ValueError("El rol no existe o está inactivo")
            activas = (db.query(CompanyUserRoleModel)
                       .filter(CompanyUserRoleModel.company_user_id == membresia.id,
                               CompanyUserRoleModel.is_active.is_(True)).all())
            vigente = next((a for a in activas if a.role_id == rol.id), None)
            for a in activas:
                if a is not vigente:
                    a.is_active = False
            if vigente is None:
                vigente = CompanyUserRoleModel(company_user_id=membresia.id, role_id=rol.id)
                db.add(vigente)
            db.commit()
            return _company_user_role(db, vigente)

    # --- usuarios de la empresa (company.users.write)
    @strawberry.mutation
    def create_company_user(self, input: CreateCompanyUserInput) -> CompanyUser:
        """Crea el usuario y su membresía en la empresa del actor (sin rol: usa assignRole)."""
        with get_session() as db:
            actor = exigir(db, input.actor_company_user_id, "company.users.write")
            email = _texto(input.email, "email").lower()
            if db.query(UserModel).filter(func.lower(UserModel.email) == email).first():
                raise ValueError("El correo ya está registrado")
            usuario = UserModel(name=_texto(input.name, "name"), email=email,
                                password_hash=hash_password(input.password))
            db.add(usuario)
            db.flush()
            membresia = CompanyUserModel(company_id=actor.company_id, user_id=usuario.id)
            db.add(membresia)
            db.commit()
            return _company_user(db, membresia)

    @strawberry.mutation
    def deactivate_company_user(
        self, actor_company_user_id: strawberry.ID, company_user_id: strawberry.ID,
    ) -> CompanyUser:
        with get_session() as db:
            actor = exigir(db, actor_company_user_id, "company.users.write")
            membresia = _de_empresa(db, CompanyUserModel, company_user_id,
                                    actor.company_id, "companyUserId")
            membresia.is_active = False
            db.commit()
            return _company_user(db, membresia)

    # --- cuentas (accounts.write)
    @strawberry.mutation
    def create_account(self, input: CreateAccountInput) -> Account:
        with get_session() as db:
            actor = exigir(db, input.actor_company_user_id, "accounts.write")
            cuenta = AccountModel(company_id=actor.company_id, name=_texto(input.name, "name"))
            db.add(cuenta)
            db.commit()
            return _account(db, cuenta)

    # --- conceptos (concepts.write)
    @strawberry.mutation
    def create_concept(self, input: CreateConceptInput) -> Concept:
        with get_session() as db:
            actor = exigir(db, input.actor_company_user_id, "concepts.write")
            concepto = ConceptModel(company_id=actor.company_id,
                                    name=_texto(input.name, "name"), type=input.type.value)
            db.add(concepto)
            db.commit()
            return _concept(concepto)

    @strawberry.mutation
    def assign_concept_to_account(self, input: AssignConceptToAccountInput) -> AccountConcept:
        with get_session() as db:
            actor = exigir(db, input.actor_company_user_id, "concepts.write")
            cuenta = _de_empresa(db, AccountModel, input.account_id, actor.company_id, "accountId")
            concepto = _de_empresa(db, ConceptModel, input.concept_id, actor.company_id, "conceptId")
            if not cuenta.is_active or not concepto.is_active:
                raise ValueError("La cuenta y el concepto deben estar activos")
            pareja = (db.query(AccountConceptModel)
                      .filter(AccountConceptModel.account_id == cuenta.id,
                              AccountConceptModel.concept_id == concepto.id).first())
            if pareja is not None and pareja.is_active:
                raise ValueError("Ese concepto ya está asignado a la cuenta")
            if pareja is None:
                pareja = AccountConceptModel(account_id=cuenta.id, concept_id=concepto.id)
                db.add(pareja)
            else:
                pareja.is_active = True
            db.commit()
            return _account_concept(db, pareja)

    # --- movimientos (transactions.write)
    @strawberry.mutation
    def create_transaction(self, input: CreateTransactionInput) -> Transaction:
        with get_session() as db:
            # 1) El permiso se exige antes de validar y antes del commit.
            actor = exigir(db, input.actor_company_user_id, "transactions.write")
            # 2) Reglas que ya tenía el movimiento.
            monto = Decimal(str(input.amount)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
            if monto <= 0:
                raise ValueError("El monto debe ser mayor que cero")
            cuenta = _de_empresa(db, AccountModel, input.account_id, actor.company_id, "accountId")
            concepto = _de_empresa(db, ConceptModel, input.concept_id, actor.company_id, "conceptId")
            if not cuenta.is_active or not concepto.is_active:
                raise ValueError("La cuenta y el concepto deben estar activos")
            permitido = (db.query(AccountConceptModel)
                         .filter(AccountConceptModel.account_id == cuenta.id,
                                 AccountConceptModel.concept_id == concepto.id,
                                 AccountConceptModel.is_active.is_(True)).first())
            if permitido is None:
                raise ValueError("El concepto no está permitido en esa cuenta")
            movimiento = TransactionModel(
                company_id=actor.company_id, account_id=cuenta.id, concept_id=concepto.id,
                company_user_id=actor.id, type=input.type.value, amount=monto,
                description=input.description,
            )
            db.add(movimiento)
            db.commit()
            return _transaction(movimiento)


schema = strawberry.Schema(query=Query, mutation=Mutation)
