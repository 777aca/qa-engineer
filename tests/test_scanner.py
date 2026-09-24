import json
import subprocess
import sys

import pytest
from playwright.sync_api import expect
from scan_lib.common import CheckSpec, Outcome
from scan_lib.l0_smoke import CHECKS as SMOKE
from scan_lib.l1_happy import CHECKS as LOGIN
from scan_lib.l2_loop import CHECKS as LOOP
from scan_lib.l3_detail import CHECKS as DETAIL
from scan_lib.l4_full import CHECKS as FULL
from scan_lib.redaction import Redactor
from scan_lib.runner import RunOptions, execute_checks
from scan_lib.scenarios import load_scenarios
from scan import export_report

pytestmark = pytest.mark.browser


def run(browser, site, tmp_path, specs, path="/good", **kwargs):
    return execute_checks(browser, site[0] + path, "pc", tmp_path, specs,
                          RunOptions(timeout_ms=2500, **kwargs), Redactor())


def test_valid_email_form_disabled_button_decorative_image(browser, site, tmp_path):
    specs = [LOGIN[0], LOOP[0], DETAIL[3], FULL[2]]
    report = run(browser, site, tmp_path, specs, allow_submit=True)
    assert [item.result for item in report.checks] == ["Pass", "Pass", "Skipped", "Pass"]
    assert report.findings == []


def test_native_required_validation_is_accepted(browser, site, tmp_path):
    report = run(browser, site, tmp_path, [LOOP[0]], path="/native", allow_submit=True)
    assert report.checks[0].result == "Pass"


def test_short_html_is_not_a_white_screen(browser, site, tmp_path):
    report = run(browser, site, tmp_path, [SMOKE[0]], path="/blank")
    assert report.checks[0].result == "Pass"


def test_missing_image_alt_checked_without_inputs(browser, site, tmp_path):
    report = run(browser, site, tmp_path, [FULL[2]], path="/images")
    assert report.checks[0].result == "NeedsReview"
    assert len(report.findings) == 1


def test_exceptions_cannot_look_like_success(browser, site, tmp_path):
    def broken(ctx):
        raise RuntimeError("runner failed")
    report = run(browser, site, tmp_path, [CheckSpec("broken", "失败检查", "L0", broken)])
    assert report.checks[0].result == "Error"
    assert report.exit_code() == 2


def test_none_return_is_execution_error(browser, site, tmp_path):
    report = run(browser, site, tmp_path, [CheckSpec("none", "无结果", "L0", lambda ctx: None)])
    assert report.checks[0].result == "Error"


def test_environment_failure_blocks_dependent_checks(browser, site, tmp_path):
    report = run(browser, site, tmp_path, SMOKE, path="/broken")
    assert [item.result for item in report.checks] == ["Error", "Blocked", "Blocked"]


def test_checks_have_isolated_storage(browser, site, tmp_path):
    def change(ctx):
        ctx.page.evaluate("localStorage.setItem('modified', 'yes')")
        return Outcome("Pass", "设置测试状态")
    def verify(ctx):
        assert ctx.page.evaluate("localStorage.getItem('modified')") is None
        return Outcome("Pass", "状态隔离有效")
    report = run(browser, site, tmp_path, [CheckSpec("change", "修改", "L0", change), CheckSpec("verify", "隔离", "L0", verify)])
    assert report.exit_code() == 0


def test_storage_check_and_console_do_not_export_values(browser, site, tmp_path):
    report = run(browser, site, tmp_path, [FULL[3]], path="/leak")
    export_report(report, site[0] + "/leak", "L4", "pc", tmp_path, Redactor())
    texts = "\n".join(p.read_text(encoding="utf-8") for p in tmp_path.glob("*.json"))
    assert "FAKE-CREDENTIAL" not in texts
    assert report.findings[0].status == "待验证"
    assert (tmp_path / "test-cases.xlsx").exists()


def test_authorization_guard_blocks_post_and_active_checks(browser, site, tmp_path):
    initial = site[1]["posts"]
    report = run(browser, site, tmp_path, [SMOKE[0]], path="/post")
    assert report.checks[0].result == "Blocked"
    assert site[1]["posts"] == initial
    report = run(browser, site, tmp_path, [LOGIN[1], FULL[0]])
    assert all(item.result == "Blocked" for item in report.checks)


def test_real_business_search_and_save_reload(browser, site, tmp_path):
    url = site[0] + "/app"
    config = load_scenarios("samples/scenarios.yaml", url, "L2")
    report = execute_checks(browser, url, "pc", tmp_path, config.checks,
                            RunOptions(allow_submit=True, timeout_ms=2500), Redactor())
    assert [item.result for item in report.checks] == ["Pass", "Pass"]


