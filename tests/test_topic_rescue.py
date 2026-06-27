import pytest

from graphs.nodes.topic_rescue_node import (
    build_rescue_segments,
    build_scene_collection_segments,
    build_scene_tts,
    build_topic_brief,
    find_generic_scene_expressions,
    normalize_dynamic_scene_collection_brief,
    parse_topic_input,
    review_topic_brief,
)
from graphs.nodes.generate_plan import generate_plan


def test_parse_topic_input_routes_airport_checkin():
    parsed = parse_topic_input("机场值机")

    assert parsed["topic"] == "机场值机"
    assert parsed["scene"] == "travel"
    assert parsed["sub_scene"] == "airport_checkin"
    assert parsed["auto_generate_expressions"] is True


def test_parse_topic_input_routes_plane_attendant_as_scene_collection():
    parsed = parse_topic_input("飞机上找空乘")

    assert parsed["topic"] == "飞机上找空乘"
    assert parsed["scene"] == "travel"
    assert parsed["sub_scene"] == "in_flight_attendant"
    assert parsed["content_mode"] == "scene_collection"


def test_parse_topic_input_routes_plane_attendant_synonym_as_scene_collection():
    parsed = parse_topic_input("飞机上寻求空乘帮助")

    assert parsed["topic"] == "飞机上找空乘"
    assert parsed["sub_scene"] == "in_flight_attendant"
    assert parsed["content_mode"] == "scene_collection"


def test_build_topic_brief_adds_rescue_answer_levels():
    brief = build_topic_brief("痛点式：机场值机")

    assert brief["pain_point"] == "机场托运行李，别说 send my bag"
    assert brief["wrong_expression"] == "I want to send my bag."
    assert [item["level"] for item in brief["answer_levels"]] == [
        "survival",
        "standard",
        "polite",
    ]
    assert brief["answer_levels"][0]["english"] == "Yes, one bag."


def test_build_topic_brief_adds_scene_collection_expressions():
    brief = build_topic_brief("飞机上找空乘")

    assert brief["content_mode"] == "scene_collection"
    assert len(brief["expressions"]) == 5
    assert brief["expressions"][0]["english"] == "Excuse me, could you help me?"
    assert brief["quality_review"]["is_reasonable"] is True
    assert brief["voice_profile"]["voice"] == "playful"


def test_painpoint_plane_attendant_uses_meaningful_contrast():
    brief = build_topic_brief("痛点式：飞机上寻求空乘帮助")

    assert brief["content_mode"] == "painpoint_contrast"
    assert brief["wrong_expression"] == "Yes."
    assert "没说清楚" in brief["why_wrong"]
    assert brief["answer_levels"][0]["english"] == "Could you help me?"
    assert brief["answer_levels"][1]["english"] == "Could you help me put this up?"
    assert brief["answer_levels"][0]["english"] != "Yes, please."


def test_fallback_painpoint_avoids_weak_yes_to_yes_please_contrast():
    brief = build_topic_brief("痛点式：咖啡店杯子太小")

    assert brief["wrong_expression"] == "Help me."
    assert brief["answer_levels"][0]["english"] == "Could you help me with this?"
    assert all(item["english"] != "Yes, please." for item in brief["answer_levels"])


def test_build_rescue_segments_contains_scene_and_layered_answers():
    brief = build_topic_brief("痛点式：机场值机")
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


def test_build_scene_collection_segments_keeps_five_sentences_fast():
    brief = build_topic_brief("飞机上找空乘")
    segments = build_scene_collection_segments(brief)

    sentence_segments = [segment for segment in segments if segment["scene"].startswith("第")]
    assert len(sentence_segments) == 5
    assert sentence_segments[0]["caption"].startswith("Excuse me, could you help me?")
    assert segments[0]["scene"] == "钩子页"
    assert segments[-1]["scene"] == "互动页"
    assert sum(segment["duration"] for segment in segments) <= 38


def test_review_topic_brief_marks_scene_collection_reasonable():
    brief = build_topic_brief("飞机上找空乘")
    review = review_topic_brief(brief, "飞机上找空乘")

    assert review["content_mode"] == "scene_collection"
    assert review["suggested_sentence_count"] == 5
    assert review["issues"] == []


def test_unknown_scene_collection_marks_dynamic_generation_needed():
    brief = build_topic_brief("场景式：飞机餐忌口")

    assert brief["content_mode"] == "scene_collection"
    assert brief["needs_dynamic_generation"] is True
    assert brief["expressions"] == []
    assert brief["quality_review"]["is_reasonable"] is False


def test_dynamic_scene_collection_brief_passes_for_specific_topic():
    brief = normalize_dynamic_scene_collection_brief(
        "飞机餐忌口",
        "travel",
        {
            "topic": "飞机餐忌口",
            "real_scene": "你在飞机上拿到餐食前想确认忌口",
            "hook": "飞机餐忌口，这5句先会",
            "setup": "素食、过敏、不吃猪肉、换餐都覆盖。",
            "expressions": [
                {"label": "问素食", "english": "Do you have a vegetarian option?", "chinese": "有素食选择吗？"},
                {"label": "说花生忌口", "english": "I can't eat peanuts.", "chinese": "我不能吃花生。"},
                {"label": "说海鲜过敏", "english": "I'm allergic to seafood.", "chinese": "我对海鲜过敏。"},
                {"label": "确认猪肉", "english": "Does this have pork in it?", "chinese": "这里面有猪肉吗？"},
                {"label": "换鸡肉", "english": "Could I have the chicken instead?", "chinese": "我可以换成鸡肉吗？"},
            ],
        }
    )

    assert brief["quality_review"]["is_reasonable"] is True
    assert len(brief["expressions"]) == 5
    assert not find_generic_scene_expressions(brief["expressions"])


