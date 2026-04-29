"""run_workflow.py のユニットテスト"""

import asyncio
import json
import pytest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import requests

from run_workflow import (
    load_and_validate_input,
    load_config,
    resolve_loras,
    write_result,
    WorkflowBuilder,
    ComfyUIClient,
    WorkflowRunner,
    MAX_PROMPT_LENGTH,
    IMAGE_SIZE_MIN,
    IMAGE_SIZE_MAX,
)

TEMPLATES_DIR = Path(__file__).parent.parent / "templates"


# ── helpers ───────────────────────────────────────────────────────────────────


def write_json(path: Path, data) -> str:
    path.write_text(json.dumps(data), encoding="utf-8")
    return str(path)


def valid_input(**overrides) -> dict:
    base = {
        "loras": ["my_lora"],
        "prompts": {
            "positive": "masterpiece, best quality",
            "negative": "worst quality",
        },
    }
    base.update(overrides)
    return base


def valid_lora_list() -> dict:
    return {
        "my_lora": {"file": "my_lora.safetensors", "strength": 0.8},
        "another_lora": {"file": "another_lora.safetensors", "strength": 0.7},
    }


def valid_image_size(**overrides) -> dict:
    base = {"width": 512, "height": 512}
    base.update(overrides)
    return base


def valid_config(**overrides) -> dict:
    base = {
        "comfyui_url": "http://127.0.0.1:8188",
        "default_image_size": valid_image_size(),
        "loras": valid_lora_list(),
    }
    base.update(overrides)
    return base


def make_workflow(
    lora_count: int, with_sampler: bool = True, with_latent: bool = True
) -> dict:
    workflow = {
        "1": {
            "class_type": "CLIPTextEncode",
            "inputs": {"text": "", "clip": ["0", 1]},
            "_meta": {"title": "positive_prompt"},
        },
        "2": {
            "class_type": "CLIPTextEncode",
            "inputs": {"text": "", "clip": ["0", 1]},
            "_meta": {"title": "negative_prompt"},
        },
    }
    for i in range(1, lora_count + 1):
        workflow[str(10 + i)] = {
            "class_type": "LoraLoader",
            "inputs": {"lora_name": "", "strength_model": 1.0, "strength_clip": 1.0},
            "_meta": {"title": f"lora_loader_{i}"},
        }
    if with_sampler:
        workflow["99"] = {
            "class_type": "KSampler",
            "inputs": {"seed": 12345, "steps": 20, "cfg": 7},
            "_meta": {"title": "Kサンプラー"},
        }
        workflow["98"] = {
            "class_type": "FaceDetailer",
            "inputs": {"seed": 99999, "steps": 20, "cfg": 7},
            "_meta": {"title": "FaceDetailer"},
        }
    if with_latent:
        workflow["5"] = {
            "class_type": "EmptyLatentImage",
            "inputs": {"width": 512, "height": 512, "batch_size": 1},
            "_meta": {"title": "empty_latent_image"},
        }
    return workflow


def make_loras(count: int) -> list[dict]:
    return [
        {"name": f"lora{i}", "file": f"lora{i}.safetensors", "strength": 0.5 + i * 0.1}
        for i in range(1, count + 1)
    ]


def make_ws_message(**kwargs) -> str:
    return json.dumps(kwargs)


# ── load_and_validate_input ───────────────────────────────────────────────────


