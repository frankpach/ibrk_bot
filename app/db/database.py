"""Legacy database module compatibility shim.

Tests and older integration points still patch/import ``app.db.database``.
The implementation moved to ``app.infrastructure.db.compat``.
"""

from app.infrastructure.db.compat import *  # noqa: F401,F403
