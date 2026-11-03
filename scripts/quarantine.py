from __future__ import annotations

import json
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PATH = ROOT / "evals" / "quarantine.json"


def load(path: Path | None = None) -> dict:
    target = Path(path) if path else DEFAULT_PATH
    if not target.exists():
        return {"version": 1, "skills": {}}
    try:
        data = json.loads(target.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {"version": 1, "skills": {}}
    if not isinstance(data, dict):
        return {"version": 1, "skills": {}}
    data.setdefault("version", 1)
    data.setdefault("skills", {})
    return data


def active_entries(skill: str, path: Path | None = None, today: date | None = None) -> list[dict]:
    data = load(path)
    today = today or date.today()
    entries = []
    for entry in data.get("skills", {}).get(skill, []):
        expires = entry.get("expires")
        if expires:
            try:
                if date.fromisoformat(expires) < today:
                    continue
            except ValueError:
                continue
        entries.append(entry)
    return entries


def match(entries: list[dict], input_text: str | None) -> dict | None:
    if not input_text:
        return None
    for entry in entries:
        case = entry.get("case") or entry.get("input")
        if case == input_text:
            return entry
    return None