class TestLoadAndValidateInput:
    def test_valid_single_lora(self, tmp_path):
        path = write_json(tmp_path / "input.json", valid_input())
        data = load_and_validate_input(path)
        assert data["loras"] == ["my_lora"]

    def test_valid_no_loras(self, tmp_path):
        path = write_json(tmp_path / "input.json", valid_input(loras=[]))
        assert load_and_validate_input(path)["loras"] == []

    def test_valid_four_loras(self, tmp_path):
        path = write_json(
            tmp_path / "input.json", valid_input(loras=["a", "b", "c", "d"])
        )
        assert len(load_and_validate_input(path)["loras"]) == 4

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

    def test_loras_not_list(self, tmp_path):
        path = write_json(tmp_path / "input.json", valid_input(loras="my_lora"))
        with pytest.raises(ValueError, match="リスト形式"):
            load_and_validate_input(path)

    def test_loras_exceeds_max(self, tmp_path):
        path = write_json(
            tmp_path / "input.json", valid_input(loras=["a", "b", "c", "d", "e"])
        )
        with pytest.raises(ValueError, match="最大4個"):
            load_and_validate_input(path)

    def test_loras_item_empty_string(self, tmp_path):
        path = write_json(tmp_path / "input.json", valid_input(loras=[""]))
        with pytest.raises(ValueError, match="空でない文字列"):
            load_and_validate_input(path)

    def test_loras_item_not_string(self, tmp_path):
        path = write_json(tmp_path / "input.json", valid_input(loras=[123]))
        with pytest.raises(ValueError, match="空でない文字列"):
            load_and_validate_input(path)

    def test_missing_prompts_key(self, tmp_path):
        data = valid_input()
        del data["prompts"]
        path = write_json(tmp_path / "input.json", data)
        with pytest.raises(ValueError, match="'prompts' キーがありません"):
            load_and_validate_input(path)

    def test_prompts_not_object(self, tmp_path):
        path = write_json(
            tmp_path / "input.json", valid_input(prompts="positive prompt")
        )
        with pytest.raises(ValueError, match="'prompts' はオブジェクト形式"):
            load_and_validate_input(path)

    def test_missing_positive_key(self, tmp_path):
        path = write_json(
            tmp_path / "input.json", valid_input(prompts={"negative": "bad"})
        )
        with pytest.raises(ValueError, match="'positive' キーがありません"):
            load_and_validate_input(path)

    def test_missing_negative_key(self, tmp_path):
        path = write_json(
            tmp_path / "input.json", valid_input(prompts={"positive": "good"})
        )
        with pytest.raises(ValueError, match="'negative' キーがありません"):
            load_and_validate_input(path)

    def test_positive_not_string(self, tmp_path):
        path = write_json(
            tmp_path / "input.json",
            valid_input(prompts={"positive": 123, "negative": "bad"}),
        )
        with pytest.raises(ValueError, match="'prompts.positive' は文字列"):
            load_and_validate_input(path)

    def test_positive_at_max_length(self, tmp_path):
        path = write_json(
            tmp_path / "input.json",
            valid_input(prompts={"positive": "a" * 3000, "negative": "bad"}),
        )
        assert load_and_validate_input(path)

    def test_positive_exceeds_max_length(self, tmp_path):
        path = write_json(
            tmp_path / "input.json",
            valid_input(prompts={"positive": "a" * 3001, "negative": "bad"}),
        )
        with pytest.raises(ValueError, match="'prompts.positive' が長すぎます"):
            load_and_validate_input(path)

    def test_negative_exceeds_max_length(self, tmp_path):
        path = write_json(
            tmp_path / "input.json",
            valid_input(prompts={"positive": "good", "negative": "b" * 3001}),
        )
        with pytest.raises(ValueError, match="'prompts.negative' が長すぎます"):
            load_and_validate_input(path)

    def test_image_size_omitted_is_accepted(self, tmp_path):
        path = write_json(tmp_path / "input.json", valid_input())
        data = load_and_validate_input(path)
        assert "image_size" not in data

    def test_image_size_valid(self, tmp_path):
        path = write_json(
            tmp_path / "input.json",
            valid_input(image_size={"width": 768, "height": 1024}),
        )
        data = load_and_validate_input(path)
        assert data["image_size"] == {"width": 768, "height": 1024}

    def test_image_size_not_object(self, tmp_path):
        path = write_json(tmp_path / "input.json", valid_input(image_size=[512, 512]))
        with pytest.raises(ValueError, match="'image_size' はオブジェクト形式"):
            load_and_validate_input(path)

    def test_image_size_missing_width(self, tmp_path):
        path = write_json(
            tmp_path / "input.json", valid_input(image_size={"height": 512})
        )
        with pytest.raises(
            ValueError, match="'image_size' に 'width' キーがありません"
        ):
            load_and_validate_input(path)

    def test_image_size_missing_height(self, tmp_path):
        path = write_json(
            tmp_path / "input.json", valid_input(image_size={"width": 512})
        )
        with pytest.raises(
            ValueError, match="'image_size' に 'height' キーがありません"
        ):
            load_and_validate_input(path)

    def test_image_size_width_not_integer(self, tmp_path):
        path = write_json(
            tmp_path / "input.json",
            valid_input(image_size={"width": 512.0, "height": 512}),
        )
        with pytest.raises(ValueError, match="'image_size.width' は整数"):
            load_and_validate_input(path)

    def test_image_size_width_bool_rejected(self, tmp_path):
        path = write_json(
            tmp_path / "input.json",
            valid_input(image_size={"width": True, "height": 512}),
        )
        with pytest.raises(ValueError, match="'image_size.width' は整数"):
            load_and_validate_input(path)

    @pytest.mark.parametrize("dim", ["width", "height"])
    def test_image_size_below_min(self, tmp_path, dim):
        size = {"width": 512, "height": 512}
        size[dim] = IMAGE_SIZE_MIN - 1
        path = write_json(tmp_path / "input.json", valid_input(image_size=size))
        with pytest.raises(ValueError, match=f"'image_size.{dim}'"):
            load_and_validate_input(path)

    @pytest.mark.parametrize("dim", ["width", "height"])
    def test_image_size_above_max(self, tmp_path, dim):
        size = {"width": 512, "height": 512}
        size[dim] = IMAGE_SIZE_MAX + 1
        path = write_json(tmp_path / "input.json", valid_input(image_size=size))
        with pytest.raises(ValueError, match=f"'image_size.{dim}'"):
            load_and_validate_input(path)

    @pytest.mark.parametrize("dim", ["width", "height"])
    def test_image_size_not_multiple_of_8(self, tmp_path, dim):
        size = {"width": 512, "height": 512}
        size[dim] = 513
        path = write_json(tmp_path / "input.json", valid_input(image_size=size))
        with pytest.raises(ValueError, match="8 の倍数"):
            load_and_validate_input(path)

    def test_image_size_boundary_min(self, tmp_path):
        path = write_json(
            tmp_path / "input.json",
            valid_input(image_size={"width": IMAGE_SIZE_MIN, "height": IMAGE_SIZE_MIN}),
        )
        assert load_and_validate_input(path)

    def test_image_size_boundary_max(self, tmp_path):
        path = write_json(
            tmp_path / "input.json",
            valid_input(image_size={"width": IMAGE_SIZE_MAX, "height": IMAGE_SIZE_MAX}),
        )
        assert load_and_validate_input(path)


