import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from forge.api import uploads as uploads_api
from forge.uploads import UploadService


@pytest.fixture
def upload_dir(tmp_path):
    return tmp_path / "uploads"


@pytest.fixture
def service(upload_dir):
    return UploadService(upload_dir)


@pytest.fixture
async def client(service):
    app = FastAPI()
    uploads_api.set_service(service)
    app.include_router(uploads_api.router)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c


async def test_upload_returns_path_and_filename(client):
    resp = await client.post(
        "/api/uploads",
        files={"file": ("screenshot.png", b"\x89PNG", "image/png")},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "path" in data
    assert "filename" in data
    assert data["filename"].endswith(".png")
    assert "screenshot-" in data["filename"]


async def test_upload_stores_file_content(client, upload_dir):
    content = b"\x89PNG\r\ntest content"
    await client.post(
        "/api/uploads",
        files={"file": ("image.png", content, "image/png")},
    )
    files = list(upload_dir.iterdir())
    assert len(files) == 1
    assert files[0].read_bytes() == content


async def test_get_latest_returns_404_when_no_uploads(client):
    resp = await client.get("/api/uploads/latest")
    assert resp.status_code == 404


async def test_get_latest_returns_most_recent(client):
    await client.post("/api/uploads", files={"file": ("a.png", b"first", "image/png")})
    import time

    time.sleep(0.05)
    await client.post("/api/uploads", files={"file": ("b.png", b"second", "image/png")})

    resp = await client.get("/api/uploads/latest")
    assert resp.status_code == 200
    data = resp.json()
    assert "path" in data
    assert "b-" in data["filename"]  # most recent file starts with "b"
