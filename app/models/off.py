from sqlalchemy import Float, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class OffProduct(Base):
    """Cached Open Food Facts products (populated on-demand via REST API)."""

    __tablename__ = "off_product"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    barcode: Mapped[str | None] = mapped_column(String(32), unique=True, index=True)
    product_name: Mapped[str | None] = mapped_column(Text, index=True)
    brands: Mapped[str | None] = mapped_column(Text)
    categories: Mapped[str | None] = mapped_column(Text)
    allergens: Mapped[str | None] = mapped_column(Text, index=True)
    traces: Mapped[str | None] = mapped_column(Text)
    nutriscore_grade: Mapped[str | None] = mapped_column(String(2), index=True)
    nova_group: Mapped[int | None] = mapped_column(Integer)

    energy_kcal_100g: Mapped[float | None] = mapped_column(Float)
    protein_100g: Mapped[float | None] = mapped_column(Float)
    fat_100g: Mapped[float | None] = mapped_column(Float)
    saturated_fat_100g: Mapped[float | None] = mapped_column(Float)
    carbohydrate_100g: Mapped[float | None] = mapped_column(Float)
    sugar_100g: Mapped[float | None] = mapped_column(Float)
    fiber_100g: Mapped[float | None] = mapped_column(Float)
    sodium_100g: Mapped[float | None] = mapped_column(Float)
    fetched_at: Mapped[str | None] = mapped_column(String(32))