# ── load_config ───────────────────────────────────────────────────────────────


class TestLoadConfig:
    def test_valid(self, tmp_path):
        path = write_json(tmp_path / "config.json", valid_config())
        config = load_config(path)
        assert config["comfyui_url"] == "http://127.0.0.1:8188"
        assert config["loras"]["my_lora"]["file"] == "my_lora.safetensors"

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

    def test_missing_loras_key(self, tmp_path):
        data = valid_config()
        del data["loras"]
        path = write_json(tmp_path / "config.json", data)
        with pytest.raises(ValueError, match="'loras' キーがありません"):
            load_config(path)

    def test_loras_entry_not_object(self, tmp_path):
        path = write_json(
            tmp_path / "config.json", valid_config(loras={"bad": "file.safetensors"})
        )
        with pytest.raises(ValueError, match="オブジェクト形式"):
            load_config(path)

    def test_loras_missing_file_key(self, tmp_path):
        path = write_json(
            tmp_path / "config.json", valid_config(loras={"lora": {"strength": 0.8}})
        )
        with pytest.raises(ValueError, match=r"\.file は空でない文字列"):
            load_config(path)

    def test_loras_missing_strength_key(self, tmp_path):
        path = write_json(
            tmp_path / "config.json",
            valid_config(loras={"lora": {"file": "lora.safetensors"}}),
        )
        with pytest.raises(ValueError, match=r"\.strength は数値"):
            load_config(path)

    def test_loras_strength_not_number(self, tmp_path):
        path = write_json(
            tmp_path / "config.json",
            valid_config(
                loras={"lora": {"file": "lora.safetensors", "strength": "0.8"}}
            ),
        )
        with pytest.raises(ValueError, match=r"\.strength は数値"):
            load_config(path)

    def test_missing_default_image_size_key(self, tmp_path):
        data = valid_config()
        del data["default_image_size"]
        path = write_json(tmp_path / "config.json", data)
        with pytest.raises(ValueError, match="'default_image_size' キーがありません"):
            load_config(path)

    def test_default_image_size_invalid(self, tmp_path):
        path = write_json(
            tmp_path / "config.json",
            valid_config(default_image_size={"width": 100, "height": 512}),
        )
        with pytest.raises(ValueError, match="default_image_size が不正です"):
            load_config(path)

    def test_default_image_size_not_multiple_of_8(self, tmp_path):
        path = write_json(
            tmp_path / "config.json",
            valid_config(default_image_size={"width": 513, "height": 512}),
        )
        with pytest.raises(ValueError, match="default_image_size が不正です"):
            load_config(path)


# ── resolve_loras ─────────────────────────────────────────────────────────────


class TestResolveLoras:
    def test_valid_multiple_loras(self):
        result = resolve_loras(["my_lora", "another_lora"], valid_lora_list())
        assert result == [
            {"name": "my_lora", "file": "my_lora.safetensors", "strength": 0.8},
            {
                "name": "another_lora",
                "file": "another_lora.safetensors",
                "strength": 0.7,
            },
        ]

    def test_valid_no_loras(self):
        assert resolve_loras([], valid_lora_list()) == []

    def test_unknown_lora_name(self):
        with pytest.raises(
            ValueError, match="'unknown_lora' が lora_list.json に存在しません"
        ):
            resolve_loras(["unknown_lora"], valid_lora_list())

    def test_partially_unknown_lora_names(self):
        with pytest.raises(
            ValueError, match="'missing' が lora_list.json に存在しません"
        ):
            resolve_loras(["my_lora", "missing"], valid_lora_list())