def test_scene_collection_quality_blocks_generic_expressions():
    brief = normalize_dynamic_scene_collection_brief(
        "飞机餐忌口",
        "travel",
        {
            "topic": "飞机餐忌口",
            "expressions": [
                {"label": "先开口", "english": "Excuse me, could you help me?", "chinese": "不好意思，可以帮我一下吗？"},
                {"label": "说明需求", "english": "I'd like to ask about this.", "chinese": "我想问一下这个。"},
                {"label": "确认", "english": "Could you confirm that for me?", "chinese": "可以帮我确认一下吗？"},
                {"label": "没听清", "english": "Could you say that again?", "chinese": "可以再说一遍吗？"},
                {"label": "感谢", "english": "Thanks, that helps a lot.", "chinese": "谢谢，这帮了我很多。"},
            ],
        }
    )

    assert brief["quality_review"]["is_reasonable"] is False
    assert any("万能句" in issue for issue in brief["quality_review"]["issues"])


def test_build_scene_tts_removes_duplicate_you_are_in_prefix():
    brief = build_topic_brief("痛点式：机场值机")

    assert build_scene_tts(brief).startswith("现在你在机场值机柜台")
    assert "你在你在" not in build_scene_tts(brief)


def test_generate_plan_topic_only_uses_rescue_mode(tmp_path, monkeypatch):
    monkeypatch.setenv("COZE_WORKSPACE_PATH", str(tmp_path))

    result = generate_plan({
        "raw_topic": "痛点式：机场值机",
        "topic": "痛点式：机场值机",
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


def test_generate_plan_topic_only_uses_scene_collection_mode(tmp_path, monkeypatch):
    monkeypatch.setenv("COZE_WORKSPACE_PATH", str(tmp_path))

    result = generate_plan({
        "raw_topic": "飞机上找空乘",
        "topic": "飞机上找空乘",
        "auto_generate_expressions": True,
        "duration_seconds": 28,
        "sentence_count": 3,
    })

    assert result["error"] is None if "error" in result else True
    assert result["content_meta"]["format"] == "scene_collection"
    assert result["content_meta"]["content_mode"] == "scene_collection"
    assert result["content_meta"]["sentence_count"] == 5
    assert result["content_meta"]["quality_review"]["is_reasonable"] is True
    assert result["publish_pack"]["title"].startswith("【飞机上找空乘】")
    assert len(result["review_card"]["today_expressions"]) == 5
    assert [segment["scene"] for segment in result["segments"][:3]] == [
        "钩子页",
        "场景代入",
        "第1句场景句",
    ]


def test_generate_plan_dynamic_scene_collection_uses_generated_expressions(tmp_path, monkeypatch):
    monkeypatch.setenv("COZE_WORKSPACE_PATH", str(tmp_path))

    from graphs.nodes import generate_plan as generate_plan_module

    def fake_generate_dynamic_scene_collection_brief(raw_topic, scene, memory_context):
        return normalize_dynamic_scene_collection_brief(
            raw_topic,
            scene,
            {
                "topic": "飞机餐忌口",
                "hook": "飞机餐忌口，这5句先会",
                "setup": "素食、过敏、不吃猪肉、换餐都覆盖。",
                "expressions": [
                    {"label": "问素食", "english": "Do you have a vegetarian option?", "chinese": "有素食选择吗？"},
                    {"label": "说花生忌口", "english": "I can't eat peanuts.", "chinese": "我不能吃花生。"},
                    {"label": "说海鲜过敏", "english": "I'm allergic to seafood.", "chinese": "我对海鲜过敏。"},
                    {"label": "确认猪肉", "english": "Does this have pork in it?", "chinese": "这里面有猪肉吗？"},
                    {"label": "换鸡肉", "english": "Could I have the chicken instead?", "chinese": "我可以换成鸡肉吗？"},
                ],
                "title": "【飞机餐忌口】这5句一定要会",
            }
        )

    monkeypatch.setattr(
        generate_plan_module,
        "_generate_dynamic_scene_collection_brief",
        fake_generate_dynamic_scene_collection_brief,
    )

    result = generate_plan({
        "raw_topic": "场景式：飞机餐忌口",
        "topic": "场景式：飞机餐忌口",
        "auto_generate_expressions": True,
        "duration_seconds": 28,
        "sentence_count": 3,
    })

    assert result["content_meta"]["format"] == "scene_collection"
    assert result["content_meta"]["quality_review"]["is_reasonable"] is True
    assert result["review_card"]["today_expressions"][0]["english"] == "Do you have a vegetarian option?"
    assert "Could you help me?" not in "\n".join(seg["caption"] for seg in result["segments"])


def test_tts_resolves_voice_profile_speed():
    pytest.importorskip("coze_coding_dev_sdk")
    from graphs.nodes.tts_node import _resolve_voice_and_speed

    speaker, speed = _resolve_voice_and_speed({
        "scene": "travel",
        "voice_profile": {"voice": "playful", "speed": 1.1},
    })

    assert speaker == "saturn_zh_female_tiaopigongzhu_tob"
    assert speed == 1.1
