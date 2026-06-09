from sqlalchemy import select, update, delete, func, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from db.models import (User, Listing, ListingImage, Consultant,
                       Setting, UserRole, ListingStatus, ListingType, PropertyType)
from typing import Optional


# ── Users ─────────────────────────────────────────────────────
async def get_user(db: AsyncSession, telegram_id: int) -> Optional[User]:
    r = await db.execute(select(User).where(User.telegram_id == telegram_id))
    return r.scalar_one_or_none()


async def create_user(db: AsyncSession, telegram_id: int, full_name: str,
                      phone: str, username: str | None = None) -> User:
    user = User(telegram_id=telegram_id, full_name=full_name,
                phone=phone, username=username)
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


async def update_user(db: AsyncSession, telegram_id: int, **kwargs) -> None:
    await db.execute(update(User).where(User.telegram_id == telegram_id).values(**kwargs))
    await db.commit()


async def list_users(db: AsyncSession, limit: int = 20, offset: int = 0) -> list[User]:
    r = await db.execute(select(User).order_by(User.created_at.desc())
                         .limit(limit).offset(offset))
    return list(r.scalars().all())


async def search_users(db: AsyncSession, query: str) -> list[User]:
    q = f"%{query}%"
    r = await db.execute(
        select(User).where(
            or_(User.full_name.ilike(q), User.phone.ilike(q),
                User.username.ilike(q))
        ).limit(10)
    )
    return list(r.scalars().all())


async def count_users(db: AsyncSession) -> int:
    r = await db.execute(select(func.count()).select_from(User))
    return r.scalar_one()


# ── Listings ──────────────────────────────────────────────────
async def create_listing(db: AsyncSession, owner_id: int,
                         listing_type: ListingType, property_type: PropertyType,
                         province: str, city: str, **kwargs) -> Listing:
    lst = Listing(owner_id=owner_id, listing_type=listing_type,
                  property_type=property_type, province=province,
                  city=city, **kwargs)
    db.add(lst)
    await db.commit()
    await db.refresh(lst)
    return lst


async def get_listing(db: AsyncSession, listing_id: int) -> Optional[Listing]:
    r = await db.execute(
        select(Listing)
        .options(selectinload(Listing.owner), selectinload(Listing.images))
        .where(Listing.id == listing_id)
    )
    return r.scalar_one_or_none()


async def list_listings(db: AsyncSession,
                        status: Optional[ListingStatus] = None,
                        owner_id: Optional[int] = None,
                        limit: int = 20) -> list[Listing]:
    q = select(Listing).options(selectinload(Listing.owner),
                                 selectinload(Listing.images))
    if status:
        q = q.where(Listing.status == status)
    if owner_id:
        q = q.where(Listing.owner_id == owner_id)
    q = q.order_by(Listing.created_at.desc()).limit(limit)
    r = await db.execute(q)
    return list(r.scalars().all())


async def search_listings(db: AsyncSession,
                          listing_type: Optional[ListingType] = None,
                          property_type: Optional[PropertyType] = None,
                          province: Optional[str] = None,
                          city: Optional[str] = None) -> list[Listing]:
    q = (select(Listing)
         .options(selectinload(Listing.owner), selectinload(Listing.images))
         .where(Listing.status == ListingStatus.APPROVED))
    if listing_type:  q = q.where(Listing.listing_type  == listing_type)
    if property_type: q = q.where(Listing.property_type == property_type)
    if province:      q = q.where(Listing.province.ilike(f"%{province}%"))
    if city:          q = q.where(Listing.city.ilike(f"%{city}%"))
    q = q.order_by(Listing.created_at.desc()).limit(20)
    r = await db.execute(q)
    return list(r.scalars().all())


async def update_listing(db: AsyncSession, listing_id: int, **kwargs) -> None:
    await db.execute(update(Listing).where(Listing.id == listing_id).values(**kwargs))
    await db.commit()


async def delete_listing(db: AsyncSession, listing_id: int) -> None:
    await db.execute(delete(Listing).where(Listing.id == listing_id))
    await db.commit()


async def add_listing_image(db: AsyncSession, listing_id: int,
                             file_id: str, order: int = 0) -> ListingImage:
    img = ListingImage(listing_id=listing_id, file_id=file_id, order=order)
    db.add(img)
    await db.commit()
    return img


# ── Consultants ───────────────────────────────────────────────
async def list_consultants(db: AsyncSession) -> list[Consultant]:
    r = await db.execute(select(Consultant))
    return list(r.scalars().all())


async def create_consultant(db: AsyncSession, **kwargs) -> Consultant:
    c = Consultant(**kwargs)
    db.add(c)
    await db.commit()
    await db.refresh(c)
    return c


async def delete_consultant(db: AsyncSession, consultant_id: int) -> None:
    await db.execute(delete(Consultant).where(Consultant.id == consultant_id))
    await db.commit()


# ── Settings ──────────────────────────────────────────────────
async def get_setting(db: AsyncSession, key: str, default: str = "") -> str:
    r = await db.execute(select(Setting).where(Setting.key == key))
    s = r.scalar_one_or_none()
    return s.value if s else default


async def set_setting(db: AsyncSession, key: str, value: str) -> None:
    r = await db.execute(select(Setting).where(Setting.key == key))
    s = r.scalar_one_or_none()
    if s:
        s.value = value
    else:
        db.add(Setting(key=key, value=value))
    await db.commit()
