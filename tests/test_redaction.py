import json
from scan_lib.redaction import Redactor


def test_report_redacts_all_known_secrets_and_common_credential_forms():
    redactor = Redactor(["fake-secret"])
    raw = {"actual": 'password="short" token=abcdef Bearer xyz fake-secret',
           "url": "https://user:pass@example.test/path?access_token=hidden&ok=1#token=fragment",
           "nested": {"authorization": "raw", "items": ["fake-secret"]}}
    output = json.dumps(redactor.clean(raw))
    assert all(secret not in output for secret in ("short", "abcdef", "xyz", "fake-secret", "hidden", "fragment", "user:pass", '"raw"'))
    assert "ok=1" in output


def test_redaction_is_idempotent_and_does_not_invent_payloads():
    redactor = Redactor(["qa-secret"])
    once = redactor.clean({"reason": "qa-secret", "count": 3})
    assert redactor.clean(once) == once
