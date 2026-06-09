from __future__ import annotations
import random, string
from sqlalchemy import select, update, delete, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from db.models import (User, Listing, ListingImage, Consultant,
    Setting, AdminPerm, ListingStatus, ListingType, PropertyType)


def _gen_code(n: int = 8) -> str:
    return "".join(random.choices(string.ascii_uppercase + string.digits, k=n))


# ── User ──────────────────────────────────────────────────────
async def get_user(db: AsyncSession, tid: int) -> User | None:
    r = await db.execute(select(User).where(User.telegram_id == tid))
    return r.scalar_one_or_none()

async def create_user(db: AsyncSession, tid: int, full_name: str,
                      phone: str, username: str | None = None) -> User:
    u = User(telegram_id=tid, full_name=full_name, phone=phone, username=username)
    db.add(u); await db.commit(); await db.refresh(u)
    return u

async def update_user(db: AsyncSession, tid: int, **kw) -> None:
    await db.execute(update(User).where(User.telegram_id == tid).values(**kw))
    await db.commit()

async def list_users(db: AsyncSession, offset: int = 0, limit: int = 20) -> list[User]:
    r = await db.execute(select(User).order_by(User.created_at.desc()).offset(offset).limit(limit))
    return list(r.scalars().all())

async def count_users(db: AsyncSession) -> int:
    r = await db.execute(select(func.count()).select_from(User))
    return r.scalar_one()

async def search_users(db: AsyncSession, q: str) -> list[User]:
    p = f"%{q}%"
    r = await db.execute(select(User).where(
        User.full_name.ilike(p) | User.phone.ilike(p) | User.username.ilike(p)
    ).limit(20))
    return list(r.scalars().all())


# ── Listing ───────────────────────────────────────────────────
async def create_listing(db: AsyncSession, owner_id: int,
                         listing_type: ListingType, property_type: PropertyType,
                         **kw) -> Listing:
    code = _gen_code()
    while await get_listing_by_code(db, code):
        code = _gen_code()
    lst = Listing(owner_id=owner_id, listing_type=listing_type,
                  property_type=property_type, code=code, **kw)
    db.add(lst); await db.commit(); await db.refresh(lst)
    return lst

async def get_listing(db: AsyncSession, lid: int) -> Listing | None:
    r = await db.execute(
        select(Listing).options(selectinload(Listing.images), selectinload(Listing.owner))
        .where(Listing.id == lid))
    return r.scalar_one_or_none()

async def get_listing_by_code(db: AsyncSession, code: str) -> Listing | None:
    r = await db.execute(select(Listing).where(Listing.code == code))
    return r.scalar_one_or_none()

async def get_listing_by_review_msg(db: AsyncSession, msg_id: int) -> Listing | None:
    r = await db.execute(select(Listing).where(Listing.review_msg_id == msg_id))
    return r.scalar_one_or_none()

async def update_listing(db: AsyncSession, lid: int, **kw) -> None:
    await db.execute(update(Listing).where(Listing.id == lid).values(**kw))
    await db.commit()

async def delete_listing(db: AsyncSession, lid: int) -> None:
    await db.execute(delete(Listing).where(Listing.id == lid))
    await db.commit()

async def list_listings(db: AsyncSession, owner_id: int | None = None,
                        status: ListingStatus | None = None,
                        offset: int = 0, limit: int = 20) -> list[Listing]:
    q = select(Listing).options(selectinload(Listing.images))
    if owner_id: q = q.where(Listing.owner_id == owner_id)
    if status:   q = q.where(Listing.status == status)
    r = await db.execute(q.order_by(Listing.created_at.desc()).offset(offset).limit(limit))
    return list(r.scalars().all())

async def search_listings(db: AsyncSession, **f) -> list[Listing]:
    q = select(Listing).options(selectinload(Listing.images), selectinload(Listing.owner))
    if f.get("listing_type"):  q = q.where(Listing.listing_type  == f["listing_type"])
    if f.get("property_type"): q = q.where(Listing.property_type == f["property_type"])
    if f.get("province"):      q = q.where(Listing.province.ilike(f"%{f['province']}%"))
    if f.get("city"):          q = q.where(Listing.city.ilike(f"%{f['city']}%"))
    if f.get("min_area"):      q = q.where(Listing.area  >= f["min_area"])
    if f.get("max_area"):      q = q.where(Listing.area  <= f["max_area"])
    if f.get("min_price"):     q = q.where(Listing.price >= f["min_price"])
    if f.get("max_price"):     q = q.where(Listing.price <= f["max_price"])
    if f.get("bedrooms"):      q = q.where(Listing.bedrooms == f["bedrooms"])
    q = q.where(Listing.status == ListingStatus.APPROVED).order_by(Listing.created_at.desc()).limit(30)
    r = await db.execute(q)
    return list(r.scalars().all())

async def add_listing_image(db: AsyncSession, lid: int, file_id: str, order: int = 0) -> None:
    db.add(ListingImage(listing_id=lid, file_id=file_id, order=order))
    await db.commit()

async def count_listing_images(db: AsyncSession, lid: int) -> int:
    r = await db.execute(select(func.count()).select_from(ListingImage).where(ListingImage.listing_id == lid))
    return r.scalar_one()


# ── Consultant ────────────────────────────────────────────────
async def list_consultants(db: AsyncSession) -> list[Consultant]:
    r = await db.execute(select(Consultant).where(Consultant.is_active == True))
    return list(r.scalars().all())

async def get_consultant(db: AsyncSession, cid: int) -> Consultant | None:
    r = await db.execute(select(Consultant).where(Consultant.id == cid))
    return r.scalar_one_or_none()

async def create_consultant(db: AsyncSession, **kw) -> Consultant:
    c = Consultant(**kw); db.add(c); await db.commit(); await db.refresh(c)
    return c

async def update_consultant(db: AsyncSession, cid: int, **kw) -> None:
    await db.execute(update(Consultant).where(Consultant.id == cid).values(**kw))
    await db.commit()

async def delete_consultant(db: AsyncSession, cid: int) -> None:
    await db.execute(delete(Consultant).where(Consultant.id == cid))
    await db.commit()


# ── Setting ───────────────────────────────────────────────────
async def get_setting(db: AsyncSession, key: str, default: str = "") -> str:
    r = await db.execute(select(Setting).where(Setting.key == key))
    s = r.scalar_one_or_none()
    return s.value if s else default

async def set_setting(db: AsyncSession, key: str, value: str) -> None:
    r = await db.execute(select(Setting).where(Setting.key == key))
    s = r.scalar_one_or_none()
    if s: s.value = value
    else: db.add(Setting(key=key, value=value))
    await db.commit()


# ── AdminPerm ─────────────────────────────────────────────────
async def get_perms(db: AsyncSession, tid: int) -> list[str]:
    r = await db.execute(select(AdminPerm.perm).where(AdminPerm.user_id == tid))
    return [row[0] for row in r.all()]

async def set_perms(db: AsyncSession, tid: int, perms: list[str]) -> None:
    await db.execute(delete(AdminPerm).where(AdminPerm.user_id == tid))
    for p in perms: db.add(AdminPerm(user_id=tid, perm=p))
    await db.commit()
