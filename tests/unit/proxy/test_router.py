from kimi_proxy.proxy.router import get_provider_host_header


def test_get_provider_host_header_returns_netloc() -> None:
    assert get_provider_host_header("https://api.openai.com/v1") == "api.openai.com"


def test_get_provider_host_header_handles_invalid_url() -> None:
    assert get_provider_host_header("") is None