# ── WorkflowBuilder ───────────────────────────────────────────────────────────


class TestWorkflowBuilderSelectTemplate:
    def setup_method(self):
        self.builder = WorkflowBuilder(str(TEMPLATES_DIR))

    def test_zero_loras(self):
        assert self.builder.select_template(0).endswith("template_lora_0.json")

    def test_four_loras(self):
        assert self.builder.select_template(4).endswith("template_lora_4.json")

    @pytest.mark.parametrize("count", [0, 1, 2, 3, 4])
    def test_correct_template_selected(self, count):
        path = self.builder.select_template(count)
        assert Path(path).exists()
        assert f"template_lora_{count}.json" in path

    def test_templates_dir_not_found(self, tmp_path):
        builder = WorkflowBuilder(str(tmp_path / "no_dir"))
        with pytest.raises(ValueError, match="テンプレートファイルが見つかりません"):
            builder.select_template(0)

    def test_lora_count_out_of_range(self):
        with pytest.raises(ValueError, match="0〜4 個の範囲"):
            self.builder.select_template(5)


class TestWorkflowBuilderLoadTemplate:
    def setup_method(self):
        self.builder = WorkflowBuilder(str(TEMPLATES_DIR))

    def test_valid(self):
        path = str(TEMPLATES_DIR / "template_lora_1.json")
        assert isinstance(self.builder.load_template(path), dict)

    def test_file_not_found(self, tmp_path):
        with pytest.raises(ValueError, match="テンプレートファイルが見つかりません"):
            self.builder.load_template(str(tmp_path / "nonexistent.json"))

    def test_invalid_json(self, tmp_path):
        p = tmp_path / "template.json"
        p.write_text("not json", encoding="utf-8")
        with pytest.raises(ValueError, match="テンプレート JSON の解析に失敗しました"):
            self.builder.load_template(str(p))


