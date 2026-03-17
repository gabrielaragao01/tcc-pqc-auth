from __future__ import annotations

from pydantic import BaseModel, Field


class User(BaseModel):
    """Serialization model for the users SQLite table."""

    model_config = {"frozen": True}

    id: int | None = Field(default=None, description="Auto-incremented row ID.")
    username: str = Field(description="Unique username.")
    password_hash: str = Field(description="Bcrypt hash of the user's password.")
    created_at: str | None = Field(default=None, description="ISO timestamp of creation.")
