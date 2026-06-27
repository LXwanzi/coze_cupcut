from graphs.nodes.topic_rescue_node import (
    build_rescue_segments,
    build_scene_tts,
    build_topic_brief,
    parse_topic_input,
)
from graphs.nodes.generate_plan import generate_plan


def test_parse_topic_input_routes_airport_checkin():
    parsed = parse_topic_input("机场值机")

    assert parsed["topic"] == "机场值机"
    assert parsed["scene"] == "travel"
    assert parsed["sub_scene"] == "airport_checkin"
    assert parsed["auto_generate_expressions"] is True


def test_build_topic_brief_adds_rescue_answer_levels():
    brief = build_topic_brief("机场值机")

    assert brief["pain_point"] == "机场托运行李，别说 send my bag"
    assert brief["wrong_expression"] == "I want to send my bag."
    assert [item["level"] for item in brief["answer_levels"]] == [
        "survival",
        "standard",
        "polite",
    ]
    assert brief["answer_levels"][0]["english"] == "Yes, one bag."


def test_build_rescue_segments_contains_scene_and_layered_answers():
    brief = build_topic_brief("机场值机")
    segments = build_rescue_segments(brief)

    scenes = [segment["scene"] for segment in segments]
    assert scenes[:5] == [
        "钩子页",
        "沉浸场景",
        "错误表达",
        "最短能救场",
        "完整一点",
    ]
    assert any("Yes, one bag." in segment["caption"] for segment in segments)
    assert any("I have one bag to check." in segment["caption"] for segment in segments)
    assert "你在你在" not in segments[1]["tts"]
    assert "评论区说说" in segments[-1]["tts"]
    assert segments[-1]["scene"] == "预告页"
    assert sum(segment["duration"] for segment in segments) <= 30


def test_build_scene_tts_removes_duplicate_you_are_in_prefix():
    brief = build_topic_brief("机场值机")

    assert build_scene_tts(brief).startswith("现在你在机场值机柜台")
    assert "你在你在" not in build_scene_tts(brief)


def test_generate_plan_topic_only_uses_rescue_mode(tmp_path, monkeypatch):
    monkeypatch.setenv("COZE_WORKSPACE_PATH", str(tmp_path))

    result = generate_plan({
        "raw_topic": "机场值机",
        "topic": "机场值机",
        "auto_generate_expressions": True,
        "duration_seconds": 28,
        "sentence_count": 3,
    })

    assert result["error"] is None if "error" in result else True
    assert result["content_meta"]["format"] == "topic_rescue_hybrid"
    assert result["content_meta"]["pain_point"] == "机场托运行李，别说 send my bag"
    assert result["review_card"]["answer_levels"][0]["english"] == "Yes, one bag."
    assert [segment["scene"] for segment in result["segments"][:4]] == [
        "钩子页",
        "沉浸场景",
        "错误表达",
        "最短能救场",
    ]
