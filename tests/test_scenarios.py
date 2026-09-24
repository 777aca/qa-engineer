import json
import subprocess
import sys
import pytest
from data_contract import DataError
from scan_lib.scenarios import load_scenarios


def config(tmp_path, steps, **extra):
    path = tmp_path / "scenario.json"
    path.write_text(json.dumps({"schema_version": 1, "scenarios": [{"id": "test", "title": "测试",
                    "module": "模块", "steps": steps, **extra}]}), encoding="utf-8")
    return str(path)


@pytest.mark.parametrize("steps", [
    [{"action": "click", "target": {"role": "button", "name": "保存"}}],
    [{"action": "eval", "value": "alert(1)"}],
    [{"action": "expect_count", "target": {"css": ".row"}, "value": True}],
    [{"action": "expect_visible", "target": {"css": ".row", "label": "混合"}}],
    [{"action": "goto", "value": "https://outside.test"}, {"action": "expect_visible", "target": {"css": "body"}}],
])
def test_invalid_scenarios_rejected_before_browser(tmp_path, steps):
    with pytest.raises(DataError):
        load_scenarios(config(tmp_path, steps), "http://localhost", "L2")


def test_higher_level_scenarios_are_not_executed(tmp_path):
    steps = [{"action": "expect_visible", "target": {"css": "body"}}]
    result = load_scenarios(config(tmp_path, steps, level="L3"), "http://localhost", "L1")
    assert result.checks == []


def test_reproduction_steps_include_targets_and_assertions(tmp_path):
    steps = [{"action": "fill_env", "target": {"label": "密码"}, "value": "QA_TEST_SECRET"},
             {"action": "expect_text", "target": {"test_id": "result"}, "value": "已保存"}]
    spec = load_scenarios(config(tmp_path, steps), "http://localhost", "L2").checks[0]
    assert "QA_TEST_SECRET" in spec.steps[0] and "密码" in spec.steps[0]
    assert "result" in spec.expected[0] and "已保存" in spec.expected[0]


def test_missing_browser_dependency_has_actionable_exit_code():
    result = subprocess.run([sys.executable, "-S", "-X", "utf8", "scripts/scan.py", "--help"],
                            capture_output=True, text=True, encoding="utf-8")
    assert result.returncode == 2
    assert "requirements.txt" in result.stderr
