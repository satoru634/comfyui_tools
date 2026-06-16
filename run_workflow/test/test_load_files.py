"""run_workflow.py のユニットテスト"""

import pytest

from test_helper import (
    write_json,
    valid_input,
    valid_config,
    valid_workflow_config,
    valid_wd14_tagger_config,
)

from modules.load_files import (
    load_config,
    load_tagger_config,
    validate_inputs,
    validate_wd14_tagger_config,
    load_and_validate_input,
    IMAGE_SIZE_MAX,
    IMAGE_SIZE_MIN,
)

# ── validate_inputs ───────────────────────────────────────────────────────────


class TestValidateInputs:
    def test_valid_single_lora(self):
        inputs = valid_input()
        assert validate_inputs(inputs["loras"], inputs["prompts"], None) == True

    def test_valid_no_loras(self):
        inputs = valid_input(loras=[])
        assert validate_inputs(inputs["loras"], inputs["prompts"], None) == True

    def test_valid_four_loras(self):
        inputs = valid_input(loras=["a", "b", "c", "d"])
        assert validate_inputs(inputs["loras"], inputs["prompts"], None) == True

    def test_loras_not_list(self):
        inputs = valid_input(loras="my_lora")
        with pytest.raises(ValueError, match="リスト形式"):
            validate_inputs(inputs["loras"], inputs["prompts"], None)

    def test_loras_exceeds_max(self):
        inputs = valid_input(loras=["a", "b", "c", "d", "e"])
        with pytest.raises(ValueError, match="最大4個"):
            validate_inputs(inputs["loras"], inputs["prompts"], None)

    def test_loras_item_empty_string(self):
        inputs = valid_input(loras=[""])
        with pytest.raises(ValueError, match="空でない文字列"):
            validate_inputs(inputs["loras"], inputs["prompts"], None)

    def test_missing_positive_key(self):
        inputs = valid_input(prompts={"negative": "bad"})
        with pytest.raises(ValueError, match="'positive' キーがありません"):
            validate_inputs(inputs["loras"], inputs["prompts"], None)

    def test_loras_item_not_string(self):
        inputs = valid_input(loras=[123])
        with pytest.raises(ValueError, match="空でない文字列"):
            validate_inputs(inputs["loras"], inputs["prompts"], None)

    def test_prompts_not_object(self):
        inputs = valid_input(prompts="positive prompt")
        with pytest.raises(ValueError, match="'prompts' はオブジェクト形式"):
            validate_inputs(inputs["loras"], inputs["prompts"], None)

    def test_missing_negative_key(self):
        inputs = valid_input(prompts={"positive": "good"})
        with pytest.raises(ValueError, match="'negative' キーがありません"):
            validate_inputs(inputs["loras"], inputs["prompts"], None)

    def test_positive_not_string(self):
        inputs = valid_input(prompts={"positive": 123, "negative": "bad"})
        with pytest.raises(ValueError, match="'prompts.positive' は文字列"):
            validate_inputs(inputs["loras"], inputs["prompts"], None)

    def test_positive_at_max_length(self):
        inputs = valid_input(prompts={"positive": "a" * 3000, "negative": "bad"})
        assert validate_inputs(inputs["loras"], inputs["prompts"], None) == True

    def test_positive_exceeds_max_length(self):
        inputs = valid_input(prompts={"positive": "a" * 3001, "negative": "bad"})
        with pytest.raises(ValueError, match="'prompts.positive' が長すぎます"):
            validate_inputs(inputs["loras"], inputs["prompts"], None)

    def test_negative_exceeds_max_length(self):
        inputs = valid_input(prompts={"positive": "good", "negative": "b" * 3001})
        with pytest.raises(ValueError, match="'prompts.negative' が長すぎます"):
            validate_inputs(inputs["loras"], inputs["prompts"], None)

    def test_image_size_not_object(self):
        inputs = valid_input(image_size=[512, 512])
        with pytest.raises(ValueError, match="'image_size' はオブジェクト形式"):
            validate_inputs(inputs["loras"], inputs["prompts"], inputs["image_size"])

    def test_image_size_missing_width(self):
        inputs = valid_input(image_size={"height": 512})
        with pytest.raises(
            ValueError, match="'image_size' に 'width' キーがありません"
        ):
            validate_inputs(inputs["loras"], inputs["prompts"], inputs["image_size"])

    def test_image_size_missing_height(self):
        inputs = valid_input(image_size={"width": 512})
        with pytest.raises(
            ValueError, match="'image_size' に 'height' キーがありません"
        ):
            validate_inputs(inputs["loras"], inputs["prompts"], inputs["image_size"])

    def test_image_size_width_not_integer(self):
        inputs = valid_input(image_size={"width": 512.0, "height": 512})
        with pytest.raises(ValueError, match="'image_size.width' は整数"):
            validate_inputs(inputs["loras"], inputs["prompts"], inputs["image_size"])

    def test_image_size_width_bool_rejected(self):
        inputs = valid_input(image_size={"width": True, "height": 512})
        with pytest.raises(ValueError, match="'image_size.width' は整数"):
            validate_inputs(inputs["loras"], inputs["prompts"], inputs["image_size"])

    @pytest.mark.parametrize("dim", ["width", "height"])
    def test_image_size_below_min(self, dim):
        size = {"width": 512, "height": 512}
        size[dim] = IMAGE_SIZE_MIN - 1
        inputs = valid_input(image_size=size)
        with pytest.raises(ValueError, match=f"'image_size.{dim}'"):
            validate_inputs(inputs["loras"], inputs["prompts"], inputs["image_size"])

    @pytest.mark.parametrize("dim", ["width", "height"])
    def test_image_size_above_max(self, dim):
        size = {"width": 512, "height": 512}
        size[dim] = IMAGE_SIZE_MAX + 1
        inputs = valid_input(image_size=size)
        with pytest.raises(ValueError, match=f"'image_size.{dim}'"):
            validate_inputs(inputs["loras"], inputs["prompts"], inputs["image_size"])

    @pytest.mark.parametrize("dim", ["width", "height"])
    def test_image_size_not_multiple_of_8(self, dim):
        size = {"width": 512, "height": 512}
        size[dim] = 513
        inputs = valid_input(image_size=size)
        with pytest.raises(ValueError, match="8 の倍数"):
            validate_inputs(inputs["loras"], inputs["prompts"], inputs["image_size"])

    def test_image_size_valid(self):
        inputs = valid_input(image_size={"width": 768, "height": 1024})
        assert (
            validate_inputs(inputs["loras"], inputs["prompts"], inputs["image_size"])
            == True
        )

    def test_image_size_boundary_min(self):
        inputs = valid_input(
            image_size={"width": IMAGE_SIZE_MIN, "height": IMAGE_SIZE_MIN}
        )
        assert (
            validate_inputs(inputs["loras"], inputs["prompts"], inputs["image_size"])
            == True
        )

    def test_image_size_boundary_max(self):
        inputs = valid_input(
            image_size={"width": IMAGE_SIZE_MAX, "height": IMAGE_SIZE_MAX}
        )
        assert (
            validate_inputs(inputs["loras"], inputs["prompts"], inputs["image_size"])
            == True
        )


