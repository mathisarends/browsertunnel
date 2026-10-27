import json

from fastapi_rpckit import RpcFailure, RpcSuccess
from pydantic import TypeAdapter

from browsertunnel.features.browser.presentation.rpc import contract


def browser_openrpc_schema() -> dict:
    return contract.to_openrpc()


def browser_json_schema() -> dict:
    """Derive the existing JSON Schema endpoint from the OpenRPC contract."""
    document = json.loads(
        json.dumps(browser_openrpc_schema()).replace(
            "#/components/schemas/", "#/$defs/"
        )
    )
    definitions = document["components"]["schemas"]
    envelopes = TypeAdapter(RpcSuccess | RpcFailure).json_schema()
    definitions.update(envelopes.pop("$defs", {}))
    methods = document["methods"]
    notifications = document["x-rpc-notifications"]
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": "/api/browser/schema.json",
        "title": "BrowserTunnel JSON-RPC Protocol",
        "$defs": definitions,
        "oneOf": [
            *[method["x-rpc-request-schema"] for method in methods],
            *envelopes["anyOf"],
            *[notification["message"] for notification in notifications],
        ],
        "x-rpc-protocol-version": document["x-rpc-protocol-version"],
        "x-rpc-methods": methods,
        "x-rpc-notifications": notifications,
        "x-rpc-events": document["x-rpc-notification-types"],
    }