class TestWorkflowBuilderApply:
    def setup_method(self):
        self.builder = WorkflowBuilder(str(TEMPLATES_DIR))

    def test_prompts_applied(self):
        wf = self.builder.apply(
            make_workflow(0),
            {"positive": "good quality", "negative": "bad quality"},
            [],
        )
        nodes = {n["_meta"]["title"]: n for n in wf.values()}
        assert nodes["positive_prompt"]["inputs"]["text"] == "good quality"
        assert nodes["negative_prompt"]["inputs"]["text"] == "bad quality"

    def test_single_lora_applied(self):
        loras = make_loras(1)
        wf = self.builder.apply(
            make_workflow(1), {"positive": "p", "negative": "n"}, loras
        )
        nodes = {n["_meta"]["title"]: n for n in wf.values()}
        assert nodes["lora_loader_1"]["inputs"]["lora_name"] == "lora1.safetensors"
        assert nodes["lora_loader_1"]["inputs"]["strength_model"] == pytest.approx(0.6)

    def test_four_loras_applied(self):
        loras = make_loras(4)
        wf = self.builder.apply(
            make_workflow(4), {"positive": "p", "negative": "n"}, loras
        )
        nodes = {n["_meta"]["title"]: n for n in wf.values()}
        for i in range(1, 5):
            assert (
                nodes[f"lora_loader_{i}"]["inputs"]["lora_name"]
                == f"lora{i}.safetensors"
            )

    def test_original_workflow_not_mutated(self):
        original = make_workflow(1)
        original_text = original["1"]["inputs"]["text"]
        self.builder.apply(
            original, {"positive": "changed", "negative": "n"}, make_loras(1)
        )
        assert original["1"]["inputs"]["text"] == original_text

    def test_missing_positive_prompt_node(self):
        wf = make_workflow(0)
        del wf["1"]
        with pytest.raises(ValueError, match="'positive_prompt' が見つかりません"):
            self.builder.apply(wf, {"positive": "p", "negative": "n"}, [])

    def test_missing_negative_prompt_node(self):
        wf = make_workflow(0)
        del wf["2"]
        with pytest.raises(ValueError, match="'negative_prompt' が見つかりません"):
            self.builder.apply(wf, {"positive": "p", "negative": "n"}, [])

    def test_seed_is_randomized(self):
        wf1 = self.builder.apply(
            make_workflow(0), {"positive": "p", "negative": "n"}, []
        )
        wf2 = self.builder.apply(
            make_workflow(0), {"positive": "p", "negative": "n"}, []
        )
        seed1 = wf1["99"]["inputs"]["seed"]
        seed2 = wf2["99"]["inputs"]["seed"]
        assert seed1 != 12345
        assert 0 <= seed1 <= 2**53
        assert seed1 != seed2

    def test_seed_can_be_fixed(self):
        wf = self.builder.apply(
            make_workflow(0), {"positive": "p", "negative": "n"}, [], seed=42
        )
        assert wf["99"]["inputs"]["seed"] == 42

    def test_same_seed_for_ksampler_and_facedetailer(self):
        wf = self.builder.apply(
            make_workflow(0), {"positive": "p", "negative": "n"}, [], seed=777
        )
        assert wf["99"]["inputs"]["seed"] == 777
        assert wf["98"]["inputs"]["seed"] == 777

    def test_facedetailer_seed_is_randomized(self):
        wf = self.builder.apply(
            make_workflow(0), {"positive": "p", "negative": "n"}, []
        )
        assert wf["98"]["inputs"]["seed"] != 99999
        assert wf["98"]["inputs"]["seed"] == wf["99"]["inputs"]["seed"]

    def test_no_error_without_ksampler(self):
        wf = make_workflow(0, with_sampler=False)
        result = self.builder.apply(wf, {"positive": "p", "negative": "n"}, [])
        assert "99" not in result

    def test_any_node_with_seed_input_is_randomized(self):
        wf = make_workflow(0, with_sampler=False)
        wf["50"] = {
            "class_type": "SomeCustomNode",
            "inputs": {"seed": 11111, "steps": 10},
            "_meta": {"title": "custom_node"},
        }
        result = self.builder.apply(
            wf, {"positive": "p", "negative": "n"}, [], seed=999
        )
        assert result["50"]["inputs"]["seed"] == 999

    def test_node_without_seed_input_is_not_modified(self):
        wf = make_workflow(0, with_sampler=False)
        wf["50"] = {
            "class_type": "KSampler",
            "inputs": {"steps": 20, "cfg": 7},
            "_meta": {"title": "no_seed_node"},
        }
        result = self.builder.apply(
            wf, {"positive": "p", "negative": "n"}, [], seed=999
        )
        assert "seed" not in result["50"]["inputs"]

    def test_image_size_applied(self):
        wf = self.builder.apply(
            make_workflow(0),
            {"positive": "p", "negative": "n"},
            [],
            image_size={"width": 768, "height": 1024},
        )
        nodes = {n["_meta"]["title"]: n for n in wf.values()}
        assert nodes["empty_latent_image"]["inputs"]["width"] == 768
        assert nodes["empty_latent_image"]["inputs"]["height"] == 1024

    def test_image_size_none_skips_latent_node(self):
        wf = self.builder.apply(
            make_workflow(0, with_latent=False),
            {"positive": "p", "negative": "n"},
            [],
            image_size=None,
        )
        assert "5" not in wf

    def test_image_size_missing_latent_node_raises(self):
        with pytest.raises(ValueError, match="'empty_latent_image' が見つかりません"):
            self.builder.apply(
                make_workflow(0, with_latent=False),
                {"positive": "p", "negative": "n"},
                [],
                image_size={"width": 512, "height": 512},
            )

    def test_missing_lora_loader_node(self):
        with pytest.raises(ValueError, match="'lora_loader_1' が見つかりません"):
            self.builder.apply(
                make_workflow(0), {"positive": "p", "negative": "n"}, make_loras(1)
            )

    def test_real_template_with_two_loras(self):
        workflow = self.builder.load_template(
            str(TEMPLATES_DIR / "template_lora_2.json")
        )
        loras = [
            {"name": "lora_a", "file": "lora_a.safetensors", "strength": 0.8},
            {"name": "lora_b", "file": "lora_b.safetensors", "strength": 0.6},
        ]
        wf = self.builder.apply(
            workflow, {"positive": "test positive", "negative": "test negative"}, loras
        )
        nodes = {n["_meta"]["title"]: n for n in wf.values()}
        assert nodes["positive_prompt"]["inputs"]["text"] == "test positive"
        assert nodes["lora_loader_1"]["inputs"]["lora_name"] == "lora_a.safetensors"
        assert nodes["lora_loader_2"]["inputs"]["lora_name"] == "lora_b.safetensors"


# ── ComfyUIClient.submit ──────────────────────────────────────────────────────


