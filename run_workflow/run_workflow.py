"""ComfyUI ワークフロー自動実行スクリプト"""

import argparse
import json
import sys
import uuid
from datetime import datetime
from pathlib import Path

from modules.comfyui_client import ComfyUIClient
from modules.workflow_builder import WorkflowBuilder
from modules.load_files import (
    load_config,
    validate_inputs,
    load_and_validate_input,
)

# ── 結果出力 ──────────────────────────────────────────────────────────────────


def write_result(
    output_path: str,
    status: str,
    error: str | None,
    parameters: dict | None = None,
    template: str | None = None,
    prompt_id: str | None = None,
    outputs: list | None = None,
):
    result = {
        "status": status,
        "prompt_id": prompt_id,
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "template": template,
        "parameters": parameters or {},
        "outputs": outputs or [],
        "error": error,
    }
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)


# ── LoRA 解決 ─────────────────────────────────────────────────────────────────


def resolve_loras(lora_names: list[str], lora_list: dict) -> list[dict]:
    # ユーザーが指定した LoRA 名を、config.json に定義された実ファイル名・強度に変換する
    resolved = []
    for name in lora_names:
        if name not in lora_list:
            raise ValueError(f"LoRA '{name}' が lora_list.json に存在しません")
        entry = lora_list[name]
        resolved.append(
            {"name": name, "file": entry["file"], "strength": entry["strength"]}
        )
    return resolved


# ── ワークフロー実行 ──────────────────────────────────────────────────────────


class WorkflowRunner:
    """ComfyUI ワークフローの実行を担うクラス。Discord ボット等から import して使用する。"""

    def __init__(self, config_path: str = "config.json"):
        self.config = load_config(config_path)
        self._templates_dir = str(Path(__file__).parent / "templates")

        # execute() 実行後に結果を保持する属性。run() が result.json 出力に使用する
        self.template_path: str | None = None
        self.prompt_id: str | None = None
        self.parameters: dict = {}

    def execute(
        self, loras: list[str], prompts: dict, image_size: dict | None = None
    ) -> list[dict]:
        """ワークフローを実行し、出力ファイル一覧を返す。エラー時は ValueError を送出。
        スレッドセーフ: 内部処理はローカル変数で完結し、インスタンス変数は完了後に書き戻す。"""
        self.template_path = None
        self.prompt_id = None
        self.parameters = {}

        # 入力を検証する
        validate_inputs(loras, prompts, image_size)

        # 画像サイズの決定。入力に指定があればそれを使い、なければ config.json の default_image_size を使う
        effective_image_size = (
            image_size if image_size is not None else self.config["default_image_size"]
        )

        # LoRA 名の解決。ユーザーが指定した LoRA 名を、config.json に定義された実ファイル名・強度に変換する
        resolved = resolve_loras(loras, self.config["loras"])
        parameters = {
            "positive": prompts["positive"],
            "negative": prompts["negative"],
            "loras": resolved,
            "image_size": effective_image_size,
        }

        # ワークフローの構築
        builder = WorkflowBuilder(self._templates_dir)
        template_path = builder.select_template(len(resolved))
        workflow = builder.load_template(template_path)
        workflow = builder.apply(
            workflow, prompts, resolved, image_size=effective_image_size
        )

        # ワークフローの送信と実行完了待機
        client = ComfyUIClient(self.config["comfyui_url"])
        client_id = str(uuid.uuid4())
        print(f"ワークフロー送信中: {self.config['comfyui_url']}")
        prompt_id = client.submit(workflow, client_id)
        print(f"送信完了 prompt_id={prompt_id}")
        print("実行完了を待機中...")
        client.monitor(prompt_id, client_id)
        outputs = client.get_outputs(prompt_id)
        print(f"出力ファイル数: {len(outputs)}")

        # run() が result.json 出力に使用するため、完了後にインスタンス変数へ書き戻す
        self.template_path = template_path
        self.prompt_id = prompt_id
        self.parameters = parameters
        return outputs

    def run(self, input_path: str, output_path: str) -> None:
        """入力ファイルを読み込んでワークフローを実行し、結果を output_path に書き出す。"""
        try:
            input_data = load_and_validate_input(input_path)
            outputs = self.execute(
                input_data["loras"],
                input_data["prompts"],
                input_data.get("image_size"),
            )
        except ValueError as e:
            write_result(
                output_path,
                "error",
                str(e),
                parameters=self.parameters,
                template=self.template_path,
            )
            print(f"エラー: {e}", file=sys.stderr)
            sys.exit(1)

        write_result(
            output_path,
            "success",
            None,
            parameters=self.parameters,
            template=self.template_path,
            prompt_id=self.prompt_id,
            outputs=outputs,
        )
        print(f"結果を保存しました: {output_path}")


# ── エントリポイント ──────────────────────────────────────────────────────────


def main():
    parser = argparse.ArgumentParser(description="ComfyUI ワークフロー自動実行")
    parser.add_argument("-i", "--input", required=True, help="入力 JSON ファイルのパス")
    default_output = f"result_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}.json"
    parser.add_argument(
        "-o",
        "--output",
        default=default_output,
        help="結果 JSON の出力先（省略時: タイムスタンプ付きファイル名）",
    )
    parser.add_argument(
        "-c",
        "--config",
        default="config.json",
        help="設定ファイルのパス（省略時: config.json）",
    )
    args = parser.parse_args()

    WorkflowRunner(args.config).run(args.input, args.output)


if __name__ == "__main__":
    main()
