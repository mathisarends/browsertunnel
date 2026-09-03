import pyrpckit as rpc

from browsertunnel.application import Browser
from browsertunnel.presentation.rpc.methods.clipboard import ClipboardMethods
from browsertunnel.presentation.rpc.methods.input import InputMethods
from browsertunnel.presentation.rpc.methods.navigation import NavigationMethods
from browsertunnel.presentation.rpc.methods.tabs import TabMethods

BROWSER_RPC_METHODS = (
    NavigationMethods,
    InputMethods,
    ClipboardMethods,
    TabMethods,
)


def browser_rpc_methods(browser: Browser) -> tuple[rpc.RpcHandler, ...]:
    return (
        NavigationMethods(browser.navigation),
        InputMethods(browser.input),
        ClipboardMethods(browser.clipboard),
        TabMethods(browser.tabs),
    )


__all__ = ["BROWSER_RPC_METHODS", "browser_rpc_methods"]
