import pytest

from scripts import probe_image_providers


class _FakeAdapter:
    async def generate(self, image_b64: str, prompt: str) -> list[bytes]:
        assert image_b64 == probe_image_providers.ONE_BY_ONE_JPEG_B64
        assert prompt == probe_image_providers.PROMPT
        return [b"one", b"two", b"three"]


class _FailingAdapter:
    async def generate(self, image_b64: str, prompt: str) -> list[bytes]:
        raise RuntimeError("quota failed")


class _FakeProvider:
    name = "FakeImage"

    def __init__(self, adapter):
        self._adapter = adapter

    def make_adapter(self):
        return self._adapter


@pytest.mark.asyncio
async def test_probe_provider_reports_real_generation_success():
    name, status, detail = await probe_image_providers._probe_provider(
        _FakeProvider(_FakeAdapter())
    )

    assert name == "FakeImage"
    assert status == "success"
    assert detail == "3 image(s); byte lengths: 3, 3, 5"


@pytest.mark.asyncio
async def test_probe_provider_reports_generation_failure():
    name, status, detail = await probe_image_providers._probe_provider(
        _FakeProvider(_FailingAdapter())
    )

    assert name == "FakeImage"
    assert status == "failure"
    assert detail == "RuntimeError: quota failed"
