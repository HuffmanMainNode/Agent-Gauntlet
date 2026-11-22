"""OpenSSH detached attestations for canonical Agent Gauntlet bundle roots.

A valid signature proves that a key holder signed a digest. It does not prove
agent identity, truthful behavior, safe execution, or the semantic validity of results.
"""
from __future__ import annotations
import hashlib
import json
import re
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
            if path.is_symlink():
                raise AttestationError(f"symlink in challenge pack: {path}")
            if path.is_file():
                entries.append({"path": filename, "sha256": digest(path.read_bytes())})
        hashes[folder.name] = digest(canonical_bytes(entries))
    return hashes


def build_provenance(bundle_paths: list[str], repo_root: str | Path | None = None,
                     repo_commit: str | None = None,
                     additional_files: list[str] | None = None) -> dict[str, Any]:
    if not bundle_paths:
        raise AttestationError("at least one evidence bundle is required")
    root = Path(repo_root) if repo_root is not None else Path(__file__).resolve().parents[2]
    commit = _repo_commit(root, repo_commit)
    packs = _challenge_hashes(root)
    entries = [{"path": "repository/commit", "sha256": digest(commit.encode("utf-8"))}]
    for pack_id, pack_hash in sorted(packs.items()):
        entries.append({"path": f"challenge-packs/{pack_id}", "sha256": pack_hash})
    resolved_bundles = []
    for raw in bundle_paths:
        candidate = Path(raw)
        if candidate.is_symlink():
            raise AttestationError(f"evidence bundle root may not be a symlink: {candidate}")
        bundle = candidate.resolve()
        if not bundle.is_dir():
            raise AttestationError(f"evidence bundle not found: {bundle}")
        try:
            evidence = json.loads((bundle / "evidence.json").read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            raise AttestationError(f"bundle has no readable evidence manifest: {bundle}") from exc
        if not isinstance(evidence, dict):
            raise AttestationError(f"evidence manifest must be an object: {bundle}")
        raw_suite = str(evidence.get("suite") or evidence.get("challenge_id") or "bundle")
        raw_run_id = str(evidence.get("run_id") or digest((bundle / "evidence.json").read_bytes())[:16])
        suite = raw_suite if re.fullmatch(r"[A-Za-z0-9_.-]{1,80}", raw_suite) and ".." not in raw_suite else "suite-" + digest(raw_suite.encode())[:16]
        run_id = raw_run_id if re.fullmatch(r"[A-Za-z0-9_.-]{1,80}", raw_run_id) and ".." not in raw_run_id else "run-" + digest(raw_run_id.encode())[:16]
        resolved_bundles.append((suite, run_id, bundle))
    for suite, run_id, bundle in sorted(resolved_bundles, key=lambda item: (item[0], item[1])):
        for path in sorted(bundle.rglob("*")):
            if path.is_symlink():
                raise AttestationError(f"symlinks are not accepted in evidence bundles: {path}")
            if path.is_file():
                relative = path.relative_to(bundle).as_posix()
                entries.append({
                    "path": f"bundles/{suite}/{run_id}/{relative}",
                    "sha256": digest(path.read_bytes()),
                })
    pack_result_count = 0
    for raw in additional_files or []:
        candidate = Path(raw)
        if candidate.is_symlink() or not candidate.is_file():
            raise AttestationError(f"additional provenance file missing or symlinked: {candidate}")
        raw_bytes = candidate.read_bytes()
        try:
            result = json.loads(raw_bytes.decode("utf-8"))
        except (UnicodeError, json.JSONDecodeError) as exc:
            raise AttestationError(f"additional provenance file is not valid JSON: {candidate}") from exc
        if not isinstance(result, dict) or not isinstance(result.get("pack_id"), str):
            raise AttestationError(f"additional provenance file lacks a pack_id: {candidate}")
        pack_id = result["pack_id"]
        if not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", pack_id) or pack_id not in packs:
            raise AttestationError("additional provenance file has an unknown or invalid pack_id")
        raw_seed = str(result.get("seed", "unspecified"))
        seed = raw_seed if re.fullmatch(r"[A-Za-z0-9_.-]{1,80}", raw_seed) and ".." not in raw_seed else "seed-" + digest(raw_seed.encode())[:16]
        entries.append({"path": f"pack-results/{pack_id}/seed-{seed}/{digest(raw_bytes)}.json",
                        "sha256": digest(raw_bytes)})
        pack_result_count += 1
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
        "pack_result_count": pack_result_count,
        "root_algorithm": "sha256(sorted-path-hash-pairs-v1)",
    }


