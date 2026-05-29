import pytest

from scripts import probe_materials_llms


class _FakeProvider:
    def __init__(self, name: str):
        self.name = name


async def _ok_probe():
    return None


async def _failing_probe():
    raise RuntimeError("provider failed")


@pytest.mark.asyncio
async def test_probe_materials_llms_prints_ok_and_continues_on_failure(monkeypatch, capsys):
    monkeypatch.setattr(
        probe_materials_llms,
        "PROVIDERS",
        (
            claude := _FakeProvider("ClaudeSonnet"),
            gpt := _FakeProvider("Gpt5"),
            gemini := _FakeProvider("GeminiPro"),
        ),
    )
    monkeypatch.setattr(
        probe_materials_llms,
        "PROBE_FUNCTIONS",
        {
            claude: _ok_probe,
            gpt: _failing_probe,
            gemini: _ok_probe,
        },
    )

    assert await probe_materials_llms.main() == 0

    assert capsys.readouterr().out.splitlines() == [
        "ClaudeSonnet: OK",
        "Gpt5: provider failed",
        "GeminiPro: OK",
    ]
