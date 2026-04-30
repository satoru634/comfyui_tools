"""workflow_builder.py のユニットテスト"""

import pytest
from pathlib import Path

from test_helper import (
    make_workflow,
    make_loras,
)

from modules.workflow_builder import (
    WorkflowBuilder,
)

TEMPLATES_DIR = Path(__file__).parent.parent / "templates"


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
