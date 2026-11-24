"""Which catalog businesses Sabi shows to customers.

Rule (docs/VISIBLE_RESTAURANTS.md, decided 2026-11-23): only real, verified businesses are
visible. Demo/test businesses stay in the database (owner panel keeps working, nothing is
deleted) but Sabi must not recommend them, route to them by mention or product, offer them in
city delivery options, or serve their public storefront.
"""
from sqlalchemy import select

from .models import Restaurant

# Hidden by explicit decision, in addition to the standing "Prueba ..." name convention.
HIDDEN_SLUGS = frozenset({
    "la-esquina",            # fictional MVP demo restaurant
    "prueba-onboarding-final",
    "prueba-flow-final",
})


def is_hidden(restaurant: Restaurant) -> bool:
    name = (restaurant.name or "").strip().lower()
    return restaurant.slug in HIDDEN_SLUGS or name.startswith("prueba")


def public_condition():
    """SQLAlchemy WHERE clause limiting a Restaurant query to customer-visible businesses."""
    return (~Restaurant.name.ilike("prueba%")) & (Restaurant.slug.notin_(sorted(HIDDEN_SLUGS)))
