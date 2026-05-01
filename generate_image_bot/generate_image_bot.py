"""Discord ボット: ComfyUI 画像生成 エントリポイント"""

import argparse
import time
from pathlib import Path

import aiohttp

from modules.const import RECONNECT_WAIT
from modules.load_config import load_config
from modules.image_bot import ImageBot


def main():
    """コマンドライン引数を解析して設定を読み込み、ボットを起動する。
    Discord ゲートウェイへの WebSocket ハンドシェイクが失敗した場合は待機後に再起動する。"""
    parser = argparse.ArgumentParser(description="ComfyUI Discord ボット")
    parser.add_argument(
        "-c",
        "--config",
        default=str(Path(__file__).parent / "config.json"),
        help="設定ファイルのパス（省略時: config.json）",
    )
    args = parser.parse_args()
    config = load_config(args.config)
    while True:
        try:
            ImageBot(config).run(config["discord_token"])
            break  # shutdown_watcher による正常終了
        except aiohttp.WSServerHandshakeError as e:
            # Discord ゲートウェイが HTTP 520 等を返した場合は待機後に再接続する
            print(
                f"WebSocket ハンドシェイクエラー ({e}), "
                f"{RECONNECT_WAIT}秒後に再接続します..."
            )
            time.sleep(RECONNECT_WAIT)


if __name__ == "__main__":
    main()
