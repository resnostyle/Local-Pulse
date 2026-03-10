"""Tests for prompt builder."""

from normalizer.prompt import SYSTEM_PROMPT, USER_PROMPT_TEMPLATE, build_user_prompt


def test_system_prompt_contains_json_instruction():
    assert "JSON" in SYSTEM_PROMPT
    assert "title" in SYSTEM_PROMPT
    assert "start_time" in SYSTEM_PROMPT


def test_build_user_prompt_includes_all_fields():
    text = "Calendar text here"
    source = "Test Source"
    source_url = "https://example.com/calendar"

    result = build_user_prompt(text, source, source_url)

    assert source in result
    assert source_url in result
    assert text in result
    assert "---" in result


def test_build_user_prompt_truncates_long_text():
    text = "x" * 20000
    result = build_user_prompt(text, "S", "https://u.com")
    assert len(result) < 20000