# ── load_and_validate_input ───────────────────────────────────────────────────


class TestLoadAndValidateInput:
    def test_file_not_found(self, tmp_path):
        with pytest.raises(ValueError, match="入力ファイルが見つかりません"):
            load_and_validate_input(str(tmp_path / "nonexistent.json"))

    def test_invalid_json(self, tmp_path):
        p = tmp_path / "input.json"
        p.write_text("not json", encoding="utf-8")
        with pytest.raises(ValueError, match="入力 JSON の解析に失敗しました"):
            load_and_validate_input(str(p))

    def test_root_not_object(self, tmp_path):
        path = write_json(tmp_path / "input.json", [1, 2, 3])
        with pytest.raises(ValueError, match="オブジェクト形式"):
            load_and_validate_input(path)

    def test_missing_loras_key(self, tmp_path):
        data = valid_input()
        del data["loras"]
        path = write_json(tmp_path / "input.json", data)
        with pytest.raises(ValueError, match="'loras' キーがありません"):
            load_and_validate_input(path)

    def test_missing_prompts_key(self, tmp_path):
        data = valid_input()
        del data["prompts"]
        path = write_json(tmp_path / "input.json", data)
        with pytest.raises(ValueError, match="'prompts' キーがありません"):
            load_and_validate_input(path)


# ── load_config ───────────────────────────────────────────────────────────────


