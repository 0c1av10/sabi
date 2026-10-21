from datetime import datetime
from typing import Optional

from pydantic import BaseModel, field_validator


class LoginIn(BaseModel):
    slug: str
    pin: str


class MenuItemIn(BaseModel):
    name: str
    price: float
    category: str = "General"
    available: bool = True
    description: str = ""
    image_url: str = ""


class MenuItemOut(MenuItemIn):
    id: int

    class Config:
        from_attributes = True


class DeliveryZone(BaseModel):
    name: str
    fee: float


class RestaurantSettingsIn(BaseModel):
    welcome_message: Optional[str] = None
    opening_hours: Optional[str] = None
    owner_phone: Optional[str] = None
    name: Optional[str] = None
    exchange_rate: Optional[float] = None
    eur_rate: Optional[float] = None
    bcv_auto: Optional[bool] = None
    email: Optional[str] = None
    website: Optional[str] = None
    tagline: Optional[str] = None
    logo_url: Optional[str] = None
    brand_color: Optional[str] = None
    delivery_fee: Optional[float] = None
    delivery_info: Optional[str] = None
    clear_delivery_fee: Optional[bool] = None  # true = fee unknown again
    delivery_zones: Optional[list[DeliveryZone]] = None  # replaces the list; [] removes zones


class RestaurantOut(BaseModel):
    id: int
    name: str
    slug: str
    welcome_message: str
    opening_hours: str
    owner_phone: str
    currency: str
    exchange_rate: float
    eur_rate: float
    bcv_auto: Optional[bool] = None
    rates_date: Optional[str] = None
    rates_updated_at: Optional[datetime] = None
    email: Optional[str] = None
    website: Optional[str] = None
    tagline: Optional[str] = None
    logo_url: Optional[str] = None
    brand_color: Optional[str] = None
    delivery_fee: Optional[float] = None
    delivery_info: Optional[str] = None
    delivery_zones: list[DeliveryZone] = []

    @field_validator("delivery_zones", mode="before")
    @classmethod
    def _zones(cls, v):
        from .delivery import load_zones
        return load_zones(v) if isinstance(v, str) or v is None else v

    class Config:
        from_attributes = True


class OrderItemIn(BaseModel):
    name: str
    quantity: int = 1
    unit_price: float = 0.0
    extras: str = ""
    notes: str = ""


class OrderItemOut(OrderItemIn):
    id: int
    menu_item_id: Optional[int] = None

    class Config:
        from_attributes = True


class OrderOut(BaseModel):
    id: int
    status: str
    payment_status: str = "pending"
    payment_method: str = ""
    payment_reference: str = ""
    order_type: str
    address: str
    notes: str
    total: float
    delivery_fee: Optional[float] = 0.0
    delivery_zone: Optional[str] = ""
    rejection_reason: str
    edit_summary: str
    created_at: datetime
    decided_at: Optional[datetime] = None
    customer_phone: str = ""
    customer_name: str = ""
    source: str = "whatsapp"
    items: list[OrderItemOut] = []


class OrderEditIn(BaseModel):
    order_type: Optional[str] = None
    address: Optional[str] = None
    notes: Optional[str] = None
    edit_summary: str = ""
    items: Optional[list[OrderItemIn]] = None  # full replacement


class RejectIn(BaseModel):
    reason: str = ""


class PaymentConfirmIn(BaseModel):
    payment_reference: Optional[str] = None


class MessageOut(BaseModel):
    id: int
    direction: str
    body: str
    created_at: datetime

    class Config:
        from_attributes = True


class ConversationOut(BaseModel):
    id: int
    status: str
    customer_phone: str = ""
    customer_name: str = ""
    created_at: datetime
    updated_at: datetime
    messages: list[MessageOut] = []
