from datetime import datetime, timezone

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.deps import get_current_user
from app.api.routes.product_images import router as product_images_router
from app.schemas.product_image import ProductImageMetadata
from app.schemas.user import UserInDB, UserRole


def _build_app_with_user(user: UserInDB) -> TestClient:
    app = FastAPI()
    app.include_router(product_images_router)

    async def _override_current_user() -> UserInDB:
        return user

    app.dependency_overrides[get_current_user] = _override_current_user
    return TestClient(app)


def _make_user(*, user_id: str, role: UserRole) -> UserInDB:
    return UserInDB(
        _id=user_id,
        email=f"{user_id}@test.com",
        full_name="Test User",
        role=role,
        is_active=True,
        password_hash="hash",
        provider="local",
        google_sub=None,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )


class _FakeCloudinaryService:
    def __init__(self) -> None:
        self.deleted: list[str] = []

    async def upload_product_image(self, *, product_id: str, filename: str, file_bytes: bytes) -> ProductImageMetadata:
        return ProductImageMetadata(
            url=f"http://cdn/{product_id}/{filename}",
            secure_url=f"https://cdn/{product_id}/{filename}",
            public_id=f"colficultor/products/{product_id}/{filename}",
            asset_id="asset-1",
            format="jpg",
            width=640,
            height=480,
            bytes=len(file_bytes),
        )

    async def delete_image(self, public_id: str) -> None:
        self.deleted.append(public_id)


def test_upload_images_success(monkeypatch):
    from app.services import product_images_service as service

    user = _make_user(user_id="owner-1", role=UserRole.CAFICULTOR)
    client = _build_app_with_user(user)
    fake_cloudinary = _FakeCloudinaryService()

    persisted = {}

    async def _fake_get_producto_by_id(product_id: str):
        return {
            "_id": product_id,
            "caficultor_id": "owner-1",
            "imagenes": [],
            "urls_imagenes": [],
        }

    async def _fake_append_producto_imagenes(*, producto_id: str, nuevas_imagenes: list[dict]):
        persisted["producto_id"] = producto_id
        persisted["imagenes"] = nuevas_imagenes
        return {
            "_id": producto_id,
            "imagenes": nuevas_imagenes,
            "urls_imagenes": [img["secure_url"] for img in nuevas_imagenes],
        }

    monkeypatch.setattr(service, "get_producto_by_id", _fake_get_producto_by_id)
    monkeypatch.setattr(service, "append_producto_imagenes", _fake_append_producto_imagenes)
    monkeypatch.setattr(service, "get_cloudinary_service", lambda: fake_cloudinary)

    response = client.post(
        "/api/products/p1/images",
        files=[("files", ("cafe.jpg", b"image-binary", "image/jpeg"))],
    )

    assert response.status_code == 201
    body = response.json()
    assert body["product_id"] == "p1"
    assert len(body["images"]) == 1
    assert persisted["producto_id"] == "p1"
    assert persisted["imagenes"][0]["asset_id"] == "asset-1"


def test_upload_images_invalid_file(monkeypatch):
    from app.services import product_images_service as service

    user = _make_user(user_id="owner-1", role=UserRole.CAFICULTOR)
    client = _build_app_with_user(user)

    async def _fake_get_producto_by_id(product_id: str):
        return {
            "_id": product_id,
            "caficultor_id": "owner-1",
            "imagenes": [],
            "urls_imagenes": [],
        }

    monkeypatch.setattr(service, "get_producto_by_id", _fake_get_producto_by_id)

    response = client.post(
        "/api/products/p1/images",
        files=[("files", ("not-image.txt", b"hello", "text/plain"))],
    )

    assert response.status_code == 422
    assert "Tipo de archivo no permitido" in response.json()["detail"]


def test_upload_images_forbidden_user(monkeypatch):
    from app.services import product_images_service as service

    user = _make_user(user_id="buyer-1", role=UserRole.COMPRADOR)
    client = _build_app_with_user(user)

    async def _fake_get_producto_by_id(product_id: str):
        return {
            "_id": product_id,
            "caficultor_id": "owner-1",
            "imagenes": [],
            "urls_imagenes": [],
        }

    monkeypatch.setattr(service, "get_producto_by_id", _fake_get_producto_by_id)

    response = client.post(
        "/api/products/p1/images",
        files=[("files", ("cafe.jpg", b"image-binary", "image/jpeg"))],
    )

    assert response.status_code == 403
    assert "No tienes permiso" in response.json()["detail"]


def test_delete_image_success(monkeypatch):
    from app.services import product_images_service as service

    user = _make_user(user_id="owner-1", role=UserRole.CAFICULTOR)
    client = _build_app_with_user(user)
    fake_cloudinary = _FakeCloudinaryService()

    existing_image = {
        "url": "http://cdn/p1/cafe.jpg",
        "secure_url": "https://cdn/p1/cafe.jpg",
        "public_id": "colficultor/products/p1/cafe",
        "asset_id": "asset-1",
        "format": "jpg",
        "width": 640,
        "height": 480,
        "bytes": 1234,
    }

    async def _fake_get_producto_by_id(product_id: str):
        return {
            "_id": product_id,
            "caficultor_id": "owner-1",
            "imagenes": [existing_image],
            "urls_imagenes": [existing_image["secure_url"]],
        }

    async def _fake_remove_producto_imagen_por_id(*, producto_id: str, image_id: str):
        return {
            "_id": producto_id,
            "imagenes": [],
            "urls_imagenes": [],
        }, existing_image

    monkeypatch.setattr(service, "get_producto_by_id", _fake_get_producto_by_id)
    monkeypatch.setattr(service, "remove_producto_imagen_por_id", _fake_remove_producto_imagen_por_id)
    monkeypatch.setattr(service, "get_cloudinary_service", lambda: fake_cloudinary)

    response = client.delete("/api/products/p1/images/asset-1")

    assert response.status_code == 200
    body = response.json()
    assert body["message"] == "Imagen eliminada correctamente"
    assert body["image"]["asset_id"] == "asset-1"
    assert fake_cloudinary.deleted == ["colficultor/products/p1/cafe"]
