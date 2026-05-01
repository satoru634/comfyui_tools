# generate_image_bot.py 仕様書

## 概要

Discord のメンションで ComfyUI に画像生成を指示し、生成された画像を Discord に返送するボット。
`run_workflow/run_workflow.py` の `WorkflowRunner` を import して利用する。

画像生成のトリガーは以下の 2 種類：

- **メンションメッセージ**: ボットへのメンションにキーワード形式でプロンプトを付けて送信する（既存機能）
- **スラッシュコマンド** (`/gen_image`): コマンドを実行するとモーダルが開き、フォームに入力して送信する

## ファイル構成

```
comfyui_tools/
  run_workflow/
    run_workflow.py        # 画像生成エンジン（import して使用）
    config.json            # ComfyUI 接続設定・LoRAマッピング
    templates/             # ワークフローテンプレート
  generate_image_bot/
    generate_image_bot.py  # メインボットスクリプト
    config.json            # ボット設定（トークン・パス等）
    SPEC.md                # 本ファイル
    requirements.txt       # 依存ライブラリ
    log/                   # ログ出力ディレクトリ（自動生成）
      result_YYYYMMDD_hhmmss.json
    test/
      test_generate_image_bot.py
```

## 設定ファイル

[設定ファイル](./SPEC/setting_file.md)を参照。

## 入力インターフェース

[入力インターフェース](./SPEC/io_interface.md)を参照。

## 処理概要

[処理概要](./SPEC/processing_overview.md)を参照。

## 出力

[出力](./SPEC/outputs.md)を参照。

## エラーハンドリング

[エラーハンドリング](./SPEC/errors.md)を参照。

## その他

[その他](./SPEC/others.md)を参照。
