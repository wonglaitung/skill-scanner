#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TARGETS_DIR = ROOT / "targets"
LOCK_PATH = TARGETS_DIR / "skills.lock.json"
EXCLUDED_SUFFIXES = {".pyc", ".log"}
EXCLUDED_DIRS = {"__pycache__"}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def skill_files(skill_dir: Path) -> list[Path]:
    files = []
    for path in sorted(skill_dir.rglob("*")):
        if not path.is_file():
            continue
        if path.suffix in EXCLUDED_SUFFIXES:
            continue
        if any(part in EXCLUDED_DIRS for part in path.parts):
            continue
        files.append(path)
    return files


def build_skill(skill_dir: Path) -> dict:
    files = {}
    lines = []
    for path in skill_files(skill_dir):
        relative = str(path.relative_to(skill_dir))
        digest = sha256_file(path)
        files[relative] = digest
        lines.append(f"{relative}:{digest}")

    aggregate = hashlib.sha256("\n".join(lines).encode("utf-8")).hexdigest()
    return {"aggregate": aggregate, "files": files}


def load_lock() -> dict:
    if not LOCK_PATH.exists():
        return {"skills": {}}
    return json.loads(LOCK_PATH.read_text(encoding="utf-8"))


def generate() -> int:
    skills = {}
    for skill_dir in sorted(TARGETS_DIR.iterdir()):
        if not skill_dir.is_dir() or not (skill_dir / "SKILL.md").exists():
            continue
        skills[skill_dir.name] = build_skill(skill_dir)

    LOCK_PATH.parent.mkdir(parents=True, exist_ok=True)
    LOCK_PATH.write_text(
        json.dumps({"version": 1, "skills": skills}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"lock written: {LOCK_PATH} ({len(skills)} skills)")
    return 0


def verify(skill: str | None) -> int:
    lock = load_lock()
    locked = lock.get("skills", {})
    names = [skill] if skill else sorted(locked)

    failed = False
    for name in names:
        skill_dir = TARGETS_DIR / name
        if not skill_dir.exists():
            print(f"[FAIL] missing skill: {name}")
            failed = True
            continue
        if name not in locked:
            print(f"[FAIL] no lock entry: {name}")
            failed = True
            continue

        current = build_skill(skill_dir)
        expected = locked[name]
        if current["aggregate"] != expected.get("aggregate"):
            failed = True
            print(f"[FAIL] hash mismatch: {name}")
            old_files = expected.get("files", {})
            new_files = current["files"]
            for path in sorted(set(old_files) | set(new_files)):
                if old_files.get(path) != new_files.get(path):
                    print(f"  - {path}")
        else:
            print(f"[OK] {name}")

    return 1 if failed else 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Skill 文件完整性锁")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("generate")

    verify_parser = sub.add_parser("verify")
    verify_parser.add_argument("--skill", default=None)

    args = parser.parse_args()
    if args.command == "generate":
        return generate()
    return verify(args.skill)


if __name__ == "__main__":
    sys.exit(main())
