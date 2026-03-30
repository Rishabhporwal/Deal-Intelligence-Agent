from __future__ import annotations

from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class CreditStatus(str, Enum):
    APPROVED = "approved"
    FLAGGED = "flagged"
    REJECTED = "rejected"


class CreditCheckResult(BaseModel):
    counterparty: str
    volume: float
    status: CreditStatus
    message: str


class ExtractedDeal(BaseModel):
    """Fields extracted from the deal confirmation memo by the LLM."""

    reference: Optional[str] = Field(None, description="Deal reference number")
    date: Optional[str] = Field(None, description="Deal date (YYYY-MM-DD)")
    seller: Optional[str] = Field(None, description="Full legal name of the seller")
    buyer: Optional[str] = Field(None, description="Full legal name of the buyer")
    commodity: Optional[str] = Field(None, description="Commodity being traded")
    volume_mmbtu: Optional[float] = Field(None, description="Volume in MMBtu")
    delivery_start: Optional[str] = Field(None, description="Delivery start (YYYY-MM-DD)")
    delivery_end: Optional[str] = Field(None, description="Delivery end (YYYY-MM-DD)")
    delivery_point: Optional[str] = Field(None, description="Delivery point")
    price_usd_per_mmbtu: Optional[float] = Field(None, description="Price in USD/MMBtu")
    total_value_usd: Optional[float] = Field(None, description="volume × price")
    payment_terms: Optional[str] = Field(None, description="Payment terms as stated")
    governing_law: Optional[str] = Field(None, description="Governing law jurisdiction")
    confirmed_by: Optional[str] = Field(None, description="Name + affiliation of confirming party")
    validation_flags: list[str] = Field(
        default_factory=list,
        description="Issues found during extraction",
    )


class DealResponse(BaseModel):
    """Final output — extracted data + validation flags + credit check result."""

    reference: Optional[str] = None
    date: Optional[str] = None
    seller: Optional[str] = None
    buyer: Optional[str] = None
    commodity: Optional[str] = None
    volume_mmbtu: Optional[float] = None
    delivery_start: Optional[str] = None
    delivery_end: Optional[str] = None
    delivery_point: Optional[str] = None
    price_usd_per_mmbtu: Optional[float] = None
    total_value_usd: Optional[float] = None
    payment_terms: Optional[str] = None
    governing_law: Optional[str] = None
    confirmed_by: Optional[str] = None
    validation_flags: list[str] = Field(default_factory=list)
    credit_check: Optional[CreditCheckResult] = None

    @classmethod
    def from_extracted_deal(
        cls,
        deal: ExtractedDeal,
        credit_check: CreditCheckResult,
        extra_flags: list[str] | None = None,
    ) -> "DealResponse":
        # Merge flags from LLM extraction + deterministic validation, dedup preserving order
        all_flags = list(deal.validation_flags)
        if extra_flags:
            all_flags.extend(extra_flags)

        seen: set[str] = set()
        unique_flags: list[str] = []
        for flag in all_flags:
            key = flag.lower().strip()
            if key not in seen:
                seen.add(key)
                unique_flags.append(flag)

        return cls(
            reference=deal.reference,
            date=deal.date,
            seller=deal.seller,
            buyer=deal.buyer,
            commodity=deal.commodity,
            volume_mmbtu=deal.volume_mmbtu,
            delivery_start=deal.delivery_start,
            delivery_end=deal.delivery_end,
            delivery_point=deal.delivery_point,
            price_usd_per_mmbtu=deal.price_usd_per_mmbtu,
            total_value_usd=deal.total_value_usd,
            payment_terms=deal.payment_terms,
            governing_law=deal.governing_law,
            confirmed_by=deal.confirmed_by,
            validation_flags=unique_flags,
            credit_check=credit_check,
        )