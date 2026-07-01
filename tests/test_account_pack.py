from content.account_loader import (
    account_exists,
    get_account_pack,
    normalize_account_id,
    resolve_scene_strategy,
)
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
    assert pack["scenes"]["scene_groups"]["travel"]["name"] == "旅游英语"
    assert any(item["id"] == "plane_attendant_help" for item in pack["scene_collection_presets"])
    assert any(item["id"] == "plane_attendant_help_painpoint" for item in pack["painpoint_presets"])


def test_metaphysics_account_pack_loads_isolated_config():
    pack = get_account_pack("metaphysics")

    assert pack["profile"]["account_id"] == "metaphysics"
    assert pack["modes"]["mode_aliases"]["场景式"] == "scene_product_seed"
    assert pack["prompts"]["system_role"] == "你是玄学生活方式短视频脚本策划。"
    assert pack["visual"]["style_name"] == "黑金禅意开运物语风"
    assert "black-gold zen metaphysics key visual style" in pack["visual"]["style_suffix"]
    assert "pixiu" not in pack["visual"]["style_suffix"]
    assert pack["visual"]["local_reference_image"] == "assets/metaphysics/seed/black_gold_zen_seed.png"
    assert pack["voices"]["speaker_map"]["mystic_male"] == "zh_male_ruyayichen_saturn_bigtts"
    assert pack["voices"]["speaker_map"]["gentle"] == "zh_female_santongyongns_saturn_bigtts"
    assert pack["modes"]["voice_profiles"]["painpoint_conversion"]["voice"] == "mystic_male"
    assert pack["scenes"]["scene_groups"]["money"]["name"] == "财运状态"
    assert "强命题" in pack["script_templates"]["painpoint_conversion"]["structure"]
    assert "产品桥接" not in pack["script_templates"]["painpoint_conversion"]["structure"]
    assert pack["script_templates"]["painpoint_conversion"]["quality_gate"]["min_symptoms"] == 3
    assert pack["script_templates"]["painpoint_conversion"]["quality_gate"]["min_adjustments"] == 2
    assert pack["product_catalog"]["products"][0]["name"] == "小貔貅摆件"
    assert "保证发财" in pack["safety_rules"]["forbidden_claims"]


def test_account_aliases_and_scene_strategy_are_pluginized():
    assert account_exists("xiaowanzi_english") is True
    assert normalize_account_id("玄学") == "metaphysics"
    assert normalize_account_id("小丸子英语") == "xiaowanzi_english"

    english_strategy = resolve_scene_strategy("xiaowanzi_english", "餐厅点餐")
    assert english_strategy["scene_id"] == "restaurant"
    assert "真实互动对象" in " ".join(english_strategy["content_principles"])

    metaphysics_strategy = resolve_scene_strategy("metaphysics", "最近总觉得钱留不住")
    assert metaphysics_strategy["scene_id"] == "money"
    assert "不直接卖产品" in metaphysics_strategy["hook_strategy"]


def test_topic_rescue_uses_account_pack_values():
    assert MODE_ALIASES["痛点式"] == "painpoint_contrast"
    assert "别说" in PAINPOINT_TRIGGERS
    assert any(item["id"] == "plane_attendant_help" for item in SCENE_COLLECTION_PRESETS)
    assert any(item["id"] == "airport_checkin_bag" for item in TOPIC_PRESETS)
    assert detect_scene("酒店退房查账单") == "hotel"
    assert voice_profile_for_mode("scene_collection", "travel")["voice"] == "default"
