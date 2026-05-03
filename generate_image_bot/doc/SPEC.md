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
    generate_image_bot.py  # エントリポイント（起動・再接続ループ）
    config.json            # ボット設定（トークン・パス等）
    requirements.txt       # 依存ライブラリ
    doc/
      SPEC.md              # 本ファイル
      SPEC/                # セクション別仕様書
      USERS_MANUAL.md
    modules/
      image_bot.py         # ImageBot クラス
      gen_image_modal.py   # GenImageModal クラス
      message_parser.py    # MessageParser クラス
      rate_limiter.py      # RateLimiter クラス
      load_config.py       # 設定ファイルの読み込み・バリデーション
      common_lib.py        # ログ書き込み等の共通処理
      const.py             # 定数定義
    log/                   # ログ出力ディレクトリ（自動生成）
      YYYYMMDD/            # 日付ディレクトリ（自動生成）
        result_hhmmss_ffffff.json
        system_hhmmss_ffffff.json
        discord_hhmmss_ffffff.json
    test/
      conftest.py
      test_image_bot.py
      test_gen_image_modal.py
      test_message_parser.py
      test_rate_limiter.py
      test_load_config.py
      test_common_lib.py
      test_helper.py
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
