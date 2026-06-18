"""run_workflow.py のユニットテスト"""

import json
import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch

from test_helper import (
    write_json,
    valid_input,
    valid_lora_list,
    valid_config,
    valid_workflow_config,
)

from run_workflow import (
    resolve_loras,
    write_result,
    WorkflowRunner,
    _run_tagger,
)

from modules.load_files import (
    MAX_PROMPT_LENGTH,
)

TEMPLATES_DIR = Path(__file__).parent.parent / "templates"


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
            ValueError, match="'unknown_lora' が config.json の loras 設定に存在しません"
        ):
            resolve_loras(["unknown_lora"], valid_lora_list())

    def test_partially_unknown_lora_names(self):
        with pytest.raises(
            ValueError, match="'missing' が config.json の loras 設定に存在しません"
        ):
            resolve_loras(["my_lora", "missing"], valid_lora_list())


# ── WorkflowRunner.execute ────────────────────────────────────────────────────


class TestWorkflowRunnerExecute:
    def _make_runner(self, tmp_path, workflow_name=None) -> WorkflowRunner:
        path = write_json(tmp_path / "config.json", valid_config())
        return WorkflowRunner(path, workflow_name=workflow_name)

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
        with pytest.raises(ValueError, match="config.json の loras 設定に存在しません"):
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
        assert (
            runner.parameters["image_size"]
            == valid_config()["workflows"]["sdxl"]["default_image_size"]
        )

    def test_uses_workflow_specific_loras(self, tmp_path):
        runner = self._make_runner(tmp_path)
        with patch("run_workflow.ComfyUIClient", return_value=self._mock_client([])):
            runner.execute(["my_lora"], {"positive": "good", "negative": "bad"})
        assert runner.parameters["loras"][0]["name"] == "my_lora"

    def test_raises_on_unknown_workflow(self, tmp_path):
        path = write_json(tmp_path / "config.json", valid_config())
        with pytest.raises(ValueError, match="workflows に存在しません"):
            WorkflowRunner(path, workflow_name="unknown_workflow")

    def test_uses_default_workflow_when_not_specified(self, tmp_path):
        runner = self._make_runner(tmp_path)
        assert runner._workflow_name == "sdxl"

    def test_uses_given_workflow_name(self, tmp_path):
        path = write_json(
            tmp_path / "config.json",
            valid_config(
                workflows={
                    "sdxl": valid_workflow_config(),
                    "sd15": valid_workflow_config(),
                }
            ),
        )
        runner = WorkflowRunner(path, workflow_name="sd15")
        assert runner._workflow_name == "sd15"

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

    def test_get_image_size_vertical(self, tmp_path):
        runner = self._make_runner(tmp_path)
        size = runner.get_image_size("vertical")
        assert size == {"width": 832, "height": 1216}

    def test_get_image_size_horizontal(self, tmp_path):
        runner = self._make_runner(tmp_path)
        size = runner.get_image_size("horizontal")
        assert size == {"width": 1216, "height": 832}

    def test_get_image_size_square(self, tmp_path):
        runner = self._make_runner(tmp_path)
        size = runner.get_image_size("square")
        assert size == {"width": 1024, "height": 1024}


# ── WorkflowRunner.run ────────────────────────────────────────────────────────


class TestWorkflowRunnerRun:
    def _make_runner(self, tmp_path, workflow_name=None) -> WorkflowRunner:
        path = write_json(tmp_path / "config.json", valid_config())
        return WorkflowRunner(path, workflow_name=workflow_name)

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
        expected = valid_config()["workflows"]["sdxl"]["default_image_size"]
        assert result["parameters"]["image_size"] == expected

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


# ── main (unknown workflow) ───────────────────────────────────────────────────


class TestMainUnknownWorkflow:
    def test_writes_error_result_on_unknown_workflow(self, tmp_path):
        config_path = write_json(tmp_path / "config.json", valid_config())
        input_path = write_json(tmp_path / "input.json", valid_input())
        output_path = str(tmp_path / "result.json")
        with patch(
            "sys.argv",
            [
                "run_workflow.py",
                "-i",
                input_path,
                "-w",
                "unknown_workflow",
                "-o",
                output_path,
                "-c",
                config_path,
            ],
        ):
            with pytest.raises(SystemExit) as exc_info:
                from run_workflow import main

                main()
        assert exc_info.value.code == 1
        result = json.loads(Path(output_path).read_text(encoding="utf-8"))
        assert result["status"] == "error"
        assert "unknown_workflow" in result["error"]

    def test_exits_with_code_1_on_unknown_workflow(self, tmp_path):
        config_path = write_json(tmp_path / "config.json", valid_config())
        input_path = write_json(tmp_path / "input.json", valid_input())
        output_path = str(tmp_path / "result.json")
        with patch(
            "sys.argv",
            [
                "run_workflow.py",
                "-i",
                input_path,
                "-w",
                "unknown_workflow",
                "-o",
                output_path,
                "-c",
                config_path,
            ],
        ):
            with pytest.raises(SystemExit) as exc_info:
                from run_workflow import main

                main()
        assert exc_info.value.code == 1


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


# ── _run_tagger ───────────────────────────────────────────────────────────────


class TestRunTagger:
    def _mock_runner(self, tags: str) -> MagicMock:
        mock = MagicMock()
        mock.tag.return_value = tags
        return mock

    def test_prints_tags(self, tmp_path, capsys):
        image_path = tmp_path / "photo.jpg"
        image_path.write_bytes(b"fake_image")
        with patch(
            "run_workflow.Wd14TaggerRunner",
            return_value=self._mock_runner("1girl, solo"),
        ):
            _run_tagger("config.json", str(image_path))
        assert capsys.readouterr().out.strip() == "1girl, solo"

    def test_passes_image_filename_to_tag(self, tmp_path):
        image_path = tmp_path / "photo.jpg"
        image_path.write_bytes(b"fake_image")
        mock_runner = self._mock_runner("1girl")
        with patch("run_workflow.Wd14TaggerRunner", return_value=mock_runner):
            _run_tagger("config.json", str(image_path))
        mock_runner.tag.assert_called_once_with(b"fake_image", "photo.jpg")

    def test_exits_on_value_error(self, tmp_path):
        image_path = tmp_path / "photo.jpg"
        image_path.write_bytes(b"fake_image")
        mock_runner = MagicMock()
        mock_runner.tag.side_effect = ValueError("接続エラー")
        with patch("run_workflow.Wd14TaggerRunner", return_value=mock_runner):
            with pytest.raises(SystemExit) as exc_info:
                _run_tagger("config.json", str(image_path))
        assert exc_info.value.code == 1

    def test_exits_on_file_not_found(self, tmp_path):
        with pytest.raises(SystemExit) as exc_info:
            _run_tagger("config.json", str(tmp_path / "nonexistent.jpg"))
        assert exc_info.value.code == 1
