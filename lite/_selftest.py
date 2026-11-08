"""Fast offline checks — no network, no Ollama."""
from __future__ import annotations

from lite import router, settings
from lite.session import Session
from lite.tools import registry


def test_router_local_default() -> None:
    s = dict(settings.DEFAULTS)
    s["cloud_enabled"] = False
    r = router.choose_route(s, {})
    assert r.backend == "ollama"
    assert "local" in r.reason


def test_router_cloud_manual() -> None:
    s = dict(settings.DEFAULTS)
    s["cloud_enabled"] = True
    s["cloud_provider"] = "openai"
    r = router.choose_route(s, {"OPENAI_API_KEY": "sk-test"})
    assert r.backend == "openai"
    assert r.model == s["cloud_model"]


def test_router_mistral_manual() -> None:
    s = dict(settings.DEFAULTS)
    s["cloud_enabled"] = True
    s["cloud_provider"] = "mistral"
    r = router.choose_route(s, {"MISTRAL_API_KEY": "ms-test"})
    assert r.backend == "mistral"
    assert "mistral" in r.model


def test_router_cloud_without_key_stays_local() -> None:
    s = dict(settings.DEFAULTS)
    s["cloud_enabled"] = True
    r = router.choose_route(s, {})
    assert r.backend == "ollama"


def test_slash_time() -> None:
    out = registry.try_slash("/time")
    assert out and "20" in out  # year prefix 20xx


def test_session_slash_no_network() -> None:
    sess = Session()
    reply = sess.ask("/sys")
    assert "python=" in reply
    assert sess.last_meta.get("backend") == "local"


def test_truncate() -> None:
    t = settings.truncate_text("abcdefghij", 8)
    assert t.endswith("…[truncated]")
    assert len(t) <= 8 + 5  # allow marker


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"OK {name}")
    print("all passed")
