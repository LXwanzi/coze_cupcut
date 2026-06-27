from agents.agent import _parse_user_input


def test_parse_user_input_treats_plain_text_as_topic():
    parsed = _parse_user_input("机场值机")

    assert parsed["raw_topic"] == "机场值机"
    assert parsed["topic"] == "机场值机"
    assert parsed["learning_note"] == ""
    assert parsed["scene"] == "travel"
    assert parsed["auto_generate_expressions"] is True


def test_parse_user_input_keeps_explicit_english_content():
    parsed = _parse_user_input("酒店英语：I'd like to check out, please.")

    assert parsed["raw_topic"] == "酒店英语"
    assert parsed["topic"] == "酒店英语"
    assert parsed["learning_note"] == "I'd like to check out, please."
    assert parsed["scene"] == "hotel"
    assert parsed["auto_generate_expressions"] is False
