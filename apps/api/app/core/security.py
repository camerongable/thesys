import ipaddress
import re
import socket
from dataclasses import dataclass
from urllib.parse import urlparse

from app.core.config import Settings


class SecurityValidationError(ValueError):
    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


@dataclass(frozen=True)
class UploadValidationResult:
    filename: str
    content_type: str
    media_type: str


_SAFE_FILENAME_RE = re.compile(r"[^A-Za-z0-9._-]+")
_ALLOWED_UPLOADS: dict[str, tuple[str, set[str], set[str]]] = {
    "pdf": ("application/pdf", {".pdf"}, {"application/pdf"}),
    "text": ("text/plain", {".txt"}, {"text/plain"}),
    "markdown": ("text/markdown", {".md", ".markdown"}, {"text/markdown", "text/plain"}),
    "png": ("image/png", {".png"}, {"image/png"}),
    "jpeg": ("image/jpeg", {".jpg", ".jpeg"}, {"image/jpeg"}),
    "webp": ("image/webp", {".webp"}, {"image/webp"}),
}


def validate_url_fetch_target(url: str) -> None:
    parsed = urlparse(url.strip())
    if parsed.scheme.casefold() not in {"http", "https"}:
        raise SecurityValidationError("Only http and https URLs can be fetched.")
    if not parsed.hostname:
        raise SecurityValidationError("URL must include a hostname.")
    if parsed.username or parsed.password:
        raise SecurityValidationError("URLs with embedded credentials are not allowed.")

    host = parsed.hostname.strip("[]")
    for ip_address in _resolve_host_addresses(host):
        if _is_blocked_address(ip_address):
            raise SecurityValidationError(
                f"URL host resolves to a blocked network address: {ip_address}."
            )


def validate_upload(
    *,
    filename: str | None,
    content_type: str | None,
    body: bytes,
    settings: Settings,
) -> UploadValidationResult:
    max_bytes = settings.max_upload_mb * 1024 * 1024
    if len(body) > max_bytes:
        raise SecurityValidationError(f"File exceeds {settings.max_upload_mb} MB upload limit.")

    safe_filename = sanitize_filename(filename)
    normalized_content_type = (content_type or "application/octet-stream").split(";")[0].strip()
    normalized_content_type = normalized_content_type.casefold() or "application/octet-stream"
    extension = _extension(safe_filename)

    for media_type, (canonical_content_type, extensions, content_types) in _ALLOWED_UPLOADS.items():
        if extension not in extensions:
            continue
        if normalized_content_type not in content_types:
            raise SecurityValidationError(
                f"{extension} uploads must use one of: {', '.join(sorted(content_types))}."
            )
        _validate_magic_bytes(media_type, body)
        return UploadValidationResult(
            filename=safe_filename,
            content_type=canonical_content_type,
            media_type=media_type,
        )

    raise SecurityValidationError(
        "Only PDF, text, Markdown, PNG, JPG, JPEG, and WebP uploads are supported."
    )


def sanitize_filename(filename: str | None) -> str:
    candidate = (filename or "uploaded-evidence").strip().replace("\\", "/")
    if "/" in candidate:
        raise SecurityValidationError("Upload filenames cannot include path separators.")
    sanitized = _SAFE_FILENAME_RE.sub("-", candidate).strip(".-")
    if not sanitized:
        raise SecurityValidationError("Upload filename is not valid.")
    return sanitized[:180]


def _resolve_host_addresses(host: str) -> set[ipaddress.IPv4Address | ipaddress.IPv6Address]:
    try:
        literal = ipaddress.ip_address(host)
        return {literal}
    except ValueError:
        pass

    try:
        infos = socket.getaddrinfo(host, None, proto=socket.IPPROTO_TCP)
    except socket.gaierror as exc:
        raise SecurityValidationError("URL hostname could not be resolved.") from exc

    addresses: set[ipaddress.IPv4Address | ipaddress.IPv6Address] = set()
    for info in infos:
        sockaddr = info[4]
        if not sockaddr:
            continue
        try:
            addresses.add(ipaddress.ip_address(str(sockaddr[0])))
        except ValueError:
            continue
    if not addresses:
        raise SecurityValidationError("URL hostname did not resolve to an IP address.")
    return addresses


def _is_blocked_address(address: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    return any(
        (
            address.is_loopback,
            address.is_private,
            address.is_link_local,
            address.is_multicast,
            address.is_reserved,
            address.is_unspecified,
        )
    )


def _extension(filename: str) -> str:
    marker = filename.rfind(".")
    return filename[marker:].casefold() if marker >= 0 else ""


def _validate_magic_bytes(media_type: str, body: bytes) -> None:
    if media_type == "pdf" and not body.startswith(b"%PDF"):
        raise SecurityValidationError("PDF upload did not start with a PDF signature.")
    if media_type == "png" and not body.startswith(b"\x89PNG\r\n"):
        raise SecurityValidationError("PNG upload did not start with a PNG signature.")
    if media_type == "jpeg" and not body.startswith(b"\xff\xd8\xff"):
        raise SecurityValidationError("JPEG upload did not start with a JPEG signature.")
    if media_type == "webp" and not (body.startswith(b"RIFF") and body[8:12] == b"WEBP"):
        raise SecurityValidationError("WebP upload did not start with a WebP signature.")
    if media_type in {"text", "markdown"}:
        try:
            body.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise SecurityValidationError("Text upload must be valid UTF-8.") from exc
