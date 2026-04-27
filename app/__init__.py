"""Application package — FastAPI backend boilerplate.

Layered architecture:
    app.api          → HTTP layer (routers, deps, schemas)
    app.services     → Business logic / use cases
    app.repositories → Persistence (SQLAlchemy)
    app.integrations → External adapters (cache, email, HTTP)
    app.core         → Cross-cutting infra (config, logging, i18n, ...)
"""

__version__ = "0.1.0"
