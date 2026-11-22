import pytest

from gauntlet.runner import run, verify


def test_good_fixture_scores_and_verifies(tmp_path):
    report = verify(run("repository-reality-check", "demo-good", tmp_path))
    assert report["valid"] is True
    assert report["score"]["score"] == 1


def test_bad_fixture_does_not_get_credit(tmp_path):
    report = verify(run("repository-reality-check", "demo-bad", tmp_path))
    assert report["score"]["score"] == 0
    assert report["score"]["invalid"]


def test_tampering_is_detected(tmp_path):
    bundle = run("repository-reality-check", "demo-good", tmp_path)
    (bundle / "response.json").write_text('{"findings": []}', encoding="utf-8")
    with pytest.raises(ValueError, match="Digest mismatch"):
        verify(bundle)


def test_unknown_agent_is_rejected(tmp_path):
    with pytest.raises(ValueError, match="Unknown bundled agent"):
        run("repository-reality-check", "untrusted-code", tmp_path)
