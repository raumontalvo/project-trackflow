"""Authorization checks for TrackFlow shipment and tracking access."""

from __future__ import annotations

from dataclasses import dataclass

from sqlmodel import Session, select

from services.api.database import engine
from services.api.models import StockExit


@dataclass(frozen=True)
class TrackingAuthorizationResult:
    """Result of checking access to a TrackFlow tracking number."""

    found: bool
    authorized: bool
    tracking_number: str
    shipment_country: str | None = None
    reason: str | None = None


def country_from_warehouse(warehouse: str | None) -> str | None:
    """Map TrackFlow warehouse codes to their operational country."""
    if warehouse == "LA":
        return "USA"

    if warehouse == "ZGZ":
        return "Spain"

    return None


def authorize_tracking_number(
    tracking_number: str,
    authenticated_user_uuid: str,
) -> TrackingAuthorizationResult:
    """Verify that a tracking number belongs to the authenticated user."""
    normalized_tracking = tracking_number.strip()

    with Session(engine) as session:
        statement = select(StockExit).where(
            StockExit.tracking_number == normalized_tracking
        )

        shipment = session.exec(statement).first()

    if shipment is None:
        return TrackingAuthorizationResult(
            found=False,
            authorized=False,
            tracking_number=normalized_tracking,
            reason="tracking_not_found",
        )

    shipment_country = country_from_warehouse(shipment.warehouse)

    if str(shipment.user_uuid) != str(authenticated_user_uuid):
        return TrackingAuthorizationResult(
            found=True,
            authorized=False,
            tracking_number=normalized_tracking,
            shipment_country=shipment_country,
            reason="tracking_not_owned_by_authenticated_user",
        )

    return TrackingAuthorizationResult(
        found=True,
        authorized=True,
        tracking_number=normalized_tracking,
        shipment_country=shipment_country,
    )