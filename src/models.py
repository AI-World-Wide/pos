# -*- coding: utf-8 -*-
"""ORM models for Cafe POS — full schema, even tables that aren't queried until later phases.

Schema decisions:
- `items.price_inclusive`: VAT-inclusive sticker price. Net + VAT derived at order close.
- `users` + `permissions`: 5 seeded accounts, PIN-hashed.
- `printers`: Windows spooler names + purpose mapping.
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, relationship


class Base(DeclarativeBase):
    pass


class Category(Base):
    __tablename__ = "categories"

    id = Column(Integer, primary_key=True)
    name_ar = Column(String, nullable=False)
    name_en = Column(String, nullable=False, unique=True)
    sort_order = Column(Integer, default=9999)
    is_beverage = Column(Integer, default=0)  # 1 = receipt only, never to kitchen
    visible = Column(Integer, default=1)
    color = Column(String, default="#FFFFFF")

    items = relationship("Item", back_populates="category", cascade="all, delete-orphan")


class Item(Base):
    __tablename__ = "items"

    id = Column(Integer, primary_key=True)
    category_id = Column(Integer, ForeignKey("categories.id"), nullable=False)
    name_ar = Column(String, nullable=False)
    name_en = Column(String)
    price_inclusive = Column(Float, nullable=False)  # VAT-included sticker price
    cost = Column(Float, default=0)
    barcode = Column(String)
    kitchen_station = Column(String, default="")  # '' / Bar / Shisha / Kitchen
    visible = Column(Integer, default=1)
    sort_order = Column(Integer, default=9999)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    category = relationship("Category", back_populates="items")


class Order(Base):
    __tablename__ = "orders"

    id = Column(Integer, primary_key=True)
    order_number = Column(String, unique=True)  # e.g. 2026-05-20-0001
    created_at = Column(DateTime, default=datetime.utcnow)
    closed_at = Column(DateTime)
    status = Column(String, default="open")  # open / sent / settled / voided
    subtotal = Column(Float, default=0)
    vat_amount = Column(Float, default=0)
    total = Column(Float, default=0)
    payment_method = Column(String)  # cash / card
    cash_received = Column(Float)
    change_due = Column(Float)
    cashier = Column(String)  # username from users table
    notes = Column(Text)

    lines = relationship("OrderLine", back_populates="order", cascade="all, delete-orphan")


class OrderLine(Base):
    __tablename__ = "order_lines"

    id = Column(Integer, primary_key=True)
    order_id = Column(Integer, ForeignKey("orders.id"), nullable=False)
    item_id = Column(Integer, ForeignKey("items.id"))
    item_name_ar = Column(String)  # snapshot at order time
    quantity = Column(Integer, default=1)
    unit_price_inclusive = Column(Float)  # snapshot of price_inclusive
    line_total = Column(Float)  # unit_price_inclusive * quantity
    sent_to_kitchen = Column(Integer, default=0)
    voided = Column(Integer, default=0)

    order = relationship("Order", back_populates="lines")


class Setting(Base):
    __tablename__ = "settings"

    key = Column(String, primary_key=True)
    value = Column(Text)


class PrintQueue(Base):
    __tablename__ = "print_queue"

    id = Column(Integer, primary_key=True)
    order_id = Column(Integer, ForeignKey("orders.id"))
    type = Column(String)  # receipt / kitchen
    status = Column(String, default="pending")  # pending / printed / failed
    attempts = Column(Integer, default=0)
    error_message = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True)
    username = Column(String, unique=True, nullable=False)
    name_ar = Column(String, nullable=False)
    role = Column(String, nullable=False)  # admin / cashier / waiter
    pin_hash = Column(String, nullable=False)
    active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class Permission(Base):
    __tablename__ = "permissions"

    id = Column(Integer, primary_key=True)
    role = Column(String, nullable=False)
    permission_key = Column(String, nullable=False)
    granted = Column(Boolean, default=False)

    __table_args__ = (UniqueConstraint("role", "permission_key", name="uq_role_perm"),)


class Printer(Base):
    __tablename__ = "printers"

    id = Column(Integer, primary_key=True)
    name = Column(String, unique=True, nullable=False)  # Windows spooler name e.g. "Bar"
    purpose = Column(String, default="receipt")  # receipt / kitchen / shisha
    enabled = Column(Boolean, default=True)
    last_seen_at = Column(DateTime)
