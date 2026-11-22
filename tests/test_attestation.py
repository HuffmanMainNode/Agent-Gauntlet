import json
import shutil
import subprocess
from pathlib import Path

import pytest

from gauntlet.attestation import (
    AttestationError, build_provenance, sign_scorecard, verify_scorecard_signature, scorecard_claims_digest,
)
from gauntlet.adversarial_runner import run_suite
from gauntlet.leaderboard import build_scorecard, verify_scorecard, write_scorecard

ROOT=Path(__file__).parents[1]

def make_bundle(tmp_path):
    import sys
    code="import json,sys; json.load(sys.stdin); print(json.dumps({'claims': [], 'abstain': True}))"
    return run_suite("hallucination",[sys.executable,"-c",code],[17,18],tmp_path/"runs",
                    agent_name="Attested Agent",model_id="example/model-v1",
                    adapter_version="adapter-1")

def test_provenance_root_is_deterministic_and_commits_to_source_and_packs(tmp_path):
    bundle=make_bundle(tmp_path)
    first=build_provenance([str(bundle)],repo_root=ROOT,repo_commit="abc123")
    second=build_provenance([str(bundle)],repo_root=ROOT,repo_commit="abc123")
    assert first==second
    assert first["bundle_root_sha256"] and len(first["bundle_root_sha256"])==64
    assert first["challenge_pack_count"]==10
    changed_commit=build_provenance([str(bundle)],repo_root=ROOT,repo_commit="def456")
    assert changed_commit["bundle_root_sha256"]!=first["bundle_root_sha256"]
    assert changed_commit["challenge_pack_hashes"]==first["challenge_pack_hashes"]

def test_bundle_content_changes_provenance_root(tmp_path):
    bundle=make_bundle(tmp_path)
    before=build_provenance([str(bundle)],repo_root=ROOT,repo_commit="abc123")
    with (bundle/"summary.json").open("ab") as handle:
        handle.write(b"tamper")
    after=build_provenance([str(bundle)],repo_root=ROOT,repo_commit="abc123")
    assert before["bundle_root_sha256"]!=after["bundle_root_sha256"]

def test_symlink_in_bundle_is_rejected(tmp_path):
    bundle=make_bundle(tmp_path)
    target=tmp_path/"outside.txt";target.write_text("outside")
    link=bundle/"outside-link"
    try:
        link.symlink_to(target)
    except OSError:
        pytest.skip("symlink creation unavailable")
    with pytest.raises(AttestationError,match="symlinks"):
        build_provenance([str(bundle)],repo_root=ROOT,repo_commit="abc123")

@pytest.mark.skipif(shutil.which("ssh-keygen") is None,reason="OpenSSH ssh-keygen unavailable")
def test_openssh_sign_and_verify_scorecard_root(tmp_path):
    bundle=make_bundle(tmp_path)
    card=build_scorecard([str(bundle)],"Attested Agent","example/model-v1","adapter-1")
    key=tmp_path/"signing_key"
    subprocess.run(["ssh-keygen","-q","-t","ed25519","-N","","-f",str(key)],check=True)
    pub=(tmp_path/"signing_key.pub").read_text().split()
    identity="ci-agent@example.invalid"
    namespace="agent-gauntlet"
    allowed=tmp_path/"allowed_signers"
    allowed.write_text(f'{identity} namespaces="{namespace}" {pub[0]} {pub[1]}\n')
    signature=sign_scorecard(card,key,identity,tmp_path/"scorecard.json.sig",namespace)
    scorecard_path=write_scorecard(card,str(tmp_path/"scorecard.json"))
    report=verify_scorecard(str(scorecard_path),str(signature),str(allowed),identity,namespace)
    assert report["valid"] is True
    assert report["attestation"]=="verified"
    assert report["signature"]["signed_object"]=="bundle_root_sha256"

@pytest.mark.skipif(shutil.which("ssh-keygen") is None,reason="OpenSSH ssh-keygen unavailable")
def test_tampered_provenance_fails_signature_verification(tmp_path):
    bundle=make_bundle(tmp_path)
    card=build_scorecard([str(bundle)],"Attested Agent","example/model-v1","adapter-1")
    key=tmp_path/"signing_key"
    subprocess.run(["ssh-keygen","-q","-t","ed25519","-N","","-f",str(key)],check=True)
    pub=(tmp_path/"signing_key.pub").read_text().split()
    identity="ci-agent@example.invalid";namespace="agent-gauntlet"
    allowed=tmp_path/"allowed_signers"
    allowed.write_text(f'{identity} namespaces="{namespace}" {pub[0]} {pub[1]}\n')
    signature=sign_scorecard(card,key,identity,tmp_path/"scorecard.json.sig",namespace)
    card["provenance"]["repo_commit"]="forged-commit"
    with pytest.raises(AttestationError,match="verification failed"):
        verify_scorecard_signature(card,signature,allowed,identity,namespace)

