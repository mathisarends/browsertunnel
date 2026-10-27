from pathlib import Path

from fastapi_rpckit.codegen import TypeScriptClientOptions, generate_typescript_client

from browsertunnel.features.browser.presentation.schemas import (
    browser_openrpc_schema,
)


def test_generated_browser_client_is_reproducible(tmp_path: Path) -> None:
    document = browser_openrpc_schema()
    options = TypeScriptClientOptions(
        client_name="BrowserTunnelClient", with_transport="websocket"
    )
    assert generate_typescript_client(document, tmp_path, options)
    assert generate_typescript_client(document, tmp_path, options, check=True) == ()
    client_path = tmp_path / "client.ts"
    original = client_path.read_text()
    client_path.write_text("stale\n")
    assert client_path in generate_typescript_client(
        document, tmp_path, options, check=True
    )
    assert client_path.read_text() == "stale\n"
    assert "BrowserTunnelClient" in original
