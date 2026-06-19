#!/usr/bin/env python
"""CI gate for environment-file drift between ``.env.example`` and ``Settings``.

Bidirectional, because ``Settings`` uses ``extra="forbid"``:
- every top-level ``Settings`` field must appear in ``.env.example`` (missing → fail);
- every key in ``.env.example`` must map to a ``Settings`` field, including nested
  ``PARENT__CHILD`` keys (unknown → fail) — otherwise a stray key would crash the
  app at startup.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

from pydantic import BaseModel
from pydantic.fields import FieldInfo

from app.core.config import Settings

ENV_EXAMPLE = Path(".env.example")
NESTED_DELIMITER = "__"


def _is_nested(field: FieldInfo) -> bool:
    annotation = field.annotation
    return isinstance(annotation, type) and issubclass(annotation, BaseModel)


def _valid_env_names() -> set[str]:
    """Every env key Settings can accept (top-level + nested ``PARENT__CHILD``)."""
    names: set[str] = set()
    for name, field in Settings.model_fields.items():
        annotation = field.annotation
        if isinstance(annotation, type) and issubclass(annotation, BaseModel):
            names.update(
                f"{name}{NESTED_DELIMITER}{sub}".upper() for sub in annotation.model_fields
            )
        else:
            names.add(name.upper())
    return names


def _required_top_level_names() -> set[str]:
    return {
        name.upper() for name, field in Settings.model_fields.items() if not _is_nested(field)
    }


def main() -> int:
    if not ENV_EXAMPLE.exists():
        print("[check-env] missing .env.example", file=sys.stderr)
        return 1

    text = ENV_EXAMPLE.read_text(encoding="utf-8")
    present = set(re.findall(r"^([A-Z][A-Z0-9_]+)=", text, flags=re.MULTILINE))
    missing = sorted(_required_top_level_names() - present)
    unknown = sorted(present - _valid_env_names())

    ok = True
    if missing:
        ok = False
        print("[check-env] .env.example is missing required Settings fields:")
        for item in missing:
            print(f"  - {item}")
    if unknown:
        ok = False
        print(
            "[check-env] .env.example has keys not backed by a Settings field "
            "(extra='forbid' would reject them at startup):"
        )
        for item in unknown:
            print(f"  - {item}")
    if ok:
        print("[check-env] .env.example and Settings are in sync")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
