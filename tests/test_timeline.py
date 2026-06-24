from graphs.nodes.capcut_node import _build_timeline_segments, _to_microseconds, _validate_timeline


def test_to_microseconds_accepts_seconds_and_microseconds():
    assert _to_microseconds(1.5) == 1_500_000
    assert _to_microseconds(1_500_000) == 1_500_000


def test_build_timeline_segments_uses_one_timeline_for_all_tracks():
    state = {
        "audio_segments": [
            {
                "index": 0,
                "start": 0,
                "end": 1_500_000,
                "duration": 1_500_000,
                "audio_url": "https://example.com/0.mp3",
                "caption": "小丸子通勤英语",
                "scene_data": {"scene": "标题页"},
            },
            {
                "index": 1,
                "start": 1_500_000,
                "end": 4_300_000,
                "duration": 2_800_000,
                "audio_url": "https://example.com/1.mp3",
                "caption": "I missed the subway train!\n我错过地铁了！",
                "scene_data": {"scene": "表达1"},
            },
        ],
        "scenes": [
            {"asset_url": "https://example.com/0.jpg"},
            {"asset_url": "https://example.com/1.jpg"},
        ],
    }

    timeline = _build_timeline_segments(state)

    assert _validate_timeline(timeline) is None
    assert timeline[0]["start"] == 0
    assert timeline[0]["end"] == 1_500_000
    assert timeline[1]["start"] == 1_500_000
    assert timeline[1]["end"] == 4_300_000
    assert timeline[1]["asset_url"] == "https://example.com/1.jpg"
