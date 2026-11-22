import json
import sys

import pytest

from gauntlet.adapters import invoke_command


def test_adapter_receives_json_and_returns_json():
    code = "import json,sys; x=json.load(sys.stdin); print(json.dumps({'echo': x['suite']}))"
    assert invoke_command([sys.executable, "-c", code], {"suite": "test"}) == {"echo": "test"}


def test_adapter_timeout_is_reported():
    code = "import time; time.sleep(2)"
    with pytest.raises(ValueError, match="timed out"):
        invoke_command([sys.executable, "-c", code], {}, timeout_seconds=1)


def test_adapter_rejects_non_json_output():
    code = "print('not-json')"
    with pytest.raises(ValueError, match="JSON"):
        invoke_command([sys.executable, "-c", code], {})