def test_failed_assertion_retains_trace_and_confirmed_evidence(browser, site, tmp_path):
    def fail(ctx):
        expect(ctx.page.locator("body")).to_have_text("不存在的结果", timeout=100)
        return Outcome("Pass", "不应到达")
    report = run(browser, site, tmp_path, [CheckSpec("assertion", "业务断言", "L1", fail)], trace=True)
    assert report.checks[0].result == "Fail"
    assert report.findings[0].status == "已确认"
    assert report.findings[0].reproducible == "一次"
    assert (tmp_path / "private-traces" / "assertion.zip").exists()
    assert report.exit_code() == 1


def test_missing_account_is_blocked(browser, site, tmp_path, monkeypatch):
    monkeypatch.delenv("TEST_USER", raising=False)
    monkeypatch.delenv("TEST_PASS", raising=False)
    report = run(browser, site, tmp_path, [LOGIN[1]], allow_submit=True)
    assert report.checks[0].result == "Blocked"


def test_cli_two_platforms_export_independent_records(site, tmp_path):
    result = subprocess.run([sys.executable, "-X", "utf8", "scripts/scan.py", "--url", site[0] + "/blank", "--level", "L0", "--platform", "both", "--out-dir", str(tmp_path)], capture_output=True, text=True, encoding="utf-8")
    assert result.returncode == 0, result.stdout + result.stderr
    cases = json.loads((tmp_path / "test-cases.json").read_text(encoding="utf-8"))["cases"]
    assert len(cases) == 6
    assert {case["platform"] for case in cases} == {"pc", "mobile"}
    assert len({case["id"] for case in cases}) == 6


def test_cli_l2_requires_business_coverage(site, tmp_path):
    result = subprocess.run([sys.executable, "-X", "utf8", "scripts/scan.py", "--url", site[0] + "/blank", "--level", "L2", "--out-dir", str(tmp_path)], capture_output=True, text=True, encoding="utf-8")
    assert result.returncode == 2, result.stdout + result.stderr
    cases = json.loads((tmp_path / "test-cases.json").read_text(encoding="utf-8"))["cases"]
    assert any(case["id"] == "business-coverage-pc" and case["result"] == "Blocked" for case in cases)


def test_screenshot_failure_does_not_publish_missing_image(browser, site, tmp_path, monkeypatch):
    def fail(*args, **kwargs):
        raise RuntimeError("screenshot unavailable")
    monkeypatch.setattr("playwright.sync_api.Page.screenshot", fail)
    report = run(browser, site, tmp_path, [SMOKE[0]], path="/blank")
    assert report.checks[0].result == "Error"
    assert not any(item["type"] == "screenshot" for item in report.checks[0].evidence)


def test_storage_state_loaded_in_each_isolated_check(browser, site, tmp_path):
    state = tmp_path / "state.json"
    state.write_text(json.dumps({"cookies": [], "origins": [{"origin": site[0], "localStorage": [{"name": "auth_token", "value": "FAKE-SESSION"}]}]}), encoding="utf-8")
    def verify(ctx):
        expect(ctx.page.locator("#auth")).to_have_text("已登录")
        return Outcome("Pass", "登录态已加载")
    report = run(browser, site, tmp_path, [CheckSpec("auth1", "登录态1", "L1", verify), CheckSpec("auth2", "登录态2", "L1", verify)], path="/auth", storage_state=str(state))
    assert report.exit_code() == 0


def test_cross_origin_write_is_blocked_even_with_submit_permission(browser, site, tmp_path):
    initial = site[1]["posts"]
    def attempt(ctx):
        other = site[0].replace("127.0.0.1", "localhost") + "/write"
        ctx.page.evaluate("url => fetch(url, {method:'POST'}).catch(() => null)", other)
        return Outcome("Pass", "请求已尝试")
    report = run(browser, site, tmp_path, [CheckSpec("scope", "写入范围", "L1", attempt)], allow_submit=True)
    assert report.checks[0].result == "Blocked"
    assert site[1]["posts"] == initial


def test_mobile_context_matches_selected_platform(browser, site, tmp_path):
    def verify(ctx):
        assert "Mobile" in ctx.page.evaluate("navigator.userAgent")
        assert ctx.page.evaluate("navigator.maxTouchPoints") > 0
        assert ctx.page.viewport_size["width"] == 375
        return Outcome("Pass", "移动端配置正确")
    report = execute_checks(browser, site[0] + "/blank", "mobile", tmp_path,
                            [CheckSpec("mobile", "移动端模拟", "L0", verify)], RunOptions(), Redactor())
    assert report.exit_code() == 0
