"""Shared public product knowledge; seller ownership stays in tenant-scoped links."""

from datetime import datetime
from typing import Any

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from persistence.models import JSON_DOCUMENT, Base, TenantOwned, Timestamped


class MarketplaceProduct(Base, Timestamped):
    __tablename__ = "marketplace_products"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    identity_key: Mapped[str] = mapped_column(String(80), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    website: Mapped[str] = mapped_column(String(1000), nullable=False)
    edition: Mapped[str] = mapped_column(String(200), nullable=False)
    search_text: Mapped[str] = mapped_column(Text, nullable=False)


class MarketplaceObservation(Base):
    __tablename__ = "marketplace_observations"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    product_id: Mapped[str] = mapped_column(ForeignKey("marketplace_products.id"), nullable=False)
    origin: Mapped[str] = mapped_column(String(24), nullable=False)
    source_key: Mapped[str] = mapped_column(String(160), nullable=False)
    content_hash: Mapped[str] = mapped_column(String(80), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON_DOCUMENT, nullable=False)
    source_refs: Mapped[list[dict[str, Any]]] = mapped_column(JSON_DOCUMENT, nullable=False)
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    withdrawn_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    __table_args__ = (
        UniqueConstraint(
            "product_id", "origin", "source_key", "content_hash", name="uq_marketplace_observation"
        ),
        Index("ix_marketplace_observation_current", "product_id", "active", "observed_at"),
    )


class MarketplaceSellerLink(Base, TenantOwned):
    __tablename__ = "marketplace_seller_links"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    seller_product_id: Mapped[str] = mapped_column(ForeignKey("seller_products.id"), nullable=False)
    website: Mapped[str] = mapped_column(String(1000), nullable=False)
    edition: Mapped[str] = mapped_column(String(200), nullable=False)
    seller_name: Mapped[str] = mapped_column(String(200), nullable=False)
    __table_args__ = (
        UniqueConstraint("organization_id", "seller_product_id", name="uq_marketplace_seller_link"),
    )
