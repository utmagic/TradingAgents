"""TLS environment bootstrap helpers for HTTP clients.

Ensures CA bundle env vars are set to a trusted certificate store so
libraries such as curl_cffi/requests can validate TLS chains.
"""

from __future__ import annotations

import os


def configure_tls_ca_bundle() -> None:
    """Set CA bundle env vars from certifi when not already configured."""
    # Respect explicit user/system overrides first (e.g. corporate root CA).
    if os.getenv("SSL_CERT_FILE") and os.getenv("CURL_CA_BUNDLE") and os.getenv("REQUESTS_CA_BUNDLE"):
        return

    try:
        import certifi
    except Exception:
        return

    ca_bundle = certifi.where()
    os.environ.setdefault("SSL_CERT_FILE", ca_bundle)
    os.environ.setdefault("CURL_CA_BUNDLE", ca_bundle)
    os.environ.setdefault("REQUESTS_CA_BUNDLE", ca_bundle)
