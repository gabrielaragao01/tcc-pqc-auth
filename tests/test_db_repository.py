from __future__ import annotations

import sqlite3

import pytest

from src.db.repository import UserRepository


@pytest.fixture
def repo(memory_db) -> UserRepository:  # memory_db from conftest.py
    return UserRepository()


def test_create_user_returns_user_with_id(repo):
    user = repo.create_user("alice", "password123")
    assert user.username == "alice"
    assert user.id is not None


def test_get_by_username_found(repo):
    repo.create_user("bob", "pass")
    user = repo.get_by_username("bob")
    assert user is not None
    assert user.username == "bob"


def test_get_by_username_not_found(repo):
    result = repo.get_by_username("nonexistent")
    assert result is None


def test_verify_password_correct(repo):
    repo.create_user("carol", "secret")
    user = repo.get_by_username("carol")
    assert repo.verify_password("secret", user.password_hash) is True


def test_verify_password_wrong(repo):
    repo.create_user("dave", "correct")
    user = repo.get_by_username("dave")
    assert repo.verify_password("wrong", user.password_hash) is False


def test_create_duplicate_username_raises(repo):
    repo.create_user("eve", "pass")
    with pytest.raises(sqlite3.IntegrityError):
        repo.create_user("eve", "other")
