"""Shared utilities for the Beacon project."""

import functools
import hashlib
import time

from django.core.cache import cache
from django.http import HttpResponse
from django.utils.http import url_has_allowed_host_and_scheme


def safe_redirect_url(request, url, fallback='/dashboard/'):
    """Return *url* only if it points to an allowed host, otherwise *fallback*.

    Prevents open-redirect attacks via unvalidated ``next`` parameters.
    """
    if url and url_has_allowed_host_and_scheme(
        url,
        allowed_hosts={request.get_host()},
        require_https=request.is_secure(),
    ):
        return url
    return fallback


def rate_limit(max_requests=10, window=60, key_func=None):
    """Simple cache-based rate limiter for Django views.

    Works with both function-based views and class-based view methods.

    Args:
        max_requests: Maximum requests allowed within the window.
        window: Time window in seconds.
        key_func: Optional callable(request) → str for cache key.
                  Defaults to IP-based limiting.
    """
    def decorator(view_func):
        @functools.wraps(view_func)
        def wrapper(*args, **kwargs):
            # Support both FBVs (request, ...) and CBV methods (self, request, ...)
            from django.http import HttpRequest
            if args and isinstance(args[0], HttpRequest):
                request = args[0]
            elif len(args) >= 2 and isinstance(args[1], HttpRequest):
                request = args[1]
            else:
                # Fallback: skip rate limiting if we can't find the request
                return view_func(*args, **kwargs)

            if key_func:
                ident = key_func(request)
            else:
                forwarded = request.META.get('HTTP_X_FORWARDED_FOR', '')
                ip = forwarded.split(',')[0].strip() if forwarded else request.META.get('REMOTE_ADDR', '0.0.0.0')
                ident = ip

            hashed = hashlib.md5(ident.encode()).hexdigest()[:12]
            cache_key = f'ratelimit:{view_func.__name__}:{hashed}'

            history = cache.get(cache_key, [])
            now = time.time()

            # Purge expired entries
            history = [t for t in history if now - t < window]

            if len(history) >= max_requests:
                return HttpResponse(
                    'Rate limit exceeded. Please try again later.',
                    status=429,
                    content_type='text/plain',
                )

            history.append(now)
            cache.set(cache_key, history, timeout=window)
            return view_func(*args, **kwargs)

        return wrapper
    return decorator
