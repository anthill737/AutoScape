from fastapi.testclient import TestClient

from app.domain.retailers import APPROVED_RETAILERS
from app.main import app


def test_approved_retailers_constant_contains_canonical_entries():
    assert len(APPROVED_RETAILERS) == 5
    assert all(set(retailer) == {"name", "domain"} for retailer in APPROVED_RETAILERS)
    assert all(retailer["domain"].count(".") == 1 for retailer in APPROVED_RETAILERS)
    assert len({retailer["name"] for retailer in APPROVED_RETAILERS}) == 5
    assert len({retailer["domain"] for retailer in APPROVED_RETAILERS}) == 5


def test_approved_retailers_endpoint_returns_constant():
    client = TestClient(app)

    response = client.get("/api/approved-retailers")

    assert response.status_code == 200
    assert response.json() == [dict(retailer) for retailer in APPROVED_RETAILERS]
