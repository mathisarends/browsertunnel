export interface RpcTransport {
  request<TResult>(method: string, params?: object): Promise<TResult>;
  notifications(): AsyncIterable<unknown>;
  close(): Promise<void>;
}

export class RpcRemoteError extends Error {
  constructor(
    readonly code: number,
    message: string,
    readonly data?: unknown,
  ) {
    super(message);
    this.name = "RpcRemoteError";
  }
}
