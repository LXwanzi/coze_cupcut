import json

from graphs.nodes.output_writer import write_workflow_output


def test_write_workflow_output_uses_account_configured_path(tmp_path):
    account_pack = {
        "account_id": "demo_account",
        "output": {
            "enabled": True,
            "root_dir": str(tmp_path),
            "path_template": "{account_id}/{topic_slug}",
            "files": {
                "result": "result.json",
                "segments": "segments.json",
                "publish": "publish.json",
                "review": "review_card.json",
                "timeline": "timeline_segments.json",
                "draft_url": "draft_url.txt",
                "summary": "summary.md",
            },
        },
    }
    result = {
        "success": True,
        "draft_url": "http://example.com/draft",
        "content_meta": {"selected_topic": "机场值机"},
        "publish_pack": {"title": "【机场值机】不会开口？"},
        "review_card": {"today_expressions": []},
        "segments": [{"scene": "钩子页", "caption": "机场值机"}],
        "timeline_segments": [{"scene": "钩子页"}],
    }

    output = write_workflow_output({}, result, account_pack=account_pack)

    assert output["output_dir"].endswith("demo_account/机场值机")
    assert json.loads((tmp_path / "demo_account/机场值机/result.json").read_text(encoding="utf-8"))["success"] is True
    assert (tmp_path / "demo_account/机场值机/draft_url.txt").read_text(encoding="utf-8") == "http://example.com/draft"
