#!/usr/bin/env python3
from __future__ import annotations

import argparse
import base64
import sys
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)

ROOT = Path(__file__).resolve().parents[1]
LOCK_PATH = ROOT / "evals" / "skills.lock.json"
SIG_PATH = ROOT / "evals" / "skills.lock.sig"


def keygen(private_path: Path, public_path: Path) -> int:
    private_key = Ed25519PrivateKey.generate()
    private_path.write_bytes(
        private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        )
    )
    private_path.chmod(0o600)
    public_path.write_bytes(
        private_key.public_key().public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )
    )
    print(f"private key: {private_path}")
    print(f"public key:  {public_path}")
    return 0


def sign(key_path: Path, lock_path: Path, sig_path: Path) -> int:
    private_key = serialization.load_pem_private_key(
        key_path.read_bytes(), password=None
    )
    signature = private_key.sign(lock_path.read_bytes())
    sig_path.write_text(base64.b64encode(signature).decode("ascii") + "\n", encoding="ascii")
    print(f"signature written: {sig_path}")
    return 0


def verify(public_path: Path, lock_path: Path, sig_path: Path) -> int:
    public_key: Ed25519PublicKey = serialization.load_pem_public_key(
        public_path.read_bytes()
    )
    signature = base64.b64decode(sig_path.read_text(encoding="ascii").strip())
    try:
        public_key.verify(signature, lock_path.read_bytes())
    except Exception as exc:  # noqa: BLE001
        print(f"[FAIL] signature verification failed: {exc}")
        return 1
    print("[OK] signature verified")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Skill lock 签名工具")
    sub = parser.add_subparsers(dest="command", required=True)

    keygen_parser = sub.add_parser("keygen")
    keygen_parser.add_argument("--private", type=Path, required=True)
    keygen_parser.add_argument("--public", type=Path, required=True)

    sign_parser = sub.add_parser("sign")
    sign_parser.add_argument("--key", type=Path, required=True)
    sign_parser.add_argument("--lock", type=Path, default=LOCK_PATH)
    sign_parser.add_argument("--sig", type=Path, default=SIG_PATH)

    verify_parser = sub.add_parser("verify")
    verify_parser.add_argument("--public", type=Path, required=True)
    verify_parser.add_argument("--lock", type=Path, default=LOCK_PATH)
    verify_parser.add_argument("--sig", type=Path, default=SIG_PATH)

    args = parser.parse_args()
    if args.command == "keygen":
        return keygen(args.private, args.public)
    if args.command == "sign":
        return sign(args.key, args.lock, args.sig)
    return verify(args.public, args.lock, args.sig)


if __name__ == "__main__":
    sys.exit(main())
