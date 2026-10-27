# Importing the modules explicitly registers the browser's RPC methods.
from . import clipboard, input, navigation, tabs

__all__ = ["clipboard", "input", "navigation", "tabs"]
