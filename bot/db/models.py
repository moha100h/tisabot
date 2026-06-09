from __future__ import annotations
import enum
from datetime import datetime
from sqlalchemy import (BigInteger, Boolean, DateTime, Enum, ForeignKey,
    Integer, String, Text, func)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from db.database import Base


class UserRole(str, enum.Enum):
    USER  = "user"
    ADMIN = "admin"
    SUPER = "super"

class ListingType(str, enum.Enum):
    SALE        = "sale"
    RENT        = "rent"
    PARTNERSHIP = "partnership"

class ListingStatus(str, enum.Enum):
    PENDING   = "pending"
    APPROVED  = "approved"
    REJECTED  = "rejected"
    AVAILABLE = "available"
    SOLD      = "sold"
    RENTED    = "rented"
    MORTGAGED = "mortgaged"
    INACTIVE  = "inactive"

class PropertyType(str, enum.Enum):
    APARTMENT  = "apartment"
    VILLA      = "villa"
    COMMERCIAL = "commercial"
    LAND       = "land"
    OFFICE     = "office"
    OTHER      = "other"


class User(Base):
    __tablename__ = "users"
    id:          Mapped[int]      = mapped_column(BigInteger, primary_key=True)
    telegram_id: Mapped[int]      = mapped_column(BigInteger, unique=True, index=True)
    full_name:   Mapped[str]      = mapped_column(String(128))
    phone:       Mapped[str]      = mapped_column(String(20))
    username:    Mapped[str|None] = mapped_column(String(64), nullable=True)
    role:        Mapped[UserRole] = mapped_column(Enum(UserRole), default=UserRole.USER)
    is_blocked:  Mapped[bool]     = mapped_column(Boolean, default=False)
    created_at:  Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at:  Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())
    listings:    Mapped[list[Listing]]   = relationship("Listing", back_populates="owner", lazy="select")
    permissions: Mapped[list[AdminPerm]] = relationship("AdminPerm", back_populates="user", lazy="select")


class Listing(Base):
    __tablename__ = "listings"
    id:               Mapped[int]           = mapped_column(Integer, primary_key=True, autoincrement=True)
    code:             Mapped[str]           = mapped_column(String(12), unique=True, index=True)
    owner_id:         Mapped[int]           = mapped_column(BigInteger, ForeignKey("users.telegram_id"))
    listing_type:     Mapped[ListingType]   = mapped_column(Enum(ListingType))
    property_type:    Mapped[PropertyType]  = mapped_column(Enum(PropertyType))
    status:           Mapped[ListingStatus] = mapped_column(Enum(ListingStatus), default=ListingStatus.PENDING)
    province:         Mapped[str]           = mapped_column(String(64))
    city:             Mapped[str]           = mapped_column(String(64))
    district:         Mapped[str|None]      = mapped_column(String(64),  nullable=True)
    address:          Mapped[str|None]      = mapped_column(String(256), nullable=True)
    area:             Mapped[int|None]      = mapped_column(Integer,     nullable=True)
    bedrooms:         Mapped[int|None]      = mapped_column(Integer,     nullable=True)
    price:            Mapped[int|None]      = mapped_column(BigInteger,  nullable=True)
    mortgage:         Mapped[int|None]      = mapped_column(BigInteger,  nullable=True)
    rent:             Mapped[int|None]      = mapped_column(BigInteger,  nullable=True)
    description:      Mapped[str|None]      = mapped_column(Text, nullable=True)
    facilities:       Mapped[str|None]      = mapped_column(Text, nullable=True)
    rejection_reason: Mapped[str|None]      = mapped_column(Text, nullable=True)
    review_msg_id:    Mapped[int|None]      = mapped_column(BigInteger, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())
    owner:  Mapped[User]               = relationship("User", back_populates="listings")
    images: Mapped[list[ListingImage]] = relationship("ListingImage", back_populates="listing", cascade="all, delete-orphan")


class ListingImage(Base):
    __tablename__ = "listing_images"
    id:         Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    listing_id: Mapped[int] = mapped_column(Integer, ForeignKey("listings.id", ondelete="CASCADE"))
    file_id:    Mapped[str] = mapped_column(String(256))
    order:      Mapped[int] = mapped_column(Integer, default=0)
    listing: Mapped[Listing] = relationship("Listing", back_populates="images")


class Consultant(Base):
    __tablename__ = "consultants"
    id:            Mapped[int]      = mapped_column(Integer, primary_key=True, autoincrement=True)
    name:          Mapped[str]      = mapped_column(String(128))
    phone:         Mapped[str]      = mapped_column(String(20))
    telegram:      Mapped[str|None] = mapped_column(String(64),  nullable=True)
    working_hours: Mapped[str|None] = mapped_column(String(128), nullable=True)
    office:        Mapped[str|None] = mapped_column(String(256), nullable=True)
    is_active:     Mapped[bool]     = mapped_column(Boolean, default=True)


class Setting(Base):
    __tablename__ = "settings"
    key:   Mapped[str] = mapped_column(String(64), primary_key=True)
    value: Mapped[str] = mapped_column(Text, default="")


class AdminPerm(Base):
    __tablename__ = "admin_perms"
    id:      Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.telegram_id"))
    perm:    Mapped[str] = mapped_column(String(64))
    user: Mapped[User] = relationship("User", back_populates="permissions")
