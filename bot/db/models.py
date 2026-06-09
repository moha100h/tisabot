import enum, random, string
from datetime import datetime
from sqlalchemy import (
    BigInteger, Boolean, DateTime, Enum, ForeignKey,
    Integer, String, Text, func
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from db.database import Base


def _gen_code() -> str:
    return "T" + "".join(random.choices(string.digits, k=6))


class UserRole(str, enum.Enum):
    USER  = "user"
    ADMIN = "admin"
    SUPER = "super"


class ListingType(str, enum.Enum):
    SALE        = "sale"
    RENT        = "rent"
    PARTNERSHIP = "partnership"


class PropertyType(str, enum.Enum):
    APARTMENT  = "apartment"
    VILLA      = "villa"
    COMMERCIAL = "commercial"
    LAND       = "land"
    OFFICE     = "office"
    OTHER      = "other"


class ListingStatus(str, enum.Enum):
    PENDING   = "pending"
    APPROVED  = "approved"
    REJECTED  = "rejected"
    AVAILABLE = "available"
    SOLD      = "sold"
    RENTED    = "rented"
    MORTGAGED = "mortgaged"
    INACTIVE  = "inactive"


class User(Base):
    __tablename__ = "users"

    id          : Mapped[int]      = mapped_column(Integer, primary_key=True)
    telegram_id : Mapped[int]      = mapped_column(BigInteger, unique=True, index=True)
    full_name   : Mapped[str]      = mapped_column(String(128))
    phone       : Mapped[str]      = mapped_column(String(20))
    username    : Mapped[str|None] = mapped_column(String(64), nullable=True)
    role        : Mapped[UserRole] = mapped_column(Enum(UserRole), default=UserRole.USER)
    is_blocked  : Mapped[bool]     = mapped_column(Boolean, default=False)
    created_at  : Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    listings : Mapped[list["Listing"]] = relationship(back_populates="owner",
                                                       cascade="all, delete-orphan")


class Listing(Base):
    __tablename__ = "listings"

    id               : Mapped[int]           = mapped_column(Integer, primary_key=True)
    code             : Mapped[str]           = mapped_column(String(16), default=_gen_code, unique=True)
    owner_id         : Mapped[int]           = mapped_column(BigInteger, ForeignKey("users.telegram_id"))
    listing_type     : Mapped[ListingType]   = mapped_column(Enum(ListingType))
    property_type    : Mapped[PropertyType]  = mapped_column(Enum(PropertyType))
    province         : Mapped[str]           = mapped_column(String(64))
    city             : Mapped[str]           = mapped_column(String(64))
    district         : Mapped[str|None]      = mapped_column(String(64),  nullable=True)
    address          : Mapped[str|None]      = mapped_column(String(512), nullable=True)
    contact_phone    : Mapped[str|None]      = mapped_column(String(20),  nullable=True)
    area             : Mapped[int|None]      = mapped_column(Integer, nullable=True)
    bedrooms         : Mapped[int|None]      = mapped_column(Integer, nullable=True)
    price            : Mapped[int|None]      = mapped_column(BigInteger, nullable=True)
    mortgage         : Mapped[int|None]      = mapped_column(BigInteger, nullable=True)
    rent             : Mapped[int|None]      = mapped_column(BigInteger, nullable=True)
    facilities       : Mapped[str|None]      = mapped_column(Text, nullable=True)
    description      : Mapped[str|None]      = mapped_column(Text, nullable=True)
    status           : Mapped[ListingStatus] = mapped_column(Enum(ListingStatus),
                                                              default=ListingStatus.PENDING)
    rejection_reason : Mapped[str|None]      = mapped_column(Text, nullable=True)
    review_msg_id    : Mapped[int|None]      = mapped_column(Integer, nullable=True)
    created_at       : Mapped[datetime]      = mapped_column(DateTime, server_default=func.now())

    owner  : Mapped["User"]               = relationship(back_populates="listings")
    images : Mapped[list["ListingImage"]] = relationship(back_populates="listing",
                                                          cascade="all, delete-orphan",
                                                          order_by="ListingImage.order")


class ListingImage(Base):
    __tablename__ = "listing_images"

    id         : Mapped[int] = mapped_column(Integer, primary_key=True)
    listing_id : Mapped[int] = mapped_column(Integer, ForeignKey("listings.id"))
    file_id    : Mapped[str] = mapped_column(String(256))
    order      : Mapped[int] = mapped_column(Integer, default=0)

    listing : Mapped["Listing"] = relationship(back_populates="images")


class Consultant(Base):
    __tablename__ = "consultants"

    id            : Mapped[int]      = mapped_column(Integer, primary_key=True)
    name          : Mapped[str]      = mapped_column(String(128))
    phone         : Mapped[str]      = mapped_column(String(20))
    telegram      : Mapped[str|None] = mapped_column(String(64), nullable=True)
    working_hours : Mapped[str|None] = mapped_column(String(64), nullable=True)


class Setting(Base):
    __tablename__ = "settings"

    id    : Mapped[int] = mapped_column(Integer, primary_key=True)
    key   : Mapped[str] = mapped_column(String(64), unique=True, index=True)
    value : Mapped[str] = mapped_column(Text, default='')