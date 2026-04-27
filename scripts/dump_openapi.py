#!/usr/bin/env python
"""Dump the live OpenAPI document to stdout.

Used in CI for diffing the public API surface across PRs.
"""

from __future__ import annotations

import json

from app.main import create_app


def main() -> int:
    app = create_app()
    print(json.dumps(app.openapi(), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
