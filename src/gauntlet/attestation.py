"""OpenSSH detached attestations for canonical Agent Gauntlet bundle roots.

A valid signature proves that a key holder signed a digest. It does not prove
agent identity, truthful behavior, safe execution, or the semantic validity of results.
"""
from __future__ import annotations
import hashlib
import json
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any

from .runner import canonical_bytes, digest

NAMESPACE = "agent-gauntlet"
ATTESTATION_FORMAT = "agent-gauntlet-attestation-v1"
PACK_FILES = ("challenge.json", "fixture.json", "expected.json")


class AttestationError(ValueError):
    """Invalid provenance or failed OpenSSH signature operation."""


def _repo_commit(repo_root: Path, supplied: str | None = None) -> str:
    if supplied is not None:
        if not isinstance(supplied, str) or not supplied.strip():
            raise AttestationError("repo_commit must be a non-empty string")
        return supplied.strip()
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=repo_root, capture_output=True,
            text=True, timeout=5, check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return "unknown"
    value = result.stdout.strip()
    return value if result.returncode == 0 and value else "unknown"


def _challenge_hashes(repo_root: Path) -> dict[str, str]:
    root = repo_root / "challenges"
    hashes = {}
    if not root.is_dir():
        return hashes
    for folder in sorted(root.iterdir(), key=lambda item: item.name):
        manifest = folder / "challenge.json"
        if not folder.is_dir() or not manifest.is_file():
            continue
        try:
            data = json.loads(manifest.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError):
            continue
        if not isinstance(data.get("scoring"), dict) or data["scoring"].get("contract") != "declarative-challenge-v1":
            continue
        entries = []
        for filename in PACK_FILES:
            path = folder / filename
            if path.is_file() and not path.is_symlink():
                entries.append({"path": filename, "sha256": digest(path.read_bytes())})
        hashes[folder.name] = digest(canonical_bytes(entries))
    return hashes


def build_provenance(bundle_paths: list[str], repo_root: str | Path | None = None,
                     repo_commit: str | None = None) -> dict[str, Any]:
    if not bundle_paths:
        raise AttestationError("at least one evidence bundle is required")
    root = Path(repo_root) if repo_root is not None else Path(__file__).resolve().parents[2]
    commit = _repo_commit(root, repo_commit)
    packs = _challenge_hashes(root)
    entries = [{"path": "repository/commit", "sha256": digest(commit.encode("utf-8"))}]
    for pack_id, pack_hash in sorted(packs.items()):
        entries.append({"path": f"challenge-packs/{pack_id}", "sha256": pack_hash})
    resolved_bundles = sorted(Path(raw).resolve() for raw in bundle_paths)
    for index, bundle in enumerate(resolved_bundles):
        if not bundle.is_dir():
            raise AttestationError(f"evidence bundle not found: {bundle}")
        for path in sorted(bundle.rglob("*")):
            if path.is_symlink():
                raise AttestationError(f"symlinks are not accepted in evidence bundles: {path}")
            if path.is_file():
                relative = path.relative_to(bundle).as_posix()
                entries.append({
                    "path": f"bundles/{index:04d}/{bundle.name}/{relative}",
                    "sha256": digest(path.read_bytes()),
                })
    entries.sort(key=lambda item: item["path"])
    if len({item["path"] for item in entries}) != len(entries):
        raise AttestationError("provenance contains duplicate canonical paths")
    root_hash = digest(canonical_bytes(entries))
    return {
        "repo_commit": commit,
        "challenge_pack_hashes": packs,
        "bundle_root_sha256": root_hash,
        "bundle_file_count": sum(1 for item in entries if item["path"].startswith("bundles/")),
        "challenge_pack_count": len(packs),
        "root_algorithm": "sha256(sorted-path-hash-pairs-v1)",
    }


def attestation_payload(provenance: dict[str, Any]) -> bytes:
    required = {"repo_commit", "challenge_pack_hashes", "bundle_root_sha256", "root_algorithm"}
    if not isinstance(provenance, dict) or not required <= provenance.keys():
        raise AttestationError("provenance is incomplete")
    root_hash = provenance["bundle_root_sha256"]
    if not isinstance(root_hash, str) or len(root_hash) != 64 or any(c not in "0123456789abcdef" for c in root_hash):
        raise AttestationError("bundle_root_sha256 must be a lowercase SHA-256 digest")
    return canonical_bytes({
        "format": ATTESTATION_FORMAT,
        "repo_commit": provenance["repo_commit"],
        "challenge_pack_hashes": provenance["challenge_pack_hashes"],
        "bundle_root_sha256": root_hash,
        "root_algorithm": provenance["root_algorithm"],
    })


def sign_scorecard(scorecard: dict, private_key: str | Path, identity: str,
                   signature_path: str | Path, namespace: str = NAMESPACE) -> Path:
    if not identity or not namespace:
        raise AttestationError("signer identity and namespace are required")
    executable = shutil.which("ssh-keygen")
    if not executable:
        raise AttestationError("ssh-keygen is required for OpenSSH attestations")
    key = Path(private_key).expanduser().resolve()
    if not key.is_file():
        raise AttestationError(f"private key not found: {key}")
    payload = attestation_payload(scorecard.get("provenance", {}))
    destination = Path(signature_path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="gauntlet-attest-") as directory:
        payload_file = Path(directory) / "attestation.json"
        payload_file.write_bytes(payload)
        result = subprocess.run(
            [executable, "-Y", "sign", "-f", str(key), "-n", namespace, str(payload_file)],
            capture_output=True, text=True, timeout=30, check=False,
        )
        generated = Path(str(payload_file) + ".sig")
        if result.returncode != 0 or not generated.is_file():
            raise AttestationError(f"ssh-keygen signing failed: {result.stderr.strip()}")
        destination.write_bytes(generated.read_bytes())
    scorecard["attestation"] = {
        "status": "signed",
        "scheme": "openssh-ssh-keygen-y",
        "identity": identity,
        "namespace": namespace,
        "signature_file": destination.name,
        "signed_object": "bundle_root_sha256",
    }
    scorecard.pop("scorecard_sha256", None)
    scorecard["scorecard_sha256"] = digest(canonical_bytes(scorecard))
    return destination


def verify_scorecard_signature(scorecard: dict, signature_path: str | Path,
                               allowed_signers: str | Path, identity: str,
                               namespace: str = NAMESPACE) -> dict:
    executable = shutil.which("ssh-keygen")
    if not executable:
        raise AttestationError("ssh-keygen is required for OpenSSH verification")
    signature = Path(signature_path).expanduser().resolve()
    signers = Path(allowed_signers).expanduser().resolve()
    if not signature.is_file() or not signers.is_file():
        raise AttestationError("signature or allowed_signers file not found")
    payload = attestation_payload(scorecard.get("provenance", {}))
    result = subprocess.run(
        [executable, "-Y", "verify", "-f", str(signers), "-I", identity,
         "-n", namespace, "-s", str(signature)],
        input=payload, capture_output=True, timeout=30, check=False,
    )
    if result.returncode != 0:
        message = result.stderr.decode("utf-8", errors="replace").strip()
        raise AttestationError(f"OpenSSH signature verification failed: {message}")
    return {"valid": True, "identity": identity, "namespace": namespace,
            "bundle_root_sha256": scorecard["provenance"]["bundle_root_sha256"],
            "signed_object": "bundle_root_sha256"}
