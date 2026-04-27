"""Persistence layer.

One repository per aggregate root. Repositories receive an ``AsyncSession``,
return entities/DTOs, and **must not commit** — services own the unit of work.
"""