class TestComfyUIClientSubmit:
    def setup_method(self):
        self.client = ComfyUIClient("http://127.0.0.1:8188")

    def test_valid(self):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"prompt_id": "abc123"}
        with patch("run_workflow.requests.post", return_value=mock_resp) as mock_post:
            result = self.client.submit({"node": "data"}, "client-1")
        assert result == "abc123"
        call_kwargs = mock_post.call_args.kwargs
        assert call_kwargs["json"]["client_id"] == "client-1"

    def test_connection_error(self):
        with patch(
            "run_workflow.requests.post", side_effect=requests.ConnectionError()
        ):
            with pytest.raises(ValueError, match="ComfyUI に接続できません"):
                self.client.submit({}, "client-1")

    def test_timeout(self):
        with patch("run_workflow.requests.post", side_effect=requests.Timeout()):
            with pytest.raises(ValueError, match="タイムアウト"):
                self.client.submit({}, "client-1")

    def test_http_error(self):
        mock_resp = MagicMock()
        mock_resp.raise_for_status.side_effect = requests.HTTPError("500")
        with patch("run_workflow.requests.post", return_value=mock_resp):
            with pytest.raises(ValueError, match="ComfyUI がエラーを返しました"):
                self.client.submit({}, "client-1")


# ── ComfyUIClient._monitor_ws ─────────────────────────────────────────────────


class TestComfyUIClientMonitorWs:
    def setup_method(self):
        self.client = ComfyUIClient("http://127.0.0.1:8188")

    def _run(self, messages: list) -> None:
        msgs = messages

        class FakeWs:
            def __aiter__(self):
                async def gen():
                    for m in msgs:
                        yield m

                return gen()

        mock_cm = AsyncMock()
        mock_cm.__aenter__ = AsyncMock(return_value=FakeWs())
        mock_cm.__aexit__ = AsyncMock(return_value=False)
        with patch("run_workflow.websockets.connect", return_value=mock_cm):
            asyncio.run(self.client._monitor_ws("prompt-1", "ws://localhost/ws"))

    def test_completes_on_execution_complete(self):
        self._run(
            [make_ws_message(type="execution_complete", data={"prompt_id": "prompt-1"})]
        )

    def test_completes_on_executing_null_node(self):
        self._run(
            [
                make_ws_message(
                    type="executing", data={"node": None, "prompt_id": "prompt-1"}
                )
            ]
        )

    def test_ignores_different_prompt_id(self):
        self._run(
            [
                make_ws_message(type="execution_complete", data={"prompt_id": "other"}),
                make_ws_message(
                    type="execution_complete", data={"prompt_id": "prompt-1"}
                ),
            ]
        )

    def test_raises_on_execution_error(self):
        with pytest.raises(ValueError, match="CUDA OOM"):
            self._run(
                [
                    make_ws_message(
                        type="execution_error",
                        data={"prompt_id": "prompt-1", "exception_message": "CUDA OOM"},
                    )
                ]
            )

    def test_ignores_binary_frames(self):
        self._run(
            [
                b"\x89PNG\r\n\x1a\n",
                make_ws_message(
                    type="execution_complete", data={"prompt_id": "prompt-1"}
                ),
            ]
        )

    def test_websocket_connection_error(self):
        with patch("run_workflow.websockets.connect", side_effect=OSError("refused")):
            with pytest.raises(ValueError, match="WebSocket 接続エラー"):
                asyncio.run(self.client._monitor_ws("prompt-1", "ws://localhost/ws"))


# ── ComfyUIClient.get_outputs ─────────────────────────────────────────────────


class TestComfyUIClientGetOutputs:
    def setup_method(self):
        self.client = ComfyUIClient("http://127.0.0.1:8188")

    def _mock_history(self, images_by_node: dict) -> dict:
        return {
            "prompt-1": {
                "outputs": {
                    nid: {"images": imgs} for nid, imgs in images_by_node.items()
                }
            }
        }

    def test_valid_with_images(self):
        history = self._mock_history(
            {
                "9": [{"filename": "img1.png", "subfolder": "", "type": "output"}],
                "25": [{"filename": "img2.png", "subfolder": "", "type": "output"}],
            }
        )
        mock_resp = MagicMock()
        mock_resp.json.return_value = history
        with patch("run_workflow.requests.get", return_value=mock_resp):
            outputs = self.client.get_outputs("prompt-1")
        assert {o["filename"] for o in outputs} == {"img1.png", "img2.png"}

    def test_valid_no_outputs(self):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {}
        with patch("run_workflow.requests.get", return_value=mock_resp):
            assert self.client.get_outputs("prompt-1") == []

    def test_connection_error(self):
        with patch("run_workflow.requests.get", side_effect=requests.ConnectionError()):
            with pytest.raises(ValueError, match="ComfyUI に接続できません"):
                self.client.get_outputs("prompt-1")

    def test_timeout(self):
        with patch("run_workflow.requests.get", side_effect=requests.Timeout()):
            with pytest.raises(ValueError, match="タイムアウト"):
                self.client.get_outputs("prompt-1")


# ── WorkflowRunner.execute ────────────────────────────────────────────────────


