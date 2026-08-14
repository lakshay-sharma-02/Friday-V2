"""gmail.send_document - the capability-gap loop's FIRST side-effecting
primitive, hand-built (not LLM-drafted). The two prior LLM drafts for this
gap were REJECTED on record: a confabulated wrapper around a nonexistent
`send_document` function, and a contract with an invalid qualified name.
This impl is written by hand and reviewed by the human gate.

The impl carries ONLY the imports the target module lacks: gmail.py
already provides _access_token / API_BASE / requests / base64 / Path /
contract / Idempotency / PreconditionError / PrimitiveError /
get_credentials - registration appends this block to the module, so the
email MIME imports ride WITH the function.

NO `from __future__ import annotations` here: registration appends this
block at EOF of the existing module, where a future import is a
SyntaxError (register_proposal strips one if a draft carries it).
"""

from email import encoders
from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from friday.contracts import Idempotency, contract
from friday.errors import PreconditionError, PrimitiveError
from friday.secrets import get_credentials


def _default_to() -> str:
    """The default recipient for sends: GMAIL_DEFAULT_TO env or the
    'default_to' key in the pass entry (set during the send-scope consent
    flow). Lets a plan omit `to` entirely so the goal is recipient-
    agnostic - the same convention as whatsapp's default_phone."""
    to = os.environ.get("GMAIL_DEFAULT_TO")
    if not to:
        try:
            creds = get_credentials("gmail")
        except PrimitiveError:
            return ""
        to = creds.get("default_to") or ""
    return to


def _log_redact_send_meta(result: Any) -> Any:
    """Log-time redaction for gmail.send_document: the RECIPIENT address is
    mail metadata (the same discipline as list_unread's sender/subject
    redaction) - the L0 line shows <redacted> for `to` while message_id,
    thread_id and filename stay visible so the trace still identifies the
    send. The real returned value is untouched."""
    if isinstance(result, dict):
        return {**result, "to": "<redacted>"}
    return result


@contract(
    precondition="OAuth credentials are configured and the refresh token "
    "carries the gmail.send scope (a 403 at send time means the token was "
    "minted before this scope - re-consent with gates/_gmail_oauth_setup.py "
    "--scope); to is a non-empty email address; file_path exists and is "
    "readable.",
    postcondition="The file is emailed as an attachment to `to` from the "
    "authenticated account; the returned message id is the Gmail API's "
    "proof of acceptance. No other state changes - nothing is read, moved "
    "or deleted.",
    idempotency=Idempotency.AT_MOST_ONCE,
    failure_mode="PreconditionError for a missing file or an empty "
    "recipient; PrimitiveError with the API error detail on non-2xx. If "
    "the HTTP response is lost, the message may still have been sent - "
    "verify before retrying.",
    returns="dict: {message_id, thread_id, to, filename}.",
    log_transform=_log_redact_send_meta,
)
def send_document(
    file_path: str,
    to: str | None = None,
    subject: str | None = None,
    body: str | None = None,
) -> dict[str, Any]:
    """Email `file_path` as an attachment to `to` (default: the configured
    default recipient) via the Gmail API `messages.send` endpoint. Builds a
    MIME multipart message, base64url-encodes the raw bytes, and returns
    the API's message id as proof of acceptance. The From header is left to
    the API - Gmail always sends from the authenticated account."""
    to = to or _default_to()
    if not to or not to.strip():
        raise PreconditionError(
            "send_document requires a non-empty 'to' (or a configured "
            "default: GMAIL_DEFAULT_TO env / 'default_to' in pass at "
            "friday/gmail)"
        )
    src = Path(file_path)
    if not src.is_file():
        raise PreconditionError(f"send_document requires an existing file: {file_path!r}")

    msg = MIMEMultipart()
    msg["To"] = to
    msg["Subject"] = subject or f"Friday: {src.name}"
    msg.attach(MIMEText(body or "See the attached file.", "plain"))
    with open(src, "rb") as fh:
        part = MIMEBase("application", "octet-stream")
        part.set_payload(fh.read())
    encoders.encode_base64(part)
    part.add_header("Content-Disposition", "attachment", filename=src.name)
    msg.attach(part)
    raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()

    resp = requests.post(
        f"{API_BASE}/users/me/messages/send",
        headers={"Authorization": f"Bearer {_access_token()}"},
        json={"raw": raw},
        timeout=60,
    )
    if resp.status_code != 200:
        raise PrimitiveError(
            f"gmail send failed ({resp.status_code}): {resp.text[:300]}",
            state="message not accepted by Gmail",
        )
    body_resp = resp.json()
    return {
        "message_id": str(body_resp.get("id", "")),
        "thread_id": str(body_resp.get("threadId", "")),
        "to": to,
        "filename": src.name,
    }
