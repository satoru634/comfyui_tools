# generate_image_bot.py 仕様書 -その他-

## 開発ルール

- `discord_token` は `config.json` に記述し、ソースコードにハードコードしない。
- `config.json` は `.gitignore` に追加し、リポジトリに含めない。
- 新機能を追加する場合は `ImageBot` → `MessageParser` / `RateLimiter` → `WorkflowRunner` の依存方向を崩さない。
- 関数は 30 行以内を目安にする。
- メッセージテンプレートの展開は `str.format_map()` を使い、既知のキーのみを渡す辞書を与えること（`str.format()` は `{obj.__class__}` 等の属性アクセスを展開するため使用しない）。

## 依存ライブラリ

- `discord.py` — Discord API クライアント
- `run_workflow`（ローカル import）

## 実行

```bash
python generate_image_bot.py
python generate_image_bot.py --config /path/to/config.json
```

| オプション | 省略時 | 説明 |
|---|---|---|
| `-c` / `--config` | スクリプトと同じディレクトリの `config.json` | 設定ファイルのパス |

## 使用例

### 通常リクエスト

```
ユーザー: @bot
          workflow: anima
          loras: my_lora, another_lora
          positive: masterpiece, best quality, 1girl,
            (detailed face:1.3), solo
          negative: worst quality, bad quality, blurry
          image_orientation: vertical

ボット:   [⏳ リアクション付与]
          ...（生成中）...
          [画像ファイルを添付して返信]
          [⏳ リアクション削除、✅ リアクション付与]
```

### レート制限時

```
ユーザー: @bot
          positive: 1girl
          negative: worst quality

ボット:   [❌ リアクション付与]
          リクエストが連続しています。あと 18 秒待ってから再試行してください。
```

### スラッシュコマンド経由

```
ユーザー: /gen_image
          → GenImageModal が表示される

          [ワークフロー]                  anima
          [LoRAs]                        my_lora, another_lora
          [Positive]                     masterpiece, best quality, 1girl
          [Negative]                     worst quality, bad quality
          [画像の向き (vertical / horizontal / square)]  vertical

          → 送信ボタンを押す

ボット:   **workflow**: anima
          **loras**: my_lora, another_lora
          **positive**: masterpiece, best quality, 1girl
          **negative**: worst quality, bad quality
          **image_orientation**: vertical
          [⏳ リアクション付与]
          ...（生成中）...
          [画像ファイルを添付して返信]
          [⏳ リアクション削除、✅ リアクション付与]
```
