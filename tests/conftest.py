from collections.abc import Iterator
from pathlib import Path
import sys

import pytest
from fastapi.testclient import TestClient

API_SRC = Path(__file__).resolve().parents[1] / "services" / "api" / "src"
sys.path.insert(0, str(API_SRC))

from app.main import create_app  # noqa: E402
from core.config import get_settings  # noqa: E402


@pytest.fixture(autouse=True)
def clear_settings_cache() -> Iterator[None]:
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture
def client() -> TestClient:
    return TestClient(create_app())
