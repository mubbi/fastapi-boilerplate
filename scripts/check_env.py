#!/usr/bin/env python
"""CI gate for basic environment-file drift."""

from __future__ import annotations

import re
import sys
from pathlib import Path

from app.core.config import Settings

ENV_EXAMPLE = Path(".env.example")


def _env_name(field_name: str) -> str:
    return field_name.upper()


def main() -> int:
    if not ENV_EXAMPLE.exists():
        print("[check-env] missing .env.example", file=sys.stderr)
        return 1

    text = ENV_EXAMPLE.read_text(encoding="utf-8")
    present = set(re.findall(r"^([A-Z][A-Z0-9_]+)=", text, flags=re.MULTILINE))
    required = {
        _env_name(name)
        for name, field in Settings.model_fields.items()
        if not field_name_is_nested(name)
    }
    missing = sorted(required - present)
    if missing:
        print("[check-env] .env.example is missing:")
        for item in missing:
            print(f"  - {item}")
        return 1
    print("[check-env] .env.example covers Settings fields")
    return 0


def field_name_is_nested(name: str) -> bool:
    return name in {"database", "redis", "http_client"}


if __name__ == "__main__":
    raise SystemExit(main())
