# Authentication

Larch uses OAuth 2.0. Every API call carries a bearer access token in the Authorization header.

## Tokens

Access tokens expire after 60 minutes. An expired token returns HTTP 401 with the code `token_expired`.

## Refresh

To refresh an access token, POST the refresh token to `/oauth/token` with `grant_type=refresh_token`.
Refresh tokens are valid for 30 days and are rotated on every use.

## Scopes

Request only the scopes you need: `read`, `write` or `admin`.
