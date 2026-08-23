"""L1 primitive: HTTP requests (GET, POST, PUT, DELETE, PATCH).

Deterministic HTTPS mechanism for calling APIs, webhooks, and REST
endpoints from within a plan. Returns structured response data (status
code, headers, body) so L2 checks can verify the result.

Safety: this is a READ-heavy primitive (GET is idempotent). Write
methods (POST/PUT/DELETE/PATCH) are at-most-once because a retry could
duplicate a side effect on the remote server. No authentication is
built-in — callers pass headers explicitly (e.g. Authorization).

Credentials: none by default. Pass headers in the args.
"""

from __future__ import annotations

import json
from typing import Any

import requests

from friday.contracts import Idempotency, contract
from friday.errors import PreconditionError, PrimitiveError

DEFAULT_TIMEOUT_S = 30
MAX_BODY_CHARS = 50_000  # cap logged body size


def _parse_body(resp: requests.Response) -> Any:
    """Parse response body: try JSON first, fall back to text."""
    content_type = resp.headers.get("Content-Type", "")
    if "json" in content_type:
        try:
            return resp.json()
        except (json.JSONDecodeError, ValueError):
            pass
    text = resp.text
    if len(text) > MAX_BODY_CHARS:
        text = text[:MAX_BODY_CHARS] + f"...<+{len(resp.text) - MAX_BODY_CHARS} chars>"
    return text


@contract(
    precondition="url is a non-empty string starting with http:// or https://. method is a valid HTTP method.",
    postcondition="Returns the HTTP response with status, headers, and body. The remote server is called exactly once.",
    idempotency=Idempotency.IDEMPOTENT,
    failure_mode="PreconditionError for empty url or invalid method; PrimitiveError on network/timeout failure.",
    returns="dict: {status_code, headers, body, url, method}.",
)
def request(
    url: str,
    method: str = "GET",
    headers: dict[str, str] | None = None,
    body: Any = None,
    timeout_s: int = DEFAULT_TIMEOUT_S,
) -> dict[str, Any]:
    """Make an HTTP request and return the structured response.

    Args:
        url: The target URL (must start with http:// or https://).
        method: HTTP method (GET, POST, PUT, DELETE, PATCH). Case-insensitive.
        headers: Optional dict of request headers.
        body: Optional request body. If a dict/list, sent as JSON.
              If a string, sent as raw text. If bytes, sent as raw binary.
        timeout_s: Request timeout in seconds (default 30).

    Returns:
        dict with keys: status_code (int), headers (dict), body (str|dict|list),
        url (str), method (str).
    """
    if not url or not url.strip():
        raise PreconditionError("request requires a non-empty url")
    url = url.strip()
    if not (url.startswith("http://") or url.startswith("https://")):
        raise PreconditionError(f"request url must start with http:// or https://, got {url[:20]}...")

    valid_methods = {"GET", "POST", "PUT", "DELETE", "PATCH", "HEAD", "OPTIONS"}
    method_upper = method.upper()
    if method_upper not in valid_methods:
        raise PreconditionError(f"request method must be one of {sorted(valid_methods)}, got {method!r}")

    kwargs: dict[str, Any] = {"timeout": timeout_s}
    if headers:
        kwargs["headers"] = headers

    if body is not None and method_upper not in ("GET", "HEAD"):
        if isinstance(body, (dict, list)):
            kwargs["json"] = body
        elif isinstance(body, bytes):
            kwargs["data"] = body
        else:
            kwargs["data"] = str(body)

    try:
        resp = requests.request(method_upper, url, **kwargs)
    except requests.Timeout as exc:
        raise PrimitiveError(
            f"HTTP {method_upper} {url} timed out after {timeout_s}s",
            state="request not completed",
        ) from exc
    except requests.ConnectionError as exc:
        raise PrimitiveError(
            f"HTTP {method_upper} {url} connection failed: {exc}",
            state="request not completed",
        ) from exc
    except requests.RequestException as exc:
        raise PrimitiveError(
            f"HTTP {method_upper} {url} failed: {exc}",
            state="request not completed",
        ) from exc

    return {
        "status_code": resp.status_code,
        "headers": dict(resp.headers),
        "body": _parse_body(resp),
        "url": resp.url,
        "method": method_upper,
    }
