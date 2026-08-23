import pyrpckit as rpc

from backend.application import Browser
from backend.presentation.rpc.methods.clipboard import ClipboardMethods
from backend.presentation.rpc.methods.input import InputMethods
from backend.presentation.rpc.methods.navigation import NavigationMethods
from backend.presentation.rpc.methods.tabs import TabMethods

BROWSER_RPC_METHODS = (
    NavigationMethods,
    InputMethods,
    ClipboardMethods,
    TabMethods,
)


def browser_rpc_methods(browser: Browser) -> tuple[rpc.RpcHandler, ...]:
    return tuple(methods(browser) for methods in BROWSER_RPC_METHODS)


__all__ = ["BROWSER_RPC_METHODS", "browser_rpc_methods"]
