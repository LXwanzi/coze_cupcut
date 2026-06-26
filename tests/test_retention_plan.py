from graphs.nodes.generate_plan import (
    _extract_chat_content,
    _normalize_segments_for_retention,
    _normalize_sentence_count,
)


def test_normalize_sentence_count_defaults_to_short_video():
    assert _normalize_sentence_count(None) == 3
    assert _normalize_sentence_count(5) == 5
    assert _normalize_sentence_count(99) == 5


def test_normalize_segments_removes_legacy_slow_parts():
    segments = [
        {
            "scene": "回顾页",
            "caption": "上集回顾",
            "tts": "上次我们学了...",
            "image_prompt": "FIXED_HOOK_IMAGE",
            "duration": 2.0,
        },
        {
            "scene": "标题页",
            "caption": "酒店英语",
            "tts": "酒店英语",
            "image_prompt": "hotel scene",
            "duration": 3.0,
        },
        {
            "scene": "钩子页",
            "caption": "酒店问押金，别只会yes",
            "tts": "酒店问押金，别只会yes",
            "image_prompt": "FIXED_HOOK_IMAGE",
            "duration": 2.5,
        },
        {
            "scene": "第1句跟读",
            "caption": "Do you need a deposit?\n需要押金吗？",
            "tts": "第1句。Do you need a deposit? 需要押金吗？跟我读：Do you need a deposit? 再来一遍：Do you need a deposit?",
            "image_prompt": "hotel front desk",
            "duration": 6.0,
        },
        {
            "scene": "第2句跟读",
            "caption": "Can I pay by card?\n可以刷卡吗？",
            "tts": "第2句。Can I pay by card? 可以刷卡吗？跟我读：Can I pay by card?",
            "image_prompt": "paying at hotel",
            "duration": 6.0,
        },
        {
            "scene": "第3句跟读",
            "caption": "Could I have a receipt?\n可以给我收据吗？",
            "tts": "第3句。Could I have a receipt? 可以给我收据吗？跟我读：Could I have a receipt?",
            "image_prompt": "receipt at front desk",
            "duration": 6.0,
        },
        {
            "scene": "第4句跟读",
            "caption": "Please return my deposit.\n请退还我的押金。",
            "tts": "第4句。Please return my deposit. 请退还我的押金。跟我读：Please return my deposit.",
            "image_prompt": "deposit refund",
            "duration": 6.0,
        },
        {
            "scene": "结尾复习页",
            "caption": "本集复习\n1. Do you need a deposit?",
            "tts": "来复习一下今天学的句子",
            "image_prompt": "FIXED_REVIEW_WITH_CHAR",
            "duration": 8.0,
        },
    ]

    normalized = _normalize_segments_for_retention(segments, sentence_count=3)

    assert [seg["scene"] for seg in normalized] == [
        "钩子页",
        "第1句跟读",
        "第2句跟读",
        "第3句跟读",
        "快速汇总页",
        "预告页",
    ]
    assert "再来一遍" not in normalized[1]["tts"]
    assert normalized[1]["duration"] == 5.0
    assert normalized[-2]["duration"] == 2.5
    assert normalized[-2]["tts"] == "这几句先收藏，下一集继续学同一场景。"


class _FakeResponse:
    def __init__(self, payload):
        self._payload = payload
        self.content = b""

    def json(self):
        return self._payload


def test_extract_chat_content_supports_standard_chat_response():
    resp = _FakeResponse({
        "choices": [
            {"message": {"content": "{\"segments\": []}"}}
        ]
    })

    assert _extract_chat_content(resp) == "{\"segments\": []}"