class TestLoadConfig:
    def test_valid(self, tmp_path):
        path = write_json(tmp_path / "config.json", valid_config())
        config = load_config(path)
        assert config["comfyui_url"] == "http://127.0.0.1:8188"
        assert config["default_workflow"] == "sdxl"
        assert (
            config["workflows"]["sdxl"]["loras"]["my_lora"]["file"]
            == "my_lora.safetensors"
        )

    def test_valid_multiple_workflows(self, tmp_path):
        data = valid_config(
            workflows={
                "sdxl": valid_workflow_config(),
                "sd15": valid_workflow_config(),
            }
        )
        path = write_json(tmp_path / "config.json", data)
        config = load_config(path)
        assert "sdxl" in config["workflows"]
        assert "sd15" in config["workflows"]

    def test_file_not_found(self, tmp_path):
        with pytest.raises(ValueError, match="設定ファイルが見つかりません"):
            load_config(str(tmp_path / "nonexistent.json"))

    def test_invalid_json(self, tmp_path):
        p = tmp_path / "config.json"
        p.write_text("not json", encoding="utf-8")
        with pytest.raises(ValueError, match="config.json の解析に失敗しました"):
            load_config(str(p))

    def test_missing_comfyui_url_key(self, tmp_path):
        data = valid_config()
        del data["comfyui_url"]
        path = write_json(tmp_path / "config.json", data)
        with pytest.raises(ValueError, match="'comfyui_url' キーがありません"):
            load_config(path)

    def test_comfyui_url_empty(self, tmp_path):
        path = write_json(tmp_path / "config.json", valid_config(comfyui_url=""))
        with pytest.raises(ValueError, match="空でない文字列"):
            load_config(path)

    def test_comfyui_url_not_string(self, tmp_path):
        path = write_json(tmp_path / "config.json", valid_config(comfyui_url=8188))
        with pytest.raises(ValueError, match="空でない文字列"):
            load_config(path)

    def test_missing_default_workflow_key(self, tmp_path):
        data = valid_config()
        del data["default_workflow"]
        path = write_json(tmp_path / "config.json", data)
        with pytest.raises(ValueError, match="'default_workflow' キーがありません"):
            load_config(path)

    def test_default_workflow_empty(self, tmp_path):
        path = write_json(tmp_path / "config.json", valid_config(default_workflow=""))
        with pytest.raises(ValueError, match="空でない文字列"):
            load_config(path)

    def test_default_workflow_not_in_workflows(self, tmp_path):
        path = write_json(
            tmp_path / "config.json", valid_config(default_workflow="unknown")
        )
        with pytest.raises(ValueError, match="'workflows' に存在しません"):
            load_config(path)

    def test_missing_workflows_key(self, tmp_path):
        data = valid_config()
        del data["workflows"]
        path = write_json(tmp_path / "config.json", data)
        with pytest.raises(ValueError, match="'workflows' キーがありません"):
            load_config(path)

    def test_workflows_not_object(self, tmp_path):
        path = write_json(tmp_path / "config.json", valid_config(workflows=[]))
        with pytest.raises(ValueError, match="'workflows' はオブジェクト形式"):
            load_config(path)

    def test_workflow_entry_missing_default_image_size(self, tmp_path):
        wf = valid_workflow_config()
        del wf["default_image_size"]
        path = write_json(
            tmp_path / "config.json", valid_config(workflows={"sdxl": wf})
        )
        with pytest.raises(ValueError, match="'default_image_size' キーがありません"):
            load_config(path)

    def test_workflow_entry_invalid_default_image_size(self, tmp_path):
        wf = valid_workflow_config(default_image_size={"width": 100, "height": 512})
        path = write_json(
            tmp_path / "config.json", valid_config(workflows={"sdxl": wf})
        )
        with pytest.raises(ValueError, match="default_image_size が不正です"):
            load_config(path)

    def test_workflow_entry_default_image_size_not_multiple_of_8(self, tmp_path):
        wf = valid_workflow_config(default_image_size={"width": 513, "height": 512})
        path = write_json(
            tmp_path / "config.json", valid_config(workflows={"sdxl": wf})
        )
        with pytest.raises(ValueError, match="default_image_size が不正です"):
            load_config(path)

    def test_workflow_entry_missing_loras_key(self, tmp_path):
        wf = valid_workflow_config()
        del wf["loras"]
        path = write_json(
            tmp_path / "config.json", valid_config(workflows={"sdxl": wf})
        )
        with pytest.raises(ValueError, match="'loras' キーがありません"):
            load_config(path)

    def test_workflow_entry_loras_entry_not_object(self, tmp_path):
        wf = valid_workflow_config(loras={"bad": "file.safetensors"})
        path = write_json(
            tmp_path / "config.json", valid_config(workflows={"sdxl": wf})
        )
        with pytest.raises(ValueError, match="オブジェクト形式"):
            load_config(path)

    def test_workflow_entry_loras_missing_file_key(self, tmp_path):
        wf = valid_workflow_config(loras={"lora": {"strength": 0.8}})
        path = write_json(
            tmp_path / "config.json", valid_config(workflows={"sdxl": wf})
        )
        with pytest.raises(ValueError, match=r"\.file は空でない文字列"):
            load_config(path)

    def test_workflow_entry_loras_missing_strength_key(self, tmp_path):
        wf = valid_workflow_config(loras={"lora": {"file": "lora.safetensors"}})
        path = write_json(
            tmp_path / "config.json", valid_config(workflows={"sdxl": wf})
        )
        with pytest.raises(ValueError, match=r"\.strength は数値"):
            load_config(path)

    def test_workflow_entry_loras_strength_not_number(self, tmp_path):
        wf = valid_workflow_config(
            loras={"lora": {"file": "lora.safetensors", "strength": "0.8"}}
        )
        path = write_json(
            tmp_path / "config.json", valid_config(workflows={"sdxl": wf})
        )
        with pytest.raises(ValueError, match=r"\.strength は数値"):
            load_config(path)


