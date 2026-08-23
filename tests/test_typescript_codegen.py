from pathlib import Path
from typing import Any

from scripts.typescript_codegen import (
    TypeScriptClientOptions,
    render_typescript_client,
    write_typescript_client,
)


def openrpc_document() -> dict[str, Any]:
    return {
        "openrpc": "1.3.2",
        "info": {"title": "Test", "version": "1.0.0"},
        "methods": [
            {
                "name": "browser.input.click",
                "params": [
                    {
                        "name": "button",
                        "required": True,
                        "schema": {
                            "type": "string",
                            "enum": ["left", "right"],
                        },
                    }
                ],
                "result": {"name": "result", "schema": {"type": "null"}},
                "x-rpc-params-schema": {"$ref": "#/components/schemas/ClickParams"},
            },
            {
                "name": "browser.input.text.insert",
                "params": [
                    {
                        "name": "text",
                        "required": True,
                        "schema": {"type": "string"},
                    }
                ],
                "result": {"name": "result", "schema": {"type": "string"}},
                "x-rpc-params-schema": {"$ref": "#/components/schemas/TextParams"},
            },
        ],
        "components": {
            "schemas": {
                "ClickParams": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {
                        "button": {
                            "type": "string",
                            "enum": ["left", "right"],
                        }
                    },
                    "required": ["button"],
                },
                "TextParams": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {"text": {"type": "string"}},
                    "required": ["text"],
                },
            }
        },
    }


def test_renders_idiomatic_types_and_nested_namespaces() -> None:
    files = render_typescript_client(
        openrpc_document(),
        TypeScriptClientOptions(client_name="TestClient", source="test.json"),
    )

    assert 'button: "left" | "right";' in files["models.ts"]
    assert "async click(params: ClickParams): Promise<void>" in files["client.ts"]
    assert "await this.transport.request<null>" in files["client.ts"]
    assert "Object.assign(new BrowserInputClient" in files["client.ts"]
    assert "text: new BrowserInputTextClient" in files["client.ts"]


def test_check_reports_generated_files_that_are_out_of_date(tmp_path: Path) -> None:
    options = TypeScriptClientOptions(client_name="TestClient", source="test.json")

    changed = write_typescript_client(openrpc_document(), tmp_path, options)

    assert {path.name for path in changed} == {"models.ts", "client.ts", "index.ts"}
    assert (
        write_typescript_client(openrpc_document(), tmp_path, options, check=True) == ()
    )
    (tmp_path / "client.ts").write_text("stale\n", encoding="utf-8")
    assert write_typescript_client(
        openrpc_document(), tmp_path, options, check=True
    ) == (tmp_path / "client.ts",)
