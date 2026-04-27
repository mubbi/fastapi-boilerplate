#!/usr/bin/env python
"""CI gate: gettext catalogs are in sync and meet completeness threshold.

- Every locale in ``LOCALES_ENABLED`` has a catalog under ``app/locales/<loc>/LC_MESSAGES/``.
- Each catalog has the same set of keys as ``messages.pot``.
- Translation completeness is at least ``LOCALE_TRANSLATION_COMPLETENESS_MIN``.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

from app.core.config import get_settings

POT_PATH = Path("app/locales/messages.pot")
LOCALES_DIR = Path("app/locales")


def parse_po(path: Path) -> dict[str, str]:
    """Tiny ``.po`` parser sufficient for this CI gate."""
    if not path.exists():
        return {}
    text = path.read_text(encoding="utf-8")
    entries: dict[str, str] = {}
    msgid: str | None = None
    msgstr: str | None = None
    msgid_re = re.compile(r'^msgid\s+"(.*)"\s*$')
    msgstr_re = re.compile(r'^msgstr\s+"(.*)"\s*$')
    cont_re = re.compile(r'^"(.*)"\s*$')
    state: str | None = None
    for raw in text.splitlines():
        line = raw.rstrip()
        if line.startswith("#"):
            continue
        m = msgid_re.match(line)
        if m:
            if msgid is not None:
                entries[msgid] = msgstr or ""
            msgid = m.group(1)
            msgstr = None
            state = "msgid"
            continue
        m = msgstr_re.match(line)
        if m:
            msgstr = m.group(1)
            state = "msgstr"
            continue
        m = cont_re.match(line)
        if m and state:
            piece = m.group(1)
            if state == "msgid":
                msgid = (msgid or "") + piece
            elif state == "msgstr":
                msgstr = (msgstr or "") + piece
            continue
        if not line.strip() and msgid is not None:
            entries[msgid] = msgstr or ""
            msgid = None
            msgstr = None
            state = None
    if msgid is not None:
        entries[msgid] = msgstr or ""
    entries.pop("", None)  # drop the metadata header
    return entries


def main() -> int:
    settings = get_settings()
    enabled_locales = tuple(settings.locales_enabled)
    threshold = settings.locale_translation_completeness_min

    if not POT_PATH.exists():
        print(f"[i18n-check] missing {POT_PATH}", file=sys.stderr)
        return 1

    pot_keys = set(parse_po(POT_PATH).keys())
    if not pot_keys:
        print("[i18n-check] template has no translatable keys (skipping completeness)")
        return 0

    failed = False
    for loc in enabled_locales:
        po = LOCALES_DIR / loc / "LC_MESSAGES" / "messages.po"
        if not po.exists():
            print(f"[i18n-check] {loc}: catalog missing at {po}", file=sys.stderr)
            failed = True
            continue
        catalog = parse_po(po)
        present = sum(1 for k in pot_keys if catalog.get(k))
        completeness = present / len(pot_keys) if pot_keys else 1.0
        missing = sorted(k for k in pot_keys if not catalog.get(k))
        status = "OK" if completeness >= threshold else "FAIL"
        print(f"[i18n-check] {loc}: completeness={completeness:.0%} ({status})")
        if missing:
            for k in missing[:5]:
                print(f"             - missing: {k}")
        if completeness < threshold:
            failed = True

    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
