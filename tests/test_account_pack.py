from content.account_loader import get_account_pack
from graphs.nodes.topic_rescue_node import (
    MODE_ALIASES,
    PAINPOINT_TRIGGERS,
    SCENE_COLLECTION_PRESETS,
    TOPIC_PRESETS,
    detect_scene,
    voice_profile_for_mode,
)


def test_xiaowanzi_account_pack_loads_content_config():
    pack = get_account_pack("xiaowanzi_english")

    assert pack["profile"]["account_id"] == "xiaowanzi_english"
    assert pack["modes"]["mode_aliases"]["场景式"] == "scene_collection"
    assert pack["prompts"]["system_role"].startswith("你是“小丸子英语”")
    assert pack["visual"]["image_prompt_guard"]["enabled"] is True
    assert "Xiao Wanzi" in pack["visual"]["style_suffix"]
    assert pack["voices"]["speaker_map"]["playful"] == "saturn_zh_female_tiaopigongzhu_tob"
    assert pack["publish"]["title_templates"]["scene_collection"].startswith("【{topic}】")
    assert pack["output"]["enabled"] is True
    assert any(item["id"] == "plane_attendant_help" for item in pack["scene_collection_presets"])
    assert any(item["id"] == "plane_attendant_help_painpoint" for item in pack["painpoint_presets"])


def test_metaphysics_account_pack_loads_isolated_config():
    pack = get_account_pack("metaphysics")

    assert pack["profile"]["account_id"] == "metaphysics"
    assert pack["modes"]["mode_aliases"]["场景式"] == "scene_product_seed"
    assert pack["prompts"]["system_role"] == "你是玄学生活方式短视频脚本策划。"
    assert "oriental lifestyle" in pack["visual"]["style_suffix"]
    assert pack["voices"]["speaker_map"]["gentle"] == "zh_female_santongyongns_saturn_bigtts"
    assert pack["product_catalog"]["products"][0]["name"] == "小貔貅摆件"
    assert "保证发财" in pack["safety_rules"]["forbidden_claims"]


def test_topic_rescue_uses_account_pack_values():
    assert MODE_ALIASES["痛点式"] == "painpoint_contrast"
    assert "别说" in PAINPOINT_TRIGGERS
    assert any(item["id"] == "plane_attendant_help" for item in SCENE_COLLECTION_PRESETS)
    assert any(item["id"] == "airport_checkin_bag" for item in TOPIC_PRESETS)
    assert detect_scene("酒店退房查账单") == "hotel"
    assert voice_profile_for_mode("scene_collection", "travel")["voice"] == "default"