class TestWorkflowRunnerExecute:
    def _make_runner(self, tmp_path) -> WorkflowRunner:
        path = write_json(tmp_path / "config.json", valid_config())
        return WorkflowRunner(path)

    def _mock_client(self, outputs: list) -> MagicMock:
        mock = MagicMock()
        mock.submit.return_value = "prompt-xyz"
        mock.monitor.return_value = None
        mock.get_outputs.return_value = outputs
        return mock

    def test_returns_outputs(self, tmp_path):
        runner = self._make_runner(tmp_path)
        expected = [{"filename": "img.png", "subfolder": "", "type": "output"}]
        with patch(
            "run_workflow.ComfyUIClient", return_value=self._mock_client(expected)
        ):
            assert (
                runner.execute(["my_lora"], {"positive": "good", "negative": "bad"})
                == expected
            )

    def test_stores_prompt_id(self, tmp_path):
        runner = self._make_runner(tmp_path)
        with patch("run_workflow.ComfyUIClient", return_value=self._mock_client([])):
            runner.execute(["my_lora"], {"positive": "good", "negative": "bad"})
        assert runner.prompt_id == "prompt-xyz"

    def test_stores_template_path(self, tmp_path):
        runner = self._make_runner(tmp_path)
        with patch("run_workflow.ComfyUIClient", return_value=self._mock_client([])):
            runner.execute([], {"positive": "good", "negative": "bad"})
        assert runner.template_path is not None
        assert "template_lora_0" in runner.template_path

    def test_stores_parameters(self, tmp_path):
        runner = self._make_runner(tmp_path)
        with patch("run_workflow.ComfyUIClient", return_value=self._mock_client([])):
            runner.execute(["my_lora"], {"positive": "good", "negative": "bad"})
        assert runner.parameters["positive"] == "good"
        assert runner.parameters["loras"][0]["name"] == "my_lora"

    def test_resets_state_on_each_call(self, tmp_path):
        runner = self._make_runner(tmp_path)
        with patch("run_workflow.ComfyUIClient", return_value=self._mock_client([])):
            runner.execute([], {"positive": "first", "negative": "bad"})
        with pytest.raises(ValueError):
            runner.execute(["unknown"], {"positive": "second", "negative": "bad"})
        assert runner.parameters == {}
        assert runner.template_path is None
        assert runner.prompt_id is None

    def test_raises_on_unknown_lora(self, tmp_path):
        runner = self._make_runner(tmp_path)
        with pytest.raises(ValueError, match="lora_list.json に存在しません"):
            runner.execute(["unknown_lora"], {"positive": "good", "negative": "bad"})

    def test_raises_on_prompt_too_long(self, tmp_path):
        runner = self._make_runner(tmp_path)
        with pytest.raises(ValueError, match="長すぎます"):
            runner.execute(
                [], {"positive": "a" * (MAX_PROMPT_LENGTH + 1), "negative": "bad"}
            )

    def test_raises_on_comfyui_connection_error(self, tmp_path):
        runner = self._make_runner(tmp_path)
        with patch("run_workflow.ComfyUIClient") as mock_cls:
            mock_cls.return_value.submit.side_effect = ValueError(
                "ComfyUI に接続できません"
            )
            with pytest.raises(ValueError, match="接続できません"):
                runner.execute([], {"positive": "good", "negative": "bad"})

    def test_uses_default_image_size_when_not_specified(self, tmp_path):
        runner = self._make_runner(tmp_path)
        with patch("run_workflow.ComfyUIClient", return_value=self._mock_client([])):
            runner.execute([], {"positive": "good", "negative": "bad"})
        assert runner.parameters["image_size"] == {"width": 512, "height": 512}

    def test_uses_given_image_size(self, tmp_path):
        runner = self._make_runner(tmp_path)
        with patch("run_workflow.ComfyUIClient", return_value=self._mock_client([])):
            runner.execute(
                [],
                {"positive": "good", "negative": "bad"},
                image_size={"width": 768, "height": 1024},
            )
        assert runner.parameters["image_size"] == {"width": 768, "height": 1024}

    def test_raises_on_invalid_image_size(self, tmp_path):
        runner = self._make_runner(tmp_path)
        with pytest.raises(ValueError, match="8 の倍数"):
            runner.execute(
                [],
                {"positive": "good", "negative": "bad"},
                image_size={"width": 513, "height": 512},
            )


# ── WorkflowRunner.run ────────────────────────────────────────────────────────


