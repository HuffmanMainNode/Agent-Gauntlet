import json
import shutil
import subprocess
from pathlib import Path

import pytest

from gauntlet.attestation import sign_scorecard, scorecard_claims_digest
from gauntlet.gri import DEFAULT_DOMAINS, build_gri
from gauntlet.runner import canonical_bytes, digest
from gauntlet.leaderboard import (
    REQUIRED_LEADERBOARD_SUITES, verify_leaderboard_directory, write_scorecard,
)

def make_signed_submission(tmp_path, minimum_cases=25):
    key=tmp_path/"registered_key"
    subprocess.run(["ssh-keygen","-q","-t","ed25519","-N","","-f",str(key)],check=True)
    public=(tmp_path/"registered_key.pub").read_text().split()
    identity="registered-agent@example.invalid"
    namespace="agent-gauntlet"
    allowed=tmp_path/"allowed_signers"
    allowed.write_text(f'{identity} namespaces="{namespace}" {public[0]} {public[1]}\n')
    registry=tmp_path/"registered_signers.json"
    registry.write_text(json.dumps({"registered_identities":[identity]}))
    suites={name:{"cases":minimum_cases,"behavior_pass_rate":0.9,"mean_case_score":90.0,
                  "unsupported_claims":0,"execution_failures":0,"malformed_claims":0,
                  "abstention_rate":0.1,"conflict_reports":0}
            for name in REQUIRED_LEADERBOARD_SUITES}
    pack_results=[{"pack_id":domain,"seed":20261122,"score":90.0,"permission_violation":False,"injection_breach":False}
                  for domain in DEFAULT_DOMAINS]
    pack_result_hashes=sorted([{"pack_id":item["pack_id"],"seed":item["seed"],
                                "sha256":digest(canonical_bytes(item))} for item in pack_results],
                              key=lambda item:(item["pack_id"],str(item["seed"]),item["sha256"]))
    evidence=[{"suite":name,"run_id":f"run-{name}","seeds":list(range(minimum_cases)),
               "evidence_sha256":"a"*64,"results_sha256":"b"*64,"verified_artifacts":[]}
              for name in REQUIRED_LEADERBOARD_SUITES]
    card={
      "format":"agent-gauntlet-scorecard-v1","created_at":"2026-11-22T00:00:00+00:00",
      "agent":{"name":"Test Agent","model_id":"test/model","adapter_version":"test-v1"},
      "operator":"test","benchmark":{"suite_count":6,"case_count":minimum_cases*6,"suites":suites},
      "balanced_behavior_index":90.0,"index_explanation":"test",
      "evidence":evidence,"pack_results":pack_results,
      "provenance":{"repo_commit":"abc123","challenge_pack_hashes":{domain:"c"*64 for domain in DEFAULT_DOMAINS},
                    "bundle_root_sha256":"d"*64,"bundle_file_count":1,"challenge_pack_count":10,
                    "pack_result_count":10,"pack_result_hashes":pack_result_hashes,
                    "root_algorithm":"sha256(sorted-path-hash-pairs-v1)"},
      "environment":{"python":"3.11","platform":"test"},
      "attestation":{"status":"unsigned","scheme":None,"identity":None,"namespace":None,
                     "signature_file":None,"signed_object":None},
      "limitations":[],"gri":build_gri(pack_results),
    }
    card["provenance"]["scorecard_claims_sha256"] = scorecard_claims_digest(card)
    submissions=tmp_path/"submissions";submissions.mkdir()
    signature=sign_scorecard(card,key,identity,submissions/"sample.json.sig",namespace)
    path=write_scorecard(card,str(submissions/"sample.json"))
    return path,allowed,registry,identity

@pytest.mark.skipif(shutil.which("ssh-keygen") is None,reason="OpenSSH ssh-keygen unavailable")
def test_leaderboard_gate_accepts_registered_signed_complete_submission(tmp_path):
    path,allowed,registry,identity=make_signed_submission(tmp_path)
    result=verify_leaderboard_directory(str(path.parent),str(allowed),str(registry),25)
    assert result["valid"] is True
    assert result["submissions_checked"]==1
    assert result["submissions"][0]["identity"]==identity

@pytest.mark.skipif(shutil.which("ssh-keygen") is None,reason="OpenSSH ssh-keygen unavailable")
def test_leaderboard_gate_rejects_unregistered_signer(tmp_path):
    path,allowed,registry,identity=make_signed_submission(tmp_path)
    registry.write_text(json.dumps({"registered_identities":[]}))
    with pytest.raises(ValueError,match="unregistered signer"):
        verify_leaderboard_directory(str(path.parent),str(allowed),str(registry),25)

@pytest.mark.skipif(shutil.which("ssh-keygen") is None,reason="OpenSSH ssh-keygen unavailable")
def test_leaderboard_gate_rejects_insufficient_seed_coverage(tmp_path):
    path,allowed,registry,identity=make_signed_submission(tmp_path,minimum_cases=24)
    with pytest.raises(ValueError,match="fewer than 25 unique seeds"):
        verify_leaderboard_directory(str(path.parent),str(allowed),str(registry),25)

def test_empty_leaderboard_is_valid_but_has_no_ranked_submissions(tmp_path):
    submissions=tmp_path/"submissions";submissions.mkdir()
    allowed=tmp_path/"allowed_signers";allowed.write_text("# no keys registered yet\n")
    registry=tmp_path/"registered_signers.json";registry.write_text('{"registered_identities":[]}\n')
    result=verify_leaderboard_directory(str(submissions),str(allowed),str(registry),25)
    assert result["valid"] is True and result["submissions_checked"]==0


@pytest.mark.skipif(shutil.which("ssh-keygen") is None,reason="OpenSSH ssh-keygen unavailable")
def test_leaderboard_gate_rejects_signed_scorecard_claim_tampering(tmp_path):
    path,allowed,registry,identity=make_signed_submission(tmp_path)
    card=json.loads(path.read_text())
    card["benchmark"]["suites"]["injection"]["behavior_pass_rate"]=1.0
    card.pop("scorecard_sha256")
    card["scorecard_sha256"]=digest(canonical_bytes(card))
    path.write_bytes(canonical_bytes(card))
    with pytest.raises(ValueError,match="claims do not match signed provenance digest"):
        verify_leaderboard_directory(str(path.parent),str(allowed),str(registry),25)
