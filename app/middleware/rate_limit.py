"""Simple in-memory IP rate limiting middleware."""

from __future__ import annotations

import time
from collections import defaultdict, deque
from dataclasses import dataclass

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse


@dataclass(frozen=True)
class RateLimitRule:
    """Path based fixed-window rule."""

    prefix: str
    limit: int
    window_seconds: int
    methods: frozenset[str] | None = None

    def matches(self, request: Request) -> bool:
        if self.methods and request.method.upper() not in self.methods:
            return False
        return request.url.path.startswith(self.prefix)


class IPRateLimitMiddleware(BaseHTTPMiddleware):
    """Per-process IP rate limiter for common brute-force and enumeration paths."""

    DEFAULT_RULES = (
        RateLimitRule(
            prefix="/v1/admin/auth/login",
            limit=5,
            window_seconds=60,
            methods=frozenset({"POST"}),
        ),
        RateLimitRule(prefix="/v1/api/order/status", limit=10, window_seconds=60),
        RateLimitRule(prefix="/xpay/epay", limit=60, window_seconds=60),
        RateLimitRule(prefix="/v1/admin", limit=100, window_seconds=60),
    )

    def __init__(self, app, rules: tuple[RateLimitRule, ...] | None = None):
        super().__init__(app)
        self.rules = rules or self.DEFAULT_RULES
        self._hits: dict[tuple[str, str], deque[float]] = defaultdict(deque)

    async def dispatch(self, request: Request, call_next):
        rule = self._match_rule(request)
        if rule and self._is_limited(request, rule):
            return JSONResponse(
                status_code=429,
                content={"code": -1, "msg": "请求过于频繁，请稍后再试"},
                headers={"Retry-After": str(rule.window_seconds)},
            )
        return await call_next(request)

    def _match_rule(self, request: Request) -> RateLimitRule | None:
        for rule in self.rules:
            if rule.matches(request):
                return rule
        return None

    def _is_limited(self, request: Request, rule: RateLimitRule) -> bool:
        client_ip = request.client.host if request.client else "unknown"
        key = (client_ip, rule.prefix)
        now = time.monotonic()
        hits = self._hits[key]
        cutoff = now - rule.window_seconds

        while hits and hits[0] <= cutoff:
            hits.popleft()

        if len(hits) >= rule.limit:
            return True

        hits.append(now)
        return False
