from fastapi_rpckit import RpcChannel

# Keep the existing fully qualified method names on the wire.
channel = RpcChannel("browser", namespace="")
