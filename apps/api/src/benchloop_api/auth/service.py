import json
import time

import httpx
import jwt

from benchloop_api.auth.models import AuthenticatedPrincipal
from benchloop_api.config import AppSettings


class TokenVerificationError(Exception):
    pass


class ClerkJwtVerifier:
    def __init__(
        self,
        settings: AppSettings,
        *,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._jwks_url = settings.clerk_jwks_url
        self._issuer = settings.clerk_jwt_issuer
        self._audience = settings.clerk_jwt_audience
        self._jwks_cache_ttl_seconds = settings.clerk_jwks_cache_ttl_seconds
        self._transport = transport
        self._cached_jwks: dict[str, dict[str, object]] = {}
        self._jwks_cached_at = 0.0

    async def verify_token(self, token: str) -> AuthenticatedPrincipal:
        try:
            header = jwt.get_unverified_header(token)
        except jwt.PyJWTError as exc:
            raise TokenVerificationError("Invalid token header.") from exc

        key_id = header.get("kid")
        algorithm = header.get("alg")
        if not isinstance(key_id, str) or not key_id:
            raise TokenVerificationError("Missing signing key id.")
        if algorithm != "RS256":
            raise TokenVerificationError("Unsupported signing algorithm.")

        jwk = await self._get_signing_jwk(key_id)
        try:
            signing_key = jwt.algorithms.RSAAlgorithm.from_jwk(json.dumps(jwk))
            payload = jwt.decode(
                token,
                signing_key,
                algorithms=["RS256"],
                audience=self._audience,
                issuer=self._issuer,
                options={
                    "require": ["exp", "iat", "nbf", "sub"],
                    "verify_aud": self._audience is not None,
                    "verify_iss": self._issuer is not None,
                },
                leeway=5,
            )
        except jwt.PyJWTError as exc:
            raise TokenVerificationError("Token verification failed.") from exc

        subject = payload.get("sub")
        if not isinstance(subject, str) or not subject:
            raise TokenVerificationError("Token subject is missing.")

        return AuthenticatedPrincipal(subject=subject, claims=payload)

    async def _get_signing_jwk(self, key_id: str) -> dict[str, object]:
        if self._jwks_cache_is_fresh():
            jwk = self._cached_jwks.get(key_id)
            if jwk is not None:
                return jwk

        await self._refresh_jwks()
        jwk = self._cached_jwks.get(key_id)
        if jwk is None:
            raise TokenVerificationError("Signing key was not found.")
        return jwk

    def _jwks_cache_is_fresh(self) -> bool:
        if not self._cached_jwks:
            return False
        return (time.monotonic() - self._jwks_cached_at) < self._jwks_cache_ttl_seconds

    async def _refresh_jwks(self) -> None:
        try:
            async with httpx.AsyncClient(
                transport=self._transport,
                timeout=5.0,
            ) as client:
                response = await client.get(self._jwks_url)
                response.raise_for_status()
        except httpx.HTTPError as exc:
            raise TokenVerificationError("Unable to fetch Clerk JWKS.") from exc

        payload = response.json()
        keys = payload.get("keys")
        if not isinstance(keys, list):
            raise TokenVerificationError("Clerk JWKS payload is invalid.")

        cached_keys: dict[str, dict[str, object]] = {}
        for key in keys:
            if not isinstance(key, dict):
                continue
            key_id = key.get("kid")
            if isinstance(key_id, str) and key_id:
                cached_keys[key_id] = key

        if not cached_keys:
            raise TokenVerificationError("Clerk JWKS is empty.")

        self._cached_jwks = cached_keys
        self._jwks_cached_at = time.monotonic()
