# Okta admin authentication

The `/admin/*` surface is gated by Okta SSO using the standard
Authorization Code + PKCE flow against Okta's default authorization
server.

Two files do all the work:

- [`okta_auth.py`](../okta_auth.py) — pure-config module: env-var loading,
  cached `get_okta_config()`, derived URLs (`auth_uri`, `token_uri`,
  `userinfo_uri`, `logout_uri`), and the session-key constants.
- [`admin_api.py`](../admin_api.py) — `require_admin` dependency,
  `/admin/login`, `/admin/authorization-code/callback`, `/admin/logout`,
  and path normalization for the `/chatbot-api` prefix.

The session cookie itself is set up by Starlette's `SessionMiddleware` in
[`rag_app.py`](../rag_app.py).

## Required environment variables

| Variable                          | Purpose |
|-----------------------------------|---------|
| `OKTA_DOMAIN`                     | e.g. `integrator-123456.okta.com` |
| `OKTA_CLIENT_ID`                  | Okta app client id |
| `OKTA_CLIENT_SECRET`              | Okta app client secret |
| `OKTA_REDIRECT_URI`               | Must match the configured Okta callback (`https://www.colby.edu/chatbot-api/admin/authorization-code/callback`) |
| `OKTA_SCOPES` (optional)          | Defaults to `openid profile email` |
| `OKTA_POST_LOGOUT_REDIRECT_URI` (optional) | Where Okta sends users after logout. Auto-derived from `OKTA_REDIRECT_URI` if unset. |
| `ADMIN_OKTA_ENABLED`              | When **not** `true`, `require_admin` is a no-op (admin routes are open) |
| `ADMIN_SESSION_SECRET`            | Session-cookie signing key. Falls back to `APP_SESSION_SECRET`. |
| `ADMIN_SESSION_COOKIE_NAME`       | Defaults to `colby_admin_session` |
| `ADMIN_SESSION_SAME_SITE`         | Defaults to `lax` |
| `ADMIN_SESSION_HTTPS_ONLY`        | `true` in production, `false` for local dev |

`get_okta_config()` is `lru_cache`'d, so changes to these env vars at
runtime won't take effect until the worker restarts.

## Session keys

Defined in `okta_auth.py`:

- `OKTA_SESSION_USER_KEY = "okta_user"` — the user profile dict.
  Presence of this key == authenticated.
- `OKTA_SESSION_STATE_KEY = "okta_state"` — CSRF token for the auth code
  exchange.
- `OKTA_SESSION_CODE_VERIFIER_KEY = "okta_code_verifier"` — PKCE verifier.
- `OKTA_SESSION_ID_TOKEN_KEY = "okta_id_token"` — kept around so
  `/admin/logout` can pass `id_token_hint` to Okta.

## Exempt paths

`require_admin` allows these through without an active session so the
login flow can bootstrap:

```
/admin/, /admin/login,
/admin/authorization-code/callback,
/admin/logout,
/admin/responses, /admin/dashboard,
/admin/static/*
```

(See `_ADMIN_AUTH_EXEMPT_PATHS` in [`admin_api.py`](../admin_api.py).)
The two HTML routes (`/admin/responses`, `/admin/dashboard`) are exempt
because they render their own logged-out preview server-side — the JS
re-checks auth via an API call once the page loads.

## Path normalization

Because Platform.sh routes `/chatbot-api/*` to a container that internally
mounts routes at `/admin/*`, every auth check must compare against the
*router-relative* path, not the public URL. `_get_request_path` strips
`request.scope.root_path` (or `app.root_path`) off the front of the
incoming `path` so `/chatbot-api/admin/login` becomes `/admin/login` for
the exemption check.

## Behavior summary

- `ADMIN_OKTA_ENABLED != "true"` → `require_admin` returns immediately,
  every `/admin/*` route is wide open. Useful for local dev.
- Otherwise:
  - Exempt path → allowed.
  - `okta_user` in session → allowed.
  - No session → 307 redirect to `/admin/login`, which then redirects to
    Okta's authorize URL with PKCE.
- `/admin/authorization-code/callback` validates the `state`, exchanges
  the code at `token_uri`, fetches the profile at `userinfo_uri`, stores
  both in the session, and redirects back into the dashboard.
- `/admin/logout` clears the session and redirects to Okta's logout
  endpoint with the stored `id_token_hint` and
  `post_logout_redirect_uri`.