# ── load_tagger_config ────────────────────────────────────────────────────────


class TestLoadTaggerConfig:
    def test_valid_minimal(self, tmp_path):
        path = write_json(
            tmp_path / "config.json", {"comfyui_url": "http://127.0.0.1:8188"}
        )
        config = load_tagger_config(path)
        assert config["comfyui_url"] == "http://127.0.0.1:8188"

    def test_valid_ignores_extra_fields(self, tmp_path):
        path = write_json(tmp_path / "config.json", valid_config())
        config = load_tagger_config(path)
        assert config["comfyui_url"] == "http://127.0.0.1:8188"

    def test_file_not_found(self, tmp_path):
        with pytest.raises(ValueError, match="設定ファイルが見つかりません"):
            load_tagger_config(str(tmp_path / "nonexistent.json"))

    def test_invalid_json(self, tmp_path):
        p = tmp_path / "config.json"
        p.write_text("not json", encoding="utf-8")
        with pytest.raises(ValueError, match="config.json の解析に失敗しました"):
            load_tagger_config(str(p))

    def test_missing_comfyui_url_key(self, tmp_path):
        path = write_json(tmp_path / "config.json", {"wd14_tagger": {}})
        with pytest.raises(ValueError, match="'comfyui_url' キーがありません"):
            load_tagger_config(path)

    def test_comfyui_url_empty(self, tmp_path):
        path = write_json(tmp_path / "config.json", {"comfyui_url": ""})
        with pytest.raises(ValueError, match="空でない文字列"):
            load_tagger_config(path)

    def test_comfyui_url_not_string(self, tmp_path):
        path = write_json(tmp_path / "config.json", {"comfyui_url": 8188})
        with pytest.raises(ValueError, match="空でない文字列"):
            load_tagger_config(path)


# ── validate_wd14_tagger_config ───────────────────────────────────────────────


class TestValidateWd14TaggerConfig:
    def _make_config(self, **overrides) -> dict:
        return {**valid_config(), "wd14_tagger": valid_wd14_tagger_config(**overrides)}

    def test_valid(self):
        validate_wd14_tagger_config(self._make_config())

    def test_missing_wd14_tagger_key(self):
        with pytest.raises(ValueError, match="'wd14_tagger' キーがありません"):
            validate_wd14_tagger_config(valid_config())

    def test_wd14_tagger_not_dict(self):
        config = {**valid_config(), "wd14_tagger": "invalid"}
        with pytest.raises(ValueError, match="オブジェクト形式"):
            validate_wd14_tagger_config(config)

    def test_missing_model_name(self):
        config = self._make_config()
        del config["wd14_tagger"]["model_name"]
        with pytest.raises(ValueError, match="model_name"):
            validate_wd14_tagger_config(config)

    def test_empty_model_name(self):
        with pytest.raises(ValueError, match="model_name"):
            validate_wd14_tagger_config(self._make_config(model_name=""))

    def test_missing_general_threshold(self):
        config = self._make_config()
        del config["wd14_tagger"]["general_threshold"]
        with pytest.raises(ValueError, match="general_threshold"):
            validate_wd14_tagger_config(config)

    def test_missing_character_threshold(self):
        config = self._make_config()
        del config["wd14_tagger"]["character_threshold"]
        with pytest.raises(ValueError, match="character_threshold"):
            validate_wd14_tagger_config(config)

    def test_threshold_out_of_range(self):
        with pytest.raises(ValueError, match="0.0〜1.0"):
            validate_wd14_tagger_config(self._make_config(general_threshold=1.5))

    def test_threshold_is_bool(self):
        with pytest.raises(ValueError, match="数値"):
            validate_wd14_tagger_config(self._make_config(general_threshold=True))

    def test_threshold_boundary_zero(self):
        validate_wd14_tagger_config(self._make_config(general_threshold=0.0))

    def test_threshold_boundary_one(self):
        validate_wd14_tagger_config(self._make_config(general_threshold=1.0))
