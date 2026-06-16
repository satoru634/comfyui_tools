# generate_image_bot.py 仕様書 -入力インターフェース-

## 入力インターフェース

### メンションメッセージ

#### トリガー

ボットへのメンションを含むメッセージ。

#### 入力フォーマット

キーワード形式を採用する。

```
@bot
workflow: anima
loras: lora1, lora2
positive: masterpiece, best quality, 1girl,
  (detailed face:1.3), solo
negative: worst quality, bad quality,
  blurry
image_orientation: vertical
```

- `workflow:` 行は省略可能（省略時は `run_workflow/config.json` の `default_workflow` を使用）
- `loras:` 行は省略可能（省略時は LoRA なしで実行）
- `positive:` / `negative:` は必須
- `image_orientation:` 行は省略可能（省略時は `run_workflow/config.json` の `default_image_size` を使用）
- `image_orientation:` の値は `vertical`（縦）・`horizontal`（横）・`square`（正方形）のみ受け付ける
- 各キーワードは **行頭** に置く（`キーワード:` の形式）
- プロンプトは複数行にわたって記述できる（次のキーワード行が来るまで継続）

#### パース規則

1. メッセージ本文からメンション部分（`<@...>`）を除去する
2. 残りのテキストを行単位に分割する
3. 行が `workflow:` / `loras:` / `positive:` / `negative:` / `image_orientation:` のいずれかで始まる場合、そのキーワードの値収集を開始する
4. それ以外の行は、直前のキーワードの値に改行付きで追記する（継続行）
5. 収集した各値は前後の空白・改行をトリム（`strip()`）する

**`:` の扱い**

キーワードの判定は行頭のパターンのみで行う。
値の中に `:` が含まれていても（例: `(detailed face:1.3)`）継続行として扱われるため、強調構文は問題なく使用できる。

```
# 正しく動作する例
positive: masterpiece, (detailed face:1.3), (eyes:1.2)
```

#### 入力バリデーション

`run_workflow.py` の `_validate_loras` / `_validate_prompts` がバリデーションを担うため、
ボット側は以下のみを担当する。

| 検証内容 | ボット側 |
|---|---|
| フォーマットのパース失敗（必須キーの欠落等） | ボット側で検出しエラーメッセージ返信 |
| `image_orientation` の値が `vertical` / `horizontal` / `square` 以外 | ボット側で検出しエラーメッセージ返信 |
| `workflow` の値が `run_workflow/config.json` の `workflows` に存在しない | `WorkflowRunner` が `ValueError` を送出、ボット側でキャッチして Discord にエラーメッセージ返信 |
| LoRA 名・プロンプトの内容検証 | `WorkflowRunner.execute()` に委譲 |

---

### スラッシュコマンド（`/gen_image`）

#### トリガー

テキストチャンネルで `/gen_image` を入力する。

DM からのコマンドは無視する（リアクション・返信なし）。

#### モーダル

コマンド実行時に `GenImageModal` が表示される。フィールドは以下の通り。

| フィールド名 | ラベル | 入力スタイル | 必須 |
|---|---|---|---|
| `workflow` | ワークフロー | 1行テキスト | 省略可 |
| `loras` | LoRAs | 1行テキスト | 省略可 |
| `positive` | Positive | 複数行テキスト | 必須 |
| `negative` | Negative | 複数行テキスト | 必須 |
| `image_orientation` | 画像の向き (vertical / horizontal / square) | 1行テキスト | 省略可 |

#### モーダル送信後の動作

1. `image_orientation` の値が `vertical` / `horizontal` / `square` 以外の場合は ephemeral エラーメッセージを返信し、処理を中断する（❌ リアクションは付与しない）
2. 入力値から太字形式のメッセージを生成してチャンネルに送信する（`workflow` / `loras` / `image_orientation` が空の場合は対応する `**...**:` 行を省略）
3. 送信されたメッセージを起点として、レート制限チェック以降の生成フローを実行する

**送信メッセージの例（全フィールドあり）**

```
**workflow**: anima
**loras**: my_lora, another_lora
**positive**: masterpiece, best quality, 1girl
**negative**: worst quality, bad quality
**image_orientation**: vertical
```

**送信メッセージの例（workflow なし、loras なし、image_orientation なし）**

```
**positive**: masterpiece, best quality, 1girl
**negative**: worst quality, bad quality
```

#### 入力バリデーション

モーダル経由では `MessageParser` を経由せず入力値を直接 `parsed` に組み立てるため、パースエラーは発生しない。
`image_orientation` の値チェック（`vertical` / `horizontal` / `square` 以外は弾く）はボット側で行う。
`workflow` の存在チェックは `WorkflowRunner` コンストラクタに委譲する（`ValueError` 時はボット側でキャッチして Discord にエラーメッセージを返信）。
LoRA 名・プロンプトの内容検証は `WorkflowRunner.execute()` に委譲する（メンションメッセージと同様）。