def attestation_payload(provenance: dict[str, Any]) -> bytes:
    required = {"repo_commit", "challenge_pack_hashes", "bundle_root_sha256", "root_algorithm", "pack_result_count"}
    if not isinstance(provenance, dict) or not required <= provenance.keys():
        raise AttestationError("provenance is incomplete")
    root_hash = provenance["bundle_root_sha256"]
    if not isinstance(root_hash, str) or len(root_hash) != 64 or any(c not in "0123456789abcdef" for c in root_hash):
        raise AttestationError("bundle_root_sha256 must be a lowercase SHA-256 digest")
    if not isinstance(provenance["repo_commit"], str) or not provenance["repo_commit"]:
        raise AttestationError("repo_commit must be a non-empty string")
    pack_hashes = provenance["challenge_pack_hashes"]
    if not isinstance(pack_hashes, dict) or any(
        not isinstance(name, str) or not isinstance(value, str) or len(value) != 64
        or any(char not in "0123456789abcdef" for char in value)
        for name, value in pack_hashes.items()
    ):
        raise AttestationError("challenge_pack_hashes must map pack IDs to SHA-256 digests")
    if provenance["root_algorithm"] != "sha256(sorted-path-hash-pairs-v1)":
        raise AttestationError("unsupported provenance root algorithm")
    return canonical_bytes({
        "format": ATTESTATION_FORMAT,
        "repo_commit": provenance["repo_commit"],
        "challenge_pack_hashes": provenance["challenge_pack_hashes"],
        "bundle_root_sha256": root_hash,
        "root_algorithm": provenance["root_algorithm"],
        "pack_result_count": provenance["pack_result_count"],
    })


def sign_scorecard(scorecard: dict, private_key: str | Path, identity: str,
                   signature_path: str | Path, namespace: str = NAMESPACE) -> Path:
    if not identity or not namespace or len(identity) > 256 or not re.fullmatch(r"[A-Za-z0-9_.@+-]+", identity) or not re.fullmatch(r"[A-Za-z0-9_.@+-]+", namespace):
        raise AttestationError("valid signer identity and namespace are required")
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
        try:
            result = subprocess.run(
                [executable, "-Y", "sign", "-f", str(key), "-n", namespace, str(payload_file)],
                capture_output=True, text=True, timeout=30, check=False,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise AttestationError(f"ssh-keygen signing could not complete: {exc}") from exc
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
    metadata = scorecard.get("attestation", {})
    if (not isinstance(metadata, dict) or metadata.get("status") != "signed"
            or metadata.get("scheme") != "openssh-ssh-keygen-y"
            or metadata.get("identity") != identity
            or metadata.get("namespace") != namespace
            or metadata.get("signed_object") != "bundle_root_sha256"):
        raise AttestationError("scorecard signature metadata does not match the requested signer")
    executable = shutil.which("ssh-keygen")
    if not executable:
        raise AttestationError("ssh-keygen is required for OpenSSH verification")
    signature = Path(signature_path).expanduser().resolve()
    signers = Path(allowed_signers).expanduser().resolve()
    if not signature.is_file() or not signers.is_file():
        raise AttestationError("signature or allowed_signers file not found")
    payload = attestation_payload(scorecard.get("provenance", {}))
    try:
        result = subprocess.run(
            [executable, "-Y", "verify", "-f", str(signers), "-I", identity,
             "-n", namespace, "-s", str(signature)],
            input=payload, capture_output=True, timeout=30, check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise AttestationError(f"ssh-keygen verification could not complete: {exc}") from exc
    if result.returncode != 0:
        message = result.stderr.decode("utf-8", errors="replace").strip()
        raise AttestationError(f"OpenSSH signature verification failed: {message}")
    return {"valid": True, "identity": identity, "namespace": namespace,
            "bundle_root_sha256": scorecard["provenance"]["bundle_root_sha256"],
            "signed_object": "bundle_root_sha256"}
