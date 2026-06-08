"""Shared slowapi limiter — single source of truth for the rate-limit policy.

Registered on ``app.state.limiter`` in ``app/main.py`` and imported by the
routers for their ``@limiter.limit(...)`` decorators, so the keying function
is defined in exactly one place.
"""

from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)
