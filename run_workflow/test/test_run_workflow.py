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
)

from run_workflow import (
    resolve_loras,
    write_result,
    WorkflowRunner,
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
            ValueError, match="'unknown_lora' が lora_list.json に存在しません"
        ):
            resolve_loras(["unknown_lora"], valid_lora_list())

    def test_partially_unknown_lora_names(self):
        with pytest.raises(
            ValueError, match="'missing' が lora_list.json に存在しません"
        ):
            resolve_loras(["my_lora", "missing"], valid_lora_list())


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
