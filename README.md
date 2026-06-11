# comfyui_tools

ComfyUI 関連の Python ユーティリティ集。各ツールはサブディレクトリとして独立しています。

## ツール一覧

| ツール | 説明 |
|---|---|
| [`run_workflow/`](run_workflow/README.md) | ComfyUI のワークフローを Python から自動実行するツール |
| [`generate_image_bot/`](generate_image_bot/README.md) | Discord のメンションで ComfyUI に画像生成を指示し、生成された画像を返送する Discord ボット |

## サブモジュール

| サブモジュール | リポジトリ | 説明 |
|---|---|---|
| [`sd_scripts/`](sd_scripts/) | [kohya-ss/sd-scripts](https://github.com/kohya-ss/sd-scripts) | Stable Diffusion 系モデルのファインチューニング・LoRA 学習スクリプト集 |

初回クローン時はサブモジュールの初期化が必要です。

```bash
git submodule update --init
```

## ライセンス

[MIT](LICENSE)
