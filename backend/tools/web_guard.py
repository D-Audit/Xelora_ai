"""Public-web request guard for Xelora tools.

Tool-provided URLs are untrusted. This module rejects private, loopback, and
reserved addresses before each redirect; it also bounds redirects and response
size. It is intentionally small so the existing Excel live-data skill can use
it without turning into a general browser subsystem.
"""

from __future__ import annotations

import ipaddress
import socket
from urllib.parse import urljoin, urlsplit

import requests

MAX_REDIRECTS = 5
MAX_RESPONSE_BYTES = 2 * 1024 * 1024
_CGNAT = ipaddress.ip_network("100.64.0.0/10")


class UnsafeUrlError(ValueError):
    """Raised when a URL could reach a local or otherwise protected address."""


def _blocked_reason(address: ipaddress._BaseAddress) -> str | None:
    if address.is_loopback:
        return "loopback"
    if address.is_link_local:
        return "link-local or metadata address"
    if address.is_private or (address.version == 4 and address in _CGNAT):
        return "private network"
    if address.is_multicast or address.is_reserved or address.is_unspecified:
        return "reserved address space"
    return None


def validate_public_url(url: str) -> None:
    """Require HTTP(S) and reject a hostname that resolves to non-public IPs."""
    parsed = urlsplit(url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise UnsafeUrlError("URL must be an absolute http:// or https:// address.")

    host = parsed.hostname
    try:
        literal = ipaddress.ip_address(host)
    except ValueError:
        literal = None
    if literal is not None:
        reason = _blocked_reason(literal)
        if reason:
            raise UnsafeUrlError(f"Refusing to fetch {host}: {reason}.")
        return

    try:
        addresses = socket.getaddrinfo(host, parsed.port or (443 if parsed.scheme == "https" else 80), type=socket.SOCK_STREAM)
    except OSError as exc:
        raise UnsafeUrlError(f"Could not resolve {host}: {exc}") from exc
    for item in addresses:
        address = ipaddress.ip_address(item[4][0])
        mapped = getattr(address, "ipv4_mapped", None)
        if mapped is not None:
            address = mapped
        reason = _blocked_reason(address)
        if reason:
            raise UnsafeUrlError(f"Refusing to fetch {host}: resolves to {reason}.")


def get_public_content(
    url: str,
    *,
    timeout: float = 10.0,
    accept: str = "*/*",
) -> tuple[bytes, str, str]:
    """Fetch bounded public content, checking every redirect target."""
    current = url
    session = requests.Session()
    session.trust_env = False
    try:
        for _ in range(MAX_REDIRECTS + 1):
            validate_public_url(current)
            response = session.get(
                current,
                timeout=timeout,
                allow_redirects=False,
                stream=True,
                headers={"Accept": accept, "User-Agent": "Xelora/1.0"},
            )
            if response.is_redirect:
                destination = response.headers.get("Location")
                response.close()
                if not destination:
                    raise ValueError("Redirect response did not include a Location header.")
                current = urljoin(current, destination)
                continue
            response.raise_for_status()
            content_type = response.headers.get("Content-Type", "").lower()
            declared_length = response.headers.get("Content-Length")
            if declared_length:
                try:
                    exceeds_limit = int(declared_length) > MAX_RESPONSE_BYTES
                except ValueError:
                    exceeds_limit = False
                if exceeds_limit:
                    response.close()
                    raise ValueError("The source response exceeds the 2 MB safety limit.")
            body = bytearray()
            for chunk in response.iter_content(chunk_size=65536):
                body.extend(chunk)
                if len(body) > MAX_RESPONSE_BYTES:
                    response.close()
                    raise ValueError("The source response exceeds the 2 MB safety limit.")
            response.close()
            return bytes(body), current, content_type
    finally:
        session.close()
    raise UnsafeUrlError(f"Too many redirects (maximum {MAX_REDIRECTS}).")


def get_public_json(url: str, *, timeout: float = 10.0) -> tuple[object, str]:
    """Fetch a small JSON response, checking every redirect target."""
    body, final_url, content_type = get_public_content(
        url, timeout=timeout, accept="application/json"
    )
    if "json" not in content_type:
        raise ValueError("The source did not return JSON data.")
    return requests.models.complexjson.loads(body.decode("utf-8")), final_url
