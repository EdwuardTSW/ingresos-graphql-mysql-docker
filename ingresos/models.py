"""Modelos SQLAlchemy. El tipo GraphQL no es la tabla: aquí viven las tablas."""
from datetime import datetime

from sqlalchemy import (
    Boolean, Column, DateTime, ForeignKey, Integer, Numeric, String,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship

from .database import Base


# ---------------------------------------------------------------- base previa
class CompanyModel(Base):
    __tablename__ = "companies"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(150), nullable=False)
    is_active = Column(Boolean, nullable=False, default=True)


class UserModel(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(150), nullable=False)
    email = Column(String(150), unique=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    is_active = Column(Boolean, nullable=False, default=True)


class CompanyUserModel(Base):
    """Membresía: puente empresa-usuario. El rol NO vive en User."""
    __tablename__ = "company_users"
    __table_args__ = (UniqueConstraint("company_id", "user_id"),)
    id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey("companies.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    is_admin = Column(Boolean, nullable=False, default=False)
    is_active = Column(Boolean, nullable=False, default=True)
    company = relationship("CompanyModel")
    user = relationship("UserModel")


class AccountModel(Base):
    __tablename__ = "accounts"
    id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey("companies.id"), nullable=False)
    name = Column(String(100), nullable=False)
    is_active = Column(Boolean, nullable=False, default=True)


class ConceptModel(Base):
    __tablename__ = "concepts"
    id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey("companies.id"), nullable=False)
    name = Column(String(100), nullable=False)
    type = Column(String(10), nullable=False)  # INCOME | EXPENSE
    is_active = Column(Boolean, nullable=False, default=True)


class AccountConceptModel(Base):
    __tablename__ = "account_concepts"
    id = Column(Integer, primary_key=True, index=True)
    account_id = Column(Integer, ForeignKey("accounts.id"), nullable=False)
    concept_id = Column(Integer, ForeignKey("concepts.id"), nullable=False)
    is_active = Column(Boolean, nullable=False, default=True)
    account = relationship("AccountModel")
    concept = relationship("ConceptModel")


class TransactionModel(Base):
    __tablename__ = "transactions"
    id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey("companies.id"), nullable=False)
    account_id = Column(Integer, ForeignKey("accounts.id"), nullable=False)
    concept_id = Column(Integer, ForeignKey("concepts.id"), nullable=False)
    company_user_id = Column(Integer, ForeignKey("company_users.id"), nullable=False)
    type = Column(String(10), nullable=False)  # INCOME | EXPENSE
    amount = Column(Numeric(14, 2), nullable=False)
    description = Column(String(255))
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)


# ------------------------------------------------- Actividad 3: roles/permisos
class RoleModel(Base):
    __tablename__ = "roles"
    id = Column(Integer, primary_key=True, index=True)
    code = Column(String(50), unique=True, nullable=False)
    name = Column(String(100), nullable=False)
    description = Column(String(255))
    is_active = Column(Boolean, nullable=False, default=True)


class PermissionModel(Base):
    __tablename__ = "permissions"
    id = Column(Integer, primary_key=True, index=True)
    code = Column(String(50), unique=True, nullable=False)
    name = Column(String(100), nullable=False)
    description = Column(String(255))
    is_active = Column(Boolean, nullable=False, default=True)


class RolePermissionModel(Base):
    __tablename__ = "role_permissions"
    id = Column(Integer, primary_key=True, index=True)
    role_id = Column(Integer, ForeignKey("roles.id"), nullable=False)
    permission_id = Column(Integer, ForeignKey("permissions.id"), nullable=False)
    is_active = Column(Boolean, nullable=False, default=True)
    role = relationship("RoleModel")
    permission = relationship("PermissionModel")


class CompanyUserRoleModel(Base):
    __tablename__ = "company_user_roles"
    id = Column(Integer, primary_key=True, index=True)
    company_user_id = Column(Integer, ForeignKey("company_users.id"), nullable=False)
    role_id = Column(Integer, ForeignKey("roles.id"), nullable=False)
    is_active = Column(Boolean, nullable=False, default=True)
    company_user = relationship("CompanyUserModel")
    role = relationship("RoleModel")
