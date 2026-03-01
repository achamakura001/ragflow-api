"""
Pydantic schemas for the Item domain.
Separating ORM models from API schemas keeps the boundary clean
and makes cloud migrations / DB swaps straightforward.
"""

import datetime

from pydantic import BaseModel, ConfigDict, Field


class ItemBase(BaseModel):
    title: str = Field(..., min_length=1, max_length=255, examples=["My first item"])
    description: str | None = Field(None, examples=["A detailed description"])
    is_active: bool = Field(True)


class ItemCreate(ItemBase):
    """Schema for POST /items"""
    pass


class ItemUpdate(BaseModel):
    """Schema for PATCH /items/{id} – all fields optional."""
    title: str | None = Field(None, min_length=1, max_length=255)
    description: str | None = None
    is_active: bool | None = None


class ItemRead(ItemBase):
    """Schema returned to the client."""
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime.datetime
    updated_at: datetime.datetime


class ItemList(BaseModel):
    """Paginated list wrapper."""
    total: int
    items: list[ItemRead]
