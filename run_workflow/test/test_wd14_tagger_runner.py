"""TestWd14TaggerRunner のユニットテスト"""

import pytest
from unittest.mock import MagicMock

from test_helper import (
    write_json,
    valid_config,
    valid_wd14_tagger_config,
    make_wd14_workflow,
)

from modules.wd14_tagger_runner import (
    Wd14TaggerRunner,
)


# ── Wd14TaggerRunner ─────────────────────────────────────────────────────────


class TestWd14TaggerRunner:
    def _make_runner(self, tmp_path) -> Wd14TaggerRunner:
        config = {**valid_config(), "wd14_tagger": valid_wd14_tagger_config()}
        path = write_json(tmp_path / "config.json", config)
        runner = Wd14TaggerRunner(path)
        runner._template = make_wd14_workflow()
        runner._title_to_id = {
            "WD Timm Tagger": "1",
            "画像を読み込む": "2",
            "プレビュー任意": "3",
        }
        return runner

    def _mock_client(self, tags: str) -> MagicMock:
        mock = MagicMock()
        mock.upload_image.return_value = "uploaded.png"
        mock.submit.return_value = "prompt-xyz"
        mock.monitor.return_value = None
        mock.get_history.return_value = {"outputs": {"3": {"text": [tags]}}}
        return mock

    def test_tag_returns_tags(self, tmp_path):
        runner = self._make_runner(tmp_path)
        runner._client = self._mock_client("1girl, solo")
        assert runner.tag(b"image_data") == "1girl, solo"

    def test_tag_uploads_image(self, tmp_path):
        runner = self._make_runner(tmp_path)
        runner._client = self._mock_client("1girl")
        runner.tag(b"image_data", "photo.jpg")
        runner._client.upload_image.assert_called_once_with(b"image_data", "photo.jpg")

    def test_tag_sets_image_in_workflow(self, tmp_path):
        runner = self._make_runner(tmp_path)
        mock = self._mock_client("1girl")
        runner._client = mock
        runner.tag(b"image_data")
        submitted_workflow = mock.submit.call_args[0][0]
        assert submitted_workflow["2"]["inputs"]["image"] == "uploaded.png"

    def test_tag_sets_tagger_params_from_config(self, tmp_path):
        runner = self._make_runner(tmp_path)
        mock = self._mock_client("1girl")
        runner._client = mock
        runner.tag(b"image_data")
        submitted_workflow = mock.submit.call_args[0][0]
        tagger_inputs = submitted_workflow["1"]["inputs"]
        assert tagger_inputs["model_name"] == "wd-eva02-large-tagger-v3"
        assert tagger_inputs["general_threshold"] == 0.35
        assert tagger_inputs["character_threshold"] == 0.85

    def test_tag_does_not_mutate_template(self, tmp_path):
        runner = self._make_runner(tmp_path)
        runner._client = self._mock_client("1girl")
        original_image = runner._template["2"]["inputs"]["image"]
        runner.tag(b"image_data")
        assert runner._template["2"]["inputs"]["image"] == original_image

    def test_tag_raises_when_text_key_missing(self, tmp_path):
        runner = self._make_runner(tmp_path)
        mock = MagicMock()
        mock.upload_image.return_value = "uploaded.png"
        mock.submit.return_value = "prompt-xyz"
        mock.monitor.return_value = None
        mock.get_history.return_value = {"outputs": {"3": {}}}
        runner._client = mock
        with pytest.raises(ValueError, match="出力が取得できませんでした"):
            runner.tag(b"image_data")

    def test_tag_raises_on_upload_error(self, tmp_path):
        runner = self._make_runner(tmp_path)
        mock = MagicMock()
        mock.upload_image.side_effect = ValueError("ComfyUI に接続できません")
        runner._client = mock
        with pytest.raises(ValueError, match="接続できません"):
            runner.tag(b"image_data")

    def test_init_raises_on_missing_wd14_tagger_config(self, tmp_path):
        path = write_json(tmp_path / "config.json", valid_config())
        with pytest.raises(ValueError, match="wd14_tagger"):
            Wd14TaggerRunner(path)
