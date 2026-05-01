"""generate_image_bot.py のユニットテスト"""

import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock

from modules.gen_image_modal import GenImageModal

from test_helper import (
    valid_config,
    make_bot_for_test,
)

# ── GenImageModal ─────────────────────────────────────────────────────────────


class TestGenImageModal:
    def _make_test_modal(
        self,
        tmp_path,
        loras_val: str = "",
        positive_val: str = "1girl",
        negative_val: str = "bad quality",
        orientation_val: str = "",
    ):
        """discord.ui.Modal.__init__ を回避し、TextInput を MagicMock で差し替えたモーダルを返す。"""
        bot = make_bot_for_test(valid_config(), MagicMock(), tmp_path)
        modal = object.__new__(GenImageModal)
        modal._bot = bot
        modal.loras = MagicMock(value=loras_val)
        modal.positive = MagicMock(value=positive_val)
        modal.negative = MagicMock(value=negative_val)
        modal.image_orientation = MagicMock(value=orientation_val)
        return modal, bot

    def _make_interaction(self, user_id: int = 99999, username: str = "testuser"):
        interaction = MagicMock()
        interaction.user = MagicMock(id=user_id)
        interaction.user.name = (
            username  # MagicMock の name 引数はモック名に使われるため別途設定する
        )
        interaction.response.send_message = AsyncMock()
        mock_message = MagicMock()
        mock_message.add_reaction = AsyncMock()
        mock_message.remove_reaction = AsyncMock()
        mock_message.reply = AsyncMock()
        mock_message.channel = MagicMock()
        mock_message.channel.send = AsyncMock()
        interaction.original_response = AsyncMock(return_value=mock_message)
        return interaction, mock_message

    def test_build_parsed_with_loras(self, tmp_path):
        modal, _ = self._make_test_modal(tmp_path, loras_val="lora1, lora2")
        parsed = modal._build_parsed()
        assert parsed["loras"] == ["lora1", "lora2"]
        assert parsed["positive"] == "1girl"
        assert parsed["negative"] == "bad quality"
        assert parsed["image_orientation"] is None

    def test_build_parsed_no_loras_returns_empty_list(self, tmp_path):
        modal, _ = self._make_test_modal(tmp_path, loras_val="")
        parsed = modal._build_parsed()
        assert parsed["loras"] == []

    def test_build_parsed_loras_strips_whitespace(self, tmp_path):
        modal, _ = self._make_test_modal(tmp_path, loras_val="  lora1 ,  lora2  ")
        parsed = modal._build_parsed()
        assert parsed["loras"] == ["lora1", "lora2"]

    def test_build_parsed_loras_ignores_empty_items(self, tmp_path):
        modal, _ = self._make_test_modal(tmp_path, loras_val=" , , ")
        parsed = modal._build_parsed()
        assert parsed["loras"] == []

    def test_build_parsed_orientation_vertical(self, tmp_path):
        modal, _ = self._make_test_modal(tmp_path, orientation_val="vertical")
        parsed = modal._build_parsed()
        assert parsed["image_orientation"] == "vertical"

    def test_build_parsed_orientation_horizontal(self, tmp_path):
        modal, _ = self._make_test_modal(tmp_path, orientation_val="horizontal")
        parsed = modal._build_parsed()
        assert parsed["image_orientation"] == "horizontal"

    def test_build_parsed_orientation_case_insensitive(self, tmp_path):
        modal, _ = self._make_test_modal(tmp_path, orientation_val="Vertical")
        parsed = modal._build_parsed()
        assert parsed["image_orientation"] == "vertical"

    def test_build_parsed_orientation_empty_returns_none(self, tmp_path):
        modal, _ = self._make_test_modal(tmp_path, orientation_val="")
        parsed = modal._build_parsed()
        assert parsed["image_orientation"] is None

    def test_build_parsed_orientation_invalid_raises(self, tmp_path):
        modal, _ = self._make_test_modal(tmp_path, orientation_val="diagonal")
        with pytest.raises(ValueError, match="vertical.*horizontal"):
            modal._build_parsed()

    def test_build_message_text_with_loras(self, tmp_path):
        modal, _ = self._make_test_modal(tmp_path)
        parsed = {
            "loras": ["lora1", "lora2"],
            "positive": "1girl",
            "negative": "bad",
            "image_orientation": None,
        }
        text = modal._build_message_text(parsed)
        assert text == "**loras**: lora1, lora2\n**positive**: 1girl\n**negative**: bad"

    def test_build_message_text_without_loras(self, tmp_path):
        modal, _ = self._make_test_modal(tmp_path)
        parsed = {
            "loras": [],
            "positive": "1girl",
            "negative": "bad",
            "image_orientation": None,
        }
        text = modal._build_message_text(parsed)
        assert "**loras**" not in text
        assert text == "**positive**: 1girl\n**negative**: bad"

    def test_build_message_text_with_orientation(self, tmp_path):
        modal, _ = self._make_test_modal(tmp_path)
        parsed = {
            "loras": [],
            "positive": "1girl",
            "negative": "bad",
            "image_orientation": "vertical",
        }
        text = modal._build_message_text(parsed)
        assert "**image_orientation**: vertical" in text

    def test_build_message_text_without_orientation_omits_line(self, tmp_path):
        modal, _ = self._make_test_modal(tmp_path)
        parsed = {
            "loras": [],
            "positive": "1girl",
            "negative": "bad",
            "image_orientation": None,
        }
        text = modal._build_message_text(parsed)
        assert "**image_orientation**" not in text

    def test_on_submit_sends_keyword_format_message(self, tmp_path):
        modal, bot = self._make_test_modal(
            tmp_path, loras_val="my_lora", positive_val="1girl", negative_val="bad"
        )
        interaction, _ = self._make_interaction()
        bot.process_generation = AsyncMock()
        asyncio.run(modal.on_submit(interaction))
        sent = interaction.response.send_message.call_args.args[0]
        assert "**loras**: my_lora" in sent
        assert "**positive**: 1girl" in sent
        assert "**negative**: bad" in sent

    def test_on_submit_no_loras_omits_loras_line(self, tmp_path):
        modal, bot = self._make_test_modal(tmp_path, loras_val="")
        interaction, _ = self._make_interaction()
        bot.process_generation = AsyncMock()
        asyncio.run(modal.on_submit(interaction))
        sent = interaction.response.send_message.call_args.args[0]
        assert "**loras**" not in sent

    def test_on_submit_calls_process_generation_with_parsed(self, tmp_path):
        modal, bot = self._make_test_modal(
            tmp_path,
            loras_val="lora1",
            positive_val="masterpiece",
            negative_val="worst",
        )
        interaction, mock_message = self._make_interaction()
        mock_process = AsyncMock()
        bot.process_generation = mock_process
        asyncio.run(modal.on_submit(interaction))
        mock_process.assert_called_once()
        msg_arg, parsed_arg, user_arg = mock_process.call_args.args
        assert msg_arg is mock_message
        assert parsed_arg["loras"] == ["lora1"]
        assert parsed_arg["positive"] == "masterpiece"
        assert parsed_arg["negative"] == "worst"
        assert parsed_arg["image_orientation"] is None

    def test_on_submit_passes_interaction_user(self, tmp_path):
        modal, bot = self._make_test_modal(tmp_path)
        interaction, _ = self._make_interaction(user_id=12345, username="modaluser")
        mock_process = AsyncMock()
        bot.process_generation = mock_process
        asyncio.run(modal.on_submit(interaction))
        _, _, user_arg = mock_process.call_args.args
        assert user_arg.id == 12345
        assert user_arg.name == "modaluser"

    def test_on_submit_invalid_orientation_sends_ephemeral_error(self, tmp_path):
        modal, bot = self._make_test_modal(tmp_path, orientation_val="diagonal")
        interaction, _ = self._make_interaction()
        bot.process_generation = AsyncMock()
        asyncio.run(modal.on_submit(interaction))
        interaction.response.send_message.assert_called_once()
        call_kwargs = interaction.response.send_message.call_args.kwargs
        assert call_kwargs.get("ephemeral") is True
        bot.process_generation.assert_not_called()