def test_bundle_order_does_not_change_canonical_root(tmp_path):
    first=make_bundle(tmp_path/"first")
    second=make_bundle(tmp_path/"second")
    a=build_provenance([str(first),str(second)],repo_root=ROOT,repo_commit="stable")
    b=build_provenance([str(second),str(first)],repo_root=ROOT,repo_commit="stable")
    assert a["bundle_root_sha256"]==b["bundle_root_sha256"]

@pytest.mark.skipif(shutil.which("ssh-keygen") is None,reason="OpenSSH ssh-keygen unavailable")
def test_scorecard_cli_signs_and_verifies(tmp_path):
    import sys
    bundle=make_bundle(tmp_path)
    key=tmp_path/"cli_key"
    subprocess.run(["ssh-keygen","-q","-t","ed25519","-N","","-f",str(key)],check=True)
    pub=(tmp_path/"cli_key.pub").read_text().split()
    identity="cli-agent@example.invalid";namespace="agent-gauntlet"
    allowed=tmp_path/"cli_allowed_signers"
    allowed.write_text(f'{identity} namespaces="{namespace}" {pub[0]} {pub[1]}\n')
    card=tmp_path/"signed-card.json"
    created=subprocess.run([
        sys.executable,"-m","gauntlet","scorecard","--bundle",str(bundle),
        "--agent-name","Attested Agent","--model-id","example/model-v1",
        "--adapter-version","adapter-1","--signing-key",str(key),
        "--signer-identity",identity,"--output",str(card)
    ],cwd=ROOT,capture_output=True,text=True,check=False)
    assert created.returncode==0,created.stderr
    verified=subprocess.run([
        sys.executable,"-m","gauntlet","verify-scorecard","--scorecard",str(card),
        "--signature",str(card)+".sig","--allowed-signers",str(allowed),
        "--signer-identity",identity
    ],cwd=ROOT,capture_output=True,text=True,check=False)
    assert verified.returncode==0,verified.stderr
    assert json.loads(verified.stdout)["attestation"]=="verified"


def test_scorecard_recomputes_gri_and_binds_embedded_pack_results(tmp_path):
    import hashlib
    from gauntlet.runner import canonical_bytes
    from gauntlet.gri import build_gri, DEFAULT_DOMAINS
    bundle=make_bundle(tmp_path)
    result=tmp_path/"evidence-integrity.json"
    result.write_text(json.dumps({"pack_id":"evidence-integrity","seed":1,"score":88,
                                  "permission_violation":False,"injection_breach":False}))
    card=build_scorecard([str(bundle)],"Attested Agent","example/model-v1","adapter-1",
                         pack_result_paths=[str(result)])
    path=write_scorecard(card,str(tmp_path/"scorecard.json"))
    valid=verify_scorecard(str(path))
    assert valid["valid"] is True
    data=json.loads(path.read_text(encoding="utf-8"))
    data["pack_results"][0]["score"]=100
    data["gri"]=build_gri(data["pack_results"], DEFAULT_DOMAINS)
    data.pop("scorecard_sha256")
    data["scorecard_sha256"]=hashlib.sha256(canonical_bytes(data)).hexdigest()
    path.write_bytes(canonical_bytes(data))
    with pytest.raises(ValueError,match="signed provenance hashes"):
        verify_scorecard(str(path))


@pytest.mark.skipif(shutil.which("ssh-keygen") is None,reason="OpenSSH ssh-keygen unavailable")
def test_signature_binds_suite_and_evidence_claims(tmp_path):
    bundle=make_bundle(tmp_path)
    card=build_scorecard([str(bundle)],"Attested Agent","example/model-v1","adapter-1")
    key=tmp_path/"claims_key"
    subprocess.run(["ssh-keygen","-q","-t","ed25519","-N","","-f",str(key)],check=True)
    pub=(tmp_path/"claims_key.pub").read_text().split()
    identity="claims-agent@example.invalid";namespace="agent-gauntlet"
    allowed=tmp_path/"claims_allowed"
    allowed.write_text(f'{identity} namespaces="{namespace}" {pub[0]} {pub[1]}\\n')
    card["provenance"]["scorecard_claims_sha256"]=scorecard_claims_digest(card)
    signature=sign_scorecard(card,key,identity,tmp_path/"claims.json.sig",namespace)
    card["benchmark"]["suites"]["hallucination"]["behavior_pass_rate"]=1.0
    with pytest.raises(AttestationError,match="claims do not match"):
        verify_scorecard_signature(card,signature,allowed,identity,namespace)
