"""Business logic / use cases. One service per bounded context.

Hard rules:
- Never import ``fastapi.*``, never raise ``HTTPException``.
- Receive collaborators via ``__init__`` (Protocols) — no module globals.
"""
