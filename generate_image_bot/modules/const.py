"""Discord ボット: 定数定義"""

# config.json の reactions / messages で必須となるキー一覧
REACTION_KEYS = ("processing", "success", "error")
MESSAGE_KEYS = (
    "rate_limit",
    "generating",
    "parse_error",
    "execution_error",
    "file_too_large",
    "unexpected_error",
    "dm_not_supported",
    "shutdown_in_progress",
)

# 10MB: Discord の添付ファイル上限に合わせた閾値
MAX_FILE_SIZE = 10 * 1024 * 1024

# Discord ボット経由でユーザー入力を受け取るため、巨大文字列によるメモリ枯渇を防ぐ上限
MAX_PROMPT_LENGTH = 3000

# 画像の向き指定の有効な値
VALID_ORIENTATIONS = ("vertical", "horizontal")

# WSServerHandshakeError 発生時の再接続待機秒数
RECONNECT_WAIT = 30
