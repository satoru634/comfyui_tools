"""Discord ボット: 画像生成コマンドのモーダル"""

from typing import TYPE_CHECKING

import discord

from modules.const import (
    MAX_PROMPT_LENGTH,
    VALID_ORIENTATIONS,
)

if TYPE_CHECKING:
    import modules.image_bot


# ── スラッシュコマンド モーダル ────────────────────────────────────────────────


class GenImageModal(discord.ui.Modal, title="画像生成"):
    # モーダルの入力項目を定義
    loras = discord.ui.TextInput(
        label="LoRAs",
        required=False,
        placeholder="lora1, lora2",
        max_length=400,
    )
    positive = discord.ui.TextInput(
        label="Positive",
        style=discord.TextStyle.paragraph,
        required=True,
        placeholder="masterpiece, best quality, 1girl",
        max_length=MAX_PROMPT_LENGTH,
    )
    negative = discord.ui.TextInput(
        label="Negative",
        style=discord.TextStyle.paragraph,
        required=True,
        placeholder="worst quality, bad quality",
        max_length=MAX_PROMPT_LENGTH,
    )
    image_orientation = discord.ui.TextInput(
        label="画像の向き (vertical / horizontal)",
        required=False,
        placeholder="vertical",
        max_length=10,
    )

    def __init__(self, bot: "modules.image_bot.ImageBot"):
        super().__init__()
        self._bot = bot

    async def on_submit(self, interaction: discord.Interaction):
        """ユーザーがモーダルを送信したときの処理。入力値をパースして生成処理に渡す。"""
        try:
            parsed = self._build_parsed()
        except ValueError as e:
            await interaction.response.send_message(str(e), ephemeral=True)
            return
        await interaction.response.send_message(self._build_message_text(parsed))
        message = await interaction.original_response()
        await self._bot.process_generation(message, parsed, interaction.user)

    def _build_parsed(self) -> dict:
        """モーダルの入力値をパースして辞書にまとめる。LoRA 名のリスト化や画像の向きの検証を行う。"""
        loras_str = self.loras.value.strip()
        orientation_raw = self.image_orientation.value.strip()
        orientation = orientation_raw.lower() if orientation_raw else None
        if orientation is not None and orientation not in VALID_ORIENTATIONS:
            raise ValueError(
                f"'image_orientation' は 'vertical' または 'horizontal' で指定してください"
                f"（指定値: {orientation_raw!r}）"
            )
        return {
            "loras": [n.strip() for n in loras_str.split(",") if n.strip()],
            "positive": self.positive.value.strip(),
            "negative": self.negative.value.strip(),
            "image_orientation": orientation,
        }

    def _build_message_text(self, parsed: dict) -> str:
        """生成処理開始前にユーザーに送信するメッセージを構築する。入力内容をわかりやすく整形して返す。"""
        lines = []
        if parsed["loras"]:
            lines.append(f"**loras**: {', '.join(parsed['loras'])}")
        lines.append(f"**positive**: {parsed['positive']}")
        lines.append(f"**negative**: {parsed['negative']}")
        if parsed.get("image_orientation"):
            lines.append(f"**image_orientation**: {parsed['image_orientation']}")
        return "\n".join(lines)
