# generate_image_bot.py 仕様書 -出力-

## 出力

- 成功時: 生成画像ファイルを Discord のメッセージに添付して返信する
- 複数画像が生成された場合は、すべてを1件のメッセージにまとめて添付する
- `type` が `output` のファイルのみ送信対象とする（`temp` 等は無視する）
- 送信前に各ファイルのサイズをチェックし、**1ファイルでも 10MB 以上**であればエラーとして扱う
- エラー時: エラー内容を文字列でメッセージ返信する

## ログ出力

### 概要

画像生成を試みた際（グローバルロック取得後）のリクエスト結果を `log/` ディレクトリに JSON 形式で保存する。
ログはデバッグ・運用監視を目的とし、ユーザー非公開の内部記録として使用する。

### ログファイルパス

```
generate_image_bot/log/result_YYYYMMDD_hhmmss.json
```

- `log/` ディレクトリが存在しない場合は自動生成する。
- ファイル名はリクエスト処理時刻から生成する（`datetime.now()` ベース）。

### ログ出力タイミング

| 状況 | ログ出力 |
|---|---|
| 生成成功 | あり（status: success） |
| `WorkflowRunner.execute()` が ValueError | あり（status: error） |
| 予期しない例外 | あり（status: error） |
| `_resolve_files()` で ValueError | あり（status: error） |
| パースエラー | なし（生成を開始していないため） |
| レート制限 | なし（生成を開始していないため） |
| グローバルロック中 | なし（生成を開始していないため） |

### ログ JSON フォーマット

```json
{
  "status": "success",
  "timestamp": "2026-04-25T12:34:56",
  "user_id": 123456789,
  "username": "discord_username",
  "loras": ["lora1"],
  "positive": "masterpiece, 1girl",
  "negative": "worst quality",
  "image_orientation": "vertical",
  "outputs": [{"filename": "output.png", "subfolder": "", "type": "output"}],
  "error": null
}
```

| フィールド | 型 | 説明 |
|---|---|---|
| `status` | string | `"success"` または `"error"` |
| `timestamp` | string | ISO 8601 形式（秒精度） |
| `user_id` | integer | Discord ユーザー ID |
| `username` | string | Discord ユーザー名 |
| `loras` | array | 使用 LoRA 名のリスト |
| `positive` | string | ポジティブプロンプト |
| `negative` | string | ネガティブプロンプト |
| `image_orientation` | string \| null | 画像の向き（`"vertical"` / `"horizontal"` / `null`。省略時は null） |
| `outputs` | array | `WorkflowRunner.execute()` の戻り値（エラー時は空配列またはエラー前の出力） |
| `error` | string \| null | エラーメッセージ（成功時は null） |
