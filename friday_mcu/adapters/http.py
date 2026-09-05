"""HTTP adapter — generic HTTP requests."""

from __future__ import annotations

from typing import Any

import requests

from friday_mcu.adapters import Adapter, register_adapter
from friday_mcu.core.contracts import Idempotency, contract
from friday_mcu.core.errors import AdapterError, PreconditionError


@contract(
    precondition="url is a valid HTTP(S) URL.",
    postcondition="Returns the HTTP response.",
    idempotency=Idempotency.IDEMPOTENT,
    failure_mode="AdapterError if the request fails.",
    returns="dict: {status_code: int, body: str, headers: dict}.",
)
def request(
    url: str,
    method: str = "GET",
    headers: dict[str, str] | None = None,
    body: str = "",
    timeout: int = 30,
) -> dict[str, Any]:
    """Make an HTTP request."""
    if not url:
        raise PreconditionError("url is required")
    if not url.startswith(("http://", "https://")):
        raise PreconditionError("url must start with http:// or https://")
    try:
        resp = requests.request(
            method=method.upper(),
            url=url,
            headers=headers or {},
            data=body if body else None,
            timeout=timeout,
        )
        return {
            "status_code": resp.status_code,
            "body": resp.text[:50000],
            "headers": dict(resp.headers),
        }
    except Exception as exc:
        raise AdapterError(f"HTTP request failed: {exc}") from exc


class HTTPAdapter(Adapter):
    @property
    def name(self) -> str:
        return "http"

    @property
    def capabilities(self) -> list[str]:
        return ["request"]

    async def initialize(self) -> None:
        pass

    async def execute(self, action: str, **kwargs: Any) -> Any:
        if action == "request":
            return request(**kwargs)
        raise AdapterError(f"Unknown http action: {action}")

    async def observe(self) -> list:
        return []

    def health_check(self) -> bool:
        return True


try:
    register_adapter(HTTPAdapter())
except Exception:
    pass
