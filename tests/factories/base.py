"""Shared base for factory_boy factories.

Domain factories inherit from :class:`BaseFactory` so every aggregate is built
the same way and test data is deterministic. The boilerplate ships no domain
models yet, so this is the seam future factories plug into (see
``.cursor/rules/test-factories-seeders.mdc``).
"""

from __future__ import annotations

import factory

# Seed factory_boy's Faker/random proxy once so generated data is reproducible.
DEFAULT_SEED = "fastapi-boilerplate"
factory.random.reseed_random(DEFAULT_SEED)


class BaseFactory(factory.Factory):
    """Abstract base every aggregate/DTO factory inherits from.

    Subclasses declare ``class Meta: model = <Type>``. For ORM aggregates that
    must persist, swap the base to ``factory.alchemy.SQLAlchemyModelFactory`` and
    bind the test session; services still own the Unit of Work, so prefer
    ``build()`` over ``create()`` in unit tests.
    """

    class Meta:
        abstract = True
