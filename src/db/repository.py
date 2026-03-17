from __future__ import annotations

import bcrypt

from src.db.database import get_connection
from src.db.models import User


class UserRepository:
    """Data-access layer for the users table. Pure sqlite3 — no ORM."""

    def create_user(self, username: str, password: str) -> User:
        """Insert a new user with a bcrypt-hashed password.

        Raises sqlite3.IntegrityError if the username already exists.
        """
        password_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
        with get_connection() as conn:
            cursor = conn.execute(
                "INSERT INTO users (username, password_hash) VALUES (?, ?)",
                (username, password_hash),
            )
            conn.commit()
            row = conn.execute(
                "SELECT id, username, password_hash, created_at FROM users WHERE id = ?",
                (cursor.lastrowid,),
            ).fetchone()
        return User(**dict(row))

    def get_by_username(self, username: str) -> User | None:
        """Return a User by username, or None if not found."""
        with get_connection() as conn:
            row = conn.execute(
                "SELECT id, username, password_hash, created_at FROM users WHERE username = ?",
                (username,),
            ).fetchone()
        return User(**dict(row)) if row else None

    def verify_password(self, plain_password: str, hashed_password: str) -> bool:
        """Check a plaintext password against its bcrypt hash."""
        return bcrypt.checkpw(plain_password.encode(), hashed_password.encode())
