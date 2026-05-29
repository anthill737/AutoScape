import httpx

from app.domain import url_validator
from app.domain.url_validator import validate_material_item_url


def _response(status_code: int, html: str = "<title>Pressure Treated Lumber</title>") -> httpx.Response:
    request = httpx.Request("GET", "https://www.homedepot.com/p/product/123")
    return httpx.Response(status_code=status_code, text=html, request=request)


def test_search_or_category_path_is_rejected_without_fetch(monkeypatch):
    def fail_if_called(*args, **kwargs):
        raise AssertionError("network should not be called for search/category URLs")

    monkeypatch.setattr(url_validator.httpx, "get", fail_if_called)

    passed, reason = validate_material_item_url(
        "Pressure treated lumber",
        "https://www.homedepot.com/s/pressure%20treated%20lumber",
    )

    assert passed is False
    assert "search/category" in reason


def test_title_mismatch_is_rejected(monkeypatch):
    monkeypatch.setattr(
        url_validator.httpx,
        "get",
        lambda *args, **kwargs: _response(200, "<title>Outdoor patio umbrella</title>"),
    )

    passed, reason = validate_material_item_url(
        "Pressure treated lumber",
        "https://www.homedepot.com/p/product/123",
    )

    assert passed is False
    assert "title mismatch" in reason.lower()


def test_non_200_status_is_rejected_with_status_code(monkeypatch):
    monkeypatch.setattr(url_validator.httpx, "get", lambda *args, **kwargs: _response(404))

    passed, reason = validate_material_item_url(
        "Pressure treated lumber",
        "https://www.homedepot.com/p/product/123",
    )

    assert passed is False
    assert "404" in reason


def test_matching_product_title_passes_validation(monkeypatch):
    monkeypatch.setattr(
        url_validator.httpx,
        "get",
        lambda *args, **kwargs: _response(
            200,
            "<html><head><title>2x4 Pressure-Treated Ground Contact Lumber</title></head></html>",
        ),
    )

    passed, reason = validate_material_item_url(
        "2x4 pressure treated board",
        "https://www.homedepot.com/p/product/123",
    )

    assert passed is True
    assert "passed" in reason


def test_timeout_is_returned_as_validation_failure(monkeypatch):
    def raise_timeout(*args, **kwargs):
        raise httpx.TimeoutException("timed out")

    monkeypatch.setattr(url_validator.httpx, "get", raise_timeout)

    passed, reason = validate_material_item_url(
        "Pressure treated lumber",
        "https://www.homedepot.com/p/product/123",
    )

    assert passed is False
    assert "timeout" in reason.lower() or "timed out" in reason.lower()


def test_fetch_uses_required_timeout_and_redirect_settings(monkeypatch):
    observed = {}

    def capture_get(url, **kwargs):
        observed["url"] = url
        observed.update(kwargs)
        return _response(200)

    monkeypatch.setattr(url_validator.httpx, "get", capture_get)

    validate_material_item_url(
        "Pressure treated lumber",
        "https://www.homedepot.com/p/product/123",
    )

    assert observed["timeout"] == 5.0
    assert observed["follow_redirects"] is True
