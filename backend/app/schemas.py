from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class LoginIn(BaseModel):
    slug: str
    pin: str


class MenuItemIn(BaseModel):
    name: str
    price: float
    category: str = "General"
    available: bool = True
    description: str = ""


class MenuItemOut(MenuItemIn):
    id: int

    class Config:
        from_attributes = True


class RestaurantSettingsIn(BaseModel):
    welcome_message: Optional[str] = None
    opening_hours: Optional[str] = None
    owner_phone: Optional[str] = None
    name: Optional[str] = None


class RestaurantOut(BaseModel):
    id: int
    name: str
    slug: str
    welcome_message: str
    opening_hours: str
    owner_phone: str
    currency: str

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
    order_type: str
    address: str
    notes: str
    total: float
    rejection_reason: str
    edit_summary: str
    created_at: datetime
    decided_at: Optional[datetime] = None
    customer_phone: str = ""
    customer_name: str = ""
    items: list[OrderItemOut] = []


class OrderEditIn(BaseModel):
    order_type: Optional[str] = None
    address: Optional[str] = None
    notes: Optional[str] = None
    edit_summary: str = ""
    items: Optional[list[OrderItemIn]] = None  # full replacement


class RejectIn(BaseModel):
    reason: str = ""


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
