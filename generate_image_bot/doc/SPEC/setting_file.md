# generate_image_bot.py 仕様書 -設定ファイル-

## 設定ファイル

### config.json

```json
{
  "discord_token": "YOUR_DISCORD_BOT_TOKEN",
  "comfyui_output_dir": "C:/path/to/ComfyUI/output",
  "run_workflow_config": "../run_workflow/config.json",
  "shutdown_time": "03:00",
  "reactions": {
    "processing": "⏳",
    "success": "✅",
    "error": "❌"
  },
  "messages": {
    "rate_limit": "リクエストが連続しています。あと {remaining_seconds} 秒待ってから再試行してください。",
    "concurrent_limit": "リクエストの同時処理上限に達しています。しばらくお待ちください。",
    "parse_error": "メッセージの形式が正しくありません:\n{error}",
    "execution_error": "生成に失敗しました:\n{error}",
    "file_too_large": "画像ファイルが大きすぎます（{size_mb} MB）",
    "unexpected_error": "予期しないエラーが発生しました",
    "dm_not_supported": "DM からは使用できません。サーバーのチャンネルで実行してください。",
    "shutdown_in_progress": "ボットはシャットダウン中です。しばらくしてから再試行してください。",
    "invalid_workflow": "ワークフロー '{workflow}' は存在しません。"
  }
}
```

| キー | 説明 |
|---|---|
| `discord_token` | Discord Bot トークン |
| `comfyui_output_dir` | ComfyUI の output フォルダへの絶対パス |
| `run_workflow_config` | `run_workflow/config.json` へのパス（相対 or 絶対） |
| `shutdown_time` | ボットを停止する時刻（後述）。省略または `null` で停止なし |
| `reactions` | ボットが付けるリアクション絵文字（後述） |
| `messages` | ボットが返信するメッセージのテンプレート（後述） |

> **注意**: `image_size` はこの設定ファイルでは定義しない。各ワークフローの `image_size` は `run_workflow/config.json` の `workflows.<workflow_name>.image_size` で管理する。

### shutdown_time

| 設定値 | 動作 |
|---|---|
| 省略 または `null` | 自動停止しない |
| `"hh:mm"` 形式の文字列（例: `"03:00"`） | 毎日その時刻にボットを停止する |

- 曜日・日付は考慮しない（毎日同じ時刻に停止する）
- 停止時刻になると新規リクエストの受付を停止し、処理中のリクエストが完了してからボットを終了する
- 形式が不正な場合（`hh:mm` 以外、または存在しない時刻）は起動時にエラーとなる
- ボット起動時に停止時刻をコンソールに出力する

### reactions

| キー | デフォルト | 説明 |
|---|---|---|
| `processing` | `⏳` | 処理中に付与し、処理完了後に削除するリアクション |
| `success` | `✅` | 生成成功時に付与するリアクション |
| `error` | `❌` | エラー時に付与するリアクション |

Unicode 絵文字（例: `⏳`）とカスタム絵文字（例: `<:name:id>`）の両方を指定できる。

### messages テンプレート

`messages` の各値は Python の `str.format()` 形式で記述し、プレースホルダーは以下の通り。

| キー | 使用プレースホルダー | 説明 |
|---|---|---|
| `rate_limit` | `{remaining_seconds}` | レート制限中の返信。残り待機秒数を埋め込む |
| `concurrent_limit` | なし | 同一ユーザーの同時リクエスト上限超過時の返信 |
| `parse_error` | `{error}` | フォーマット不正時の返信。パースエラー内容を埋め込む |
| `execution_error` | `{error}` | ワークフロー実行失敗時の返信。エラー内容を埋め込む（内部ファイルパスが含まれる場合があるため、公開サーバーでは固定文字列への変更を推奨） |
| `file_too_large` | `{size_mb}` | ファイルサイズ超過時の返信。ファイルサイズ（MB・小数点1桁）を埋め込む |
| `unexpected_error` | なし | 予期しない例外発生時の返信 |
| `dm_not_supported` | なし | スラッシュコマンドを DM から実行した場合の ephemeral 返信 |
| `shutdown_in_progress` | なし | シャットダウン要求中にスラッシュコマンドを実行した場合の ephemeral 返信 |
| `invalid_workflow` | `{workflow}` | 存在しないワークフロー名が指定された場合の返信。ワークフロー名を埋め込む |

プレースホルダーを省略した場合、そのまま固定文字列として使用する。
プレースホルダーの名前は変更・削除不可。未知のプレースホルダーを追加してもエラーにはならない（無視される）。
