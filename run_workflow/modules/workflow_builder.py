import copy
import json
import random
from pathlib import Path


class WorkflowBuilder:
    def __init__(self, templates_dir: str):
        self.templates_dir = Path(templates_dir)

    def select_template(self, lora_count: int, workflow_name: str) -> str:
        """ワークフロー名と LoRA 数に応じたテンプレートを選択する"""
        if not 0 <= lora_count <= 4:
            raise ValueError(
                f"LoRA は 0〜4 個の範囲で指定してください（指定数: {lora_count}）"
            )
        workflow_dir = self.templates_dir / workflow_name
        if not workflow_dir.exists():
            raise ValueError(
                f"テンプレートディレクトリが見つかりません: {workflow_name}"
            )
        path = workflow_dir / f"template_lora_{lora_count}.json"
        if not path.exists():
            raise ValueError(
                f"テンプレートファイルが見つかりません: {workflow_name}/template_lora_{lora_count}.json"
            )
        return str(path)

    def load_template(self, template_path: str) -> dict:
        """テンプレートファイルを読み込む"""
        name = Path(template_path).name
        try:
            with open(template_path, encoding="utf-8") as f:
                return json.load(f)
        except FileNotFoundError:
            raise ValueError(f"テンプレートファイルが見つかりません: {name}")
        except json.JSONDecodeError as e:
            raise ValueError(f"テンプレート JSON の解析に失敗しました ({name}): {e}")

    def apply(
        self,
        workflow: dict,
        prompts: dict,
        resolved_loras: list[dict],
        seed: int | None = None,
        image_size: dict | None = None,
    ) -> dict:
        """テンプレートにプロンプトや LoRA、画像サイズ、シードを適用してワークフローを構築する"""
        # テンプレートを直接書き換えないよう deepcopy してから処理する
        workflow = copy.deepcopy(workflow)
        # ComfyUI API 形式はノード ID がキーのフラット辞書のため、_meta.title で書き換え対象を特定する
        title_map = {
            node["_meta"]["title"]: node
            for node in workflow.values()
            if isinstance(node, dict) and "_meta" in node
        }
        self._apply_prompts(title_map, prompts)
        self._apply_loras(title_map, resolved_loras)
        if image_size is not None:
            self._apply_image_size(title_map, image_size)
        self._apply_seeds(
            workflow, seed if seed is not None else random.randint(0, 2**53)
        )
        return workflow

    def _apply_prompts(self, title_map: dict, prompts: dict) -> None:
        """テンプレートのプロンプトノードに、ユーザーから受け取ったプロンプトを適用する"""
        for key, field in (
            ("positive_prompt", "positive"),
            ("negative_prompt", "negative"),
        ):
            if key not in title_map:
                raise ValueError(f"テンプレートにノード '{key}' が見つかりません")
            title_map[key]["inputs"]["text"] = prompts[field]

    def _apply_image_size(self, title_map: dict, image_size: dict) -> None:
        """テンプレートの画像サイズノードに、ユーザーから受け取った画像サイズを適用する"""
        key = "empty_latent_image"
        if key not in title_map:
            raise ValueError(f"テンプレートにノード '{key}' が見つかりません")
        title_map[key]["inputs"]["width"] = image_size["width"]
        title_map[key]["inputs"]["height"] = image_size["height"]

    def _apply_loras(self, title_map: dict, resolved_loras: list[dict]) -> None:
        """テンプレートの LoRA ノードに、ユーザーから受け取った LoRA を適用する"""
        for i, lora in enumerate(resolved_loras, start=1):
            key = f"lora_loader_{i}"
            if key not in title_map:
                raise ValueError(f"テンプレートにノード '{key}' が見つかりません")
            title_map[key]["inputs"]["lora_name"] = lora["file"]
            title_map[key]["inputs"]["strength_model"] = lora["strength"]

    def _apply_seeds(self, workflow: dict, seed: int) -> None:
        """テンプレートのシード値を、ユーザーから受け取ったシードで統一する"""
        # inputs.seed を持つすべてのノードに同一 seed を設定する
        for node in workflow.values():
            if (
                isinstance(node, dict)
                and isinstance(node.get("inputs"), dict)
                and "seed" in node["inputs"]
            ):
                node["inputs"]["seed"] = seed
