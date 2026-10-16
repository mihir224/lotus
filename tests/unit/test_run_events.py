from lotus_api.run_events import bounded_preview


def test_run_preview_redacts_sensitive_fields_and_bounds_text() -> None:
    preview = bounded_preview(
        {"token": "secret", "transcript": "private", "result": "x" * 500}, limit=20
    )
    assert preview["token"] == "[redacted]"
    assert preview["transcript"] == "[redacted]"
    assert len(preview["result"]) == 21