class TestWorkflowRunnerRun:
    def _make_runner(self, tmp_path) -> WorkflowRunner:
        path = write_json(tmp_path / "config.json", valid_config())
        return WorkflowRunner(path)

    def _mock_client(self, outputs: list) -> MagicMock:
        mock = MagicMock()
        mock.submit.return_value = "prompt-xyz"
        mock.monitor.return_value = None
        mock.get_outputs.return_value = outputs
        return mock

    def test_writes_success_result(self, tmp_path):
        runner = self._make_runner(tmp_path)
        input_path = write_json(tmp_path / "input.json", valid_input())
        output_path = str(tmp_path / "result.json")
        outputs = [{"filename": "img.png", "subfolder": "", "type": "output"}]
        with patch(
            "run_workflow.ComfyUIClient", return_value=self._mock_client(outputs)
        ):
            runner.run(input_path, output_path)
        result = json.loads(Path(output_path).read_text(encoding="utf-8"))
        assert result["status"] == "success"
        assert result["prompt_id"] == "prompt-xyz"
        assert result["outputs"] == outputs

    def test_writes_error_result_on_invalid_input(self, tmp_path):
        runner = self._make_runner(tmp_path)
        input_path = write_json(tmp_path / "input.json", valid_input(loras=["unknown"]))
        output_path = str(tmp_path / "result.json")
        with pytest.raises(SystemExit):
            runner.run(input_path, output_path)
        result = json.loads(Path(output_path).read_text(encoding="utf-8"))
        assert result["status"] == "error"
        assert result["error"] is not None

    def test_exits_with_code_1_on_error(self, tmp_path):
        runner = self._make_runner(tmp_path)
        input_path = write_json(tmp_path / "input.json", valid_input(loras=["unknown"]))
        output_path = str(tmp_path / "result.json")
        with pytest.raises(SystemExit) as exc_info:
            runner.run(input_path, output_path)
        assert exc_info.value.code == 1

    def test_writes_error_on_comfyui_failure(self, tmp_path):
        runner = self._make_runner(tmp_path)
        input_path = write_json(tmp_path / "input.json", valid_input())
        output_path = str(tmp_path / "result.json")
        with patch("run_workflow.ComfyUIClient") as mock_cls:
            mock_cls.return_value.submit.side_effect = ValueError("接続失敗")
            with pytest.raises(SystemExit):
                runner.run(input_path, output_path)
        result = json.loads(Path(output_path).read_text(encoding="utf-8"))
        assert result["status"] == "error"
        assert "接続失敗" in result["error"]

    def test_image_size_in_result_parameters(self, tmp_path):
        runner = self._make_runner(tmp_path)
        input_path = write_json(
            tmp_path / "input.json",
            valid_input(image_size={"width": 768, "height": 1024}),
        )
        output_path = str(tmp_path / "result.json")
        with patch("run_workflow.ComfyUIClient", return_value=self._mock_client([])):
            runner.run(input_path, output_path)
        result = json.loads(Path(output_path).read_text(encoding="utf-8"))
        assert result["parameters"]["image_size"] == {"width": 768, "height": 1024}

    def test_default_image_size_used_when_omitted(self, tmp_path):
        runner = self._make_runner(tmp_path)
        input_path = write_json(tmp_path / "input.json", valid_input())
        output_path = str(tmp_path / "result.json")
        with patch("run_workflow.ComfyUIClient", return_value=self._mock_client([])):
            runner.run(input_path, output_path)
        result = json.loads(Path(output_path).read_text(encoding="utf-8"))
        assert result["parameters"]["image_size"] == {"width": 512, "height": 512}

    def test_invalid_image_size_writes_error_result(self, tmp_path):
        runner = self._make_runner(tmp_path)
        input_path = write_json(
            tmp_path / "input.json",
            valid_input(image_size={"width": 513, "height": 512}),
        )
        output_path = str(tmp_path / "result.json")
        with pytest.raises(SystemExit):
            runner.run(input_path, output_path)
        result = json.loads(Path(output_path).read_text(encoding="utf-8"))
        assert result["status"] == "error"
        assert "8 の倍数" in result["error"]


# ── write_result ──────────────────────────────────────────────────────────────


class TestWriteResult:
    def test_error_result_json(self, tmp_path):
        out = str(tmp_path / "result.json")
        write_result(out, "error", "接続失敗")
        result = json.loads(Path(out).read_text(encoding="utf-8"))
        assert result["status"] == "error"
        assert result["error"] == "接続失敗"
        assert result["outputs"] == []
        assert result["prompt_id"] is None
        assert result["template"] is None

    def test_success_result_json(self, tmp_path):
        out = str(tmp_path / "result.json")
        outputs = [{"filename": "img.png", "subfolder": "", "type": "output"}]
        write_result(
            out,
            "success",
            None,
            parameters={"positive": "good", "loras": []},
            template=".templates/template_lora_0.json",
            prompt_id="abc123",
            outputs=outputs,
        )
        result = json.loads(Path(out).read_text(encoding="utf-8"))
        assert result["status"] == "success"
        assert result["prompt_id"] == "abc123"
        assert result["template"] == ".templates/template_lora_0.json"
        assert result["outputs"] == outputs
