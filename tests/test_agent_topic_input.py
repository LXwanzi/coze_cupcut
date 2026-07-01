from agents.agent import (
    _extract_voice_profile_override,
    _parse_user_input,
    _validate_account_contract,
)


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


def test_parse_user_input_keeps_scene_mode_prefix_as_topic():
    parsed = _parse_user_input("场景式：飞机上寻求空乘帮助")

    assert parsed["raw_topic"] == "场景式：飞机上寻求空乘帮助"
    assert parsed["topic"] == "场景式：飞机上寻求空乘帮助"
    assert parsed["learning_note"] == ""
    assert parsed["scene"] == "travel"
    assert parsed["auto_generate_expressions"] is True


def test_parse_user_input_keeps_painpoint_mode_prefix_as_topic():
    parsed = _parse_user_input("痛点式：机场值机")

    assert parsed["raw_topic"] == "痛点式：机场值机"
    assert parsed["topic"] == "痛点式：机场值机"
    assert parsed["learning_note"] == ""
    assert parsed["scene"] == "travel"
    assert parsed["auto_generate_expressions"] is True


def test_parse_user_input_extracts_voice_profile_override():
    parsed = _parse_user_input("场景式：机场值机\n音色：俏皮\n语速：1.12")

    assert parsed["topic"] == "场景式：机场值机"
    assert parsed["voice_profile_override"] == {"voice": "playful", "speed": 1.12}


def test_parse_user_input_extracts_account_contract_multiline():
    parsed = _parse_user_input(
        "account: metaphysics\nmode: 痛点式\ntopic: 最近总觉得钱留不住"
    )

    assert parsed["account_id"] == "metaphysics"
    assert parsed["raw_topic"] == "痛点式：最近总觉得钱留不住"
    assert parsed["topic"] == "痛点式：最近总觉得钱留不住"
    assert parsed["scene"] == "wallet"
    assert parsed["scene_strategy"]["scene_id"] == "money"
    assert parsed["account_explicit"] is True
    assert parsed["auto_generate_expressions"] is True


def test_parse_user_input_extracts_account_contract_inline():
    parsed = _parse_user_input(
        "账号=玄学；模式=痛点式；主题=最近总觉得钱留不住"
    )

    assert parsed["account_id"] == "metaphysics"
    assert parsed["raw_topic"] == "痛点式：最近总觉得钱留不住"
    assert parsed["scene"] == "wallet"


def test_validate_account_contract_requires_explicit_account():
    parsed = _parse_user_input("餐厅点餐")

    message = _validate_account_contract(parsed)

    assert "请先明确要生成哪个账号" in message
    assert "account: xiaowanzi_english" in message




def test_extract_voice_profile_accepts_tts_voice_code():
    message, override = _extract_voice_profile_override(
        "痛点式：酒店退房\nvoice: zh_female_yingyujiaoxue_uranus_bigtts\nspeed: 9"
    )

    assert message == "痛点式：酒店退房"
    assert override["voice"] == "zh_female_yingyujiaoxue_uranus_bigtts"
    assert override["speed"] == 1.35
