# comfyui_tools

ComfyUI 関連の Python ユーティリティ集。各ツールはサブディレクトリとして独立しています。

## セットアップ

`setup/` ディレクトリにある初期化スクリプトを実行すると、仮想環境の作成と依存ライブラリのインストールが行われます。

**Windows:**
```bat
setup\setup_venv.bat
```

**Linux / macOS:**
```bash
bash setup/setup_venv.sh
```

実行後、以下のコマンドで仮想環境をアクティベートしてください。

**Windows:**
```bat
.venv\Scripts\activate
```

**Linux / macOS:**
```bash
source .venv/bin/activate
```

## ツール一覧

| ツール | 説明 |
|---|---|
| [`run_workflow/`](run_workflow/README.md) | ComfyUI のワークフローを Python から自動実行するツール |
| [`generate_image_bot/`](generate_image_bot/README.md) | Discord のメンションで ComfyUI に画像生成を指示し、生成された画像を返送する Discord ボット |
| [`captioning_tool/`](captioning_tool/README.md) | ディレクトリ内の画像を WD Timm Tagger で一括タグ付けし、`.txt` キャプションファイルを生成するツール |

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
