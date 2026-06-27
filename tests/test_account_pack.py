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
    assert any(item["id"] == "plane_attendant_help" for item in pack["scene_collection_presets"])
    assert any(item["id"] == "plane_attendant_help_painpoint" for item in pack["painpoint_presets"])


def test_topic_rescue_uses_account_pack_values():
    assert MODE_ALIASES["痛点式"] == "painpoint_contrast"
    assert "别说" in PAINPOINT_TRIGGERS
    assert any(item["id"] == "plane_attendant_help" for item in SCENE_COLLECTION_PRESETS)
    assert any(item["id"] == "airport_checkin_bag" for item in TOPIC_PRESETS)
    assert detect_scene("酒店退房查账单") == "hotel"
    assert voice_profile_for_mode("scene_collection", "travel")["voice"] == "playful"
