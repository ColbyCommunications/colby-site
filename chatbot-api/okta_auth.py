from __future__ import annotations

import os
from functools import lru_cache
from typing import Any, Dict, List


class OktaConfigError(RuntimeError):
    """Raised when Okta configuration is incomplete or invalid."""


# Session keys used to store Okta auth state in Starlette/FastAPI sessions.
OKTA_SESSION_USER_KEY = "okta_user"
OKTA_SESSION_STATE_KEY = "okta_state"
OKTA_SESSION_CODE_VERIFIER_KEY = "okta_code_verifier"
OKTA_SESSION_ID_TOKEN_KEY = "okta_id_token"


@lru_cache()
def get_okta_config() -> Dict[str, Any]:
    """
    Load Okta configuration for the admin panel from environment variables.

    Required env vars:
    - OKTA_DOMAIN (for example: integrator-123456.okta.com)
    - OKTA_CLIENT_ID
    - OKTA_CLIENT_SECRET
    - OKTA_REDIRECT_URI (must match the /admin/authorization-code/callback URL)

    Optional:
    - OKTA_POST_LOGOUT_REDIRECT_URI (defaults to OKTA_REDIRECT_URI base path)
    - OKTA_SCOPES (defaults to "openid profile email")
    """
    domain = os.getenv("OKTA_DOMAIN")
    client_id = os.getenv("OKTA_CLIENT_ID")
    client_secret = os.getenv("OKTA_CLIENT_SECRET")
    redirect_uri = os.getenv("OKTA_REDIRECT_URI")
    scope = os.getenv("OKTA_SCOPES", "openid profile email")

    missing: List[str] = [
        name
        for name, value in [
            ("OKTA_DOMAIN", domain),
            ("OKTA_CLIENT_ID", client_id),
            ("OKTA_CLIENT_SECRET", client_secret),
            ("OKTA_REDIRECT_URI", redirect_uri),
        ]
        if not value
    ]
    if missing:
        raise OktaConfigError(
            "Okta admin authentication is not fully configured. Missing environment "
            f"variables: {', '.join(missing)}"
        )

    # Derive the base OAuth 2.0 / OIDC URLs from the domain using the default
    # authorization server, matching the Okta guide:
    # https://developer.okta.com/docs/guides/sign-into-web-app-redirect/python/main/
    base = f"https://{domain}/oauth2/default"

    # Derive a sensible default for the post-logout redirect if not provided.
    post_logout_redirect_uri = os.getenv("OKTA_POST_LOGOUT_REDIRECT_URI")
    if not post_logout_redirect_uri and redirect_uri:
        # Try to strip the callback path so we end up at the app base, e.g.
        # http://localhost:8000/chatbot-api/admin/
        if "/authorization-code/callback" in redirect_uri:
            post_logout_redirect_uri = redirect_uri.rsplit(
                "/authorization-code/callback", 1
            )[0]
        else:
            post_logout_redirect_uri = redirect_uri

    return {
        "domain": domain,
        "client_id": client_id,
        "client_secret": client_secret,
        "redirect_uri": redirect_uri,
        "post_logout_redirect_uri": post_logout_redirect_uri,
        "scope": scope,
        "auth_uri": f"{base}/v1/authorize",
        "token_uri": f"{base}/v1/token",
        "userinfo_uri": f"{base}/v1/userinfo",
        "issuer": base,
        "logout_uri": f"{base}/v1/logout",
    }



