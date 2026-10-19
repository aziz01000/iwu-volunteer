import os
import tempfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient


@pytest.fixture()
def client(tmp_path):
    db_file = tmp_path / "test.db"
    os.environ["DATABASE_PATH"] = str(db_file)
    os.environ.pop("OPENAI_API_KEY", None)
    os.environ.pop("AI_API_KEY", None)

    from app.seed import seed_if_empty

    seed_if_empty()
    from app.main import app

    with TestClient(app) as test_client:
        yield test_client


def login(client, email, password="demo1234"):
    res = client.post("/api/auth/login", json={"email": email, "password": password})
    assert res.status_code == 200, res.text
    token = res.json()["token"]
    return {"Authorization": f"Bearer {token}"}
