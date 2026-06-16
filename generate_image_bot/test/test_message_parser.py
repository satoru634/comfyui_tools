"""message_parser.py のユニットテスト"""

import pytest

from modules.message_parser import MessageParser

# ── MessageParser ─────────────────────────────────────────────────────────────


class TestMessageParser:
    def setup_method(self):
        self.parser = MessageParser()

    def test_basic_parse(self):
        text = "<@123456>\nloras: my_lora\npositive: 1girl\nnegative: bad quality"
        result = self.parser.parse(text)
        assert result["loras"] == ["my_lora"]
        assert result["positive"] == "1girl"
        assert result["negative"] == "bad quality"

    def test_no_loras_key(self):
        # loras: を省略した場合は空リストになる
        text = "<@123456>\npositive: 1girl\nnegative: bad quality"
        result = self.parser.parse(text)
        assert result["loras"] == []

    def test_multiple_loras(self):
        text = "<@123456>\nloras: lora1, lora2, lora3\npositive: 1girl\nnegative: bad"
        result = self.parser.parse(text)
        assert result["loras"] == ["lora1", "lora2", "lora3"]

    def test_loras_strips_spaces(self):
        text = "<@123456>\nloras:  lora1 ,  lora2  \npositive: 1girl\nnegative: bad"
        result = self.parser.parse(text)
        assert result["loras"] == ["lora1", "lora2"]

    def test_loras_colon_only_gives_empty_list(self):
        # loras: の後に値がない場合は空リスト
        text = "<@123456>\nloras:\npositive: 1girl\nnegative: bad"
        result = self.parser.parse(text)
        assert result["loras"] == []

    def test_multiline_positive(self):
        text = "<@123456>\npositive: 1girl,\n(detailed face:1.3), solo\nnegative: bad"
        result = self.parser.parse(text)
        assert "1girl" in result["positive"]
        assert "(detailed face:1.3), solo" in result["positive"]

    def test_multiline_negative(self):
        text = (
            "<@123456>\npositive: 1girl\nnegative: worst quality,\nbad quality,\nblurry"
        )
        result = self.parser.parse(text)
        assert "worst quality" in result["negative"]
        assert "blurry" in result["negative"]

    def test_colon_in_prompt_value(self):
        # 強調構文の : はキーワードと誤認識されない
        text = "<@123456>\npositive: (face:1.3), (eyes:1.2)\nnegative: bad"
        result = self.parser.parse(text)
        assert result["positive"] == "(face:1.3), (eyes:1.2)"

    def test_mention_not_in_result(self):
        # メンションが値に混入しない
        text = "<@123456> <@!789012>\npositive: 1girl\nnegative: bad"
        result = self.parser.parse(text)
        assert "<@" not in result["positive"]
        assert "<@" not in result["negative"]

    def test_mention_inline_with_keyword(self):
        # メンションと同じ行にキーワードがある場合でも正しくパースされる
        text = "<@123456> positive: 1girl\nnegative: bad"
        result = self.parser.parse(text)
        assert result["positive"] == "1girl"

    def test_text_before_first_keyword_ignored(self):
        # キーワード前のテキストは無視される
        text = "<@123456>\nplease generate this\npositive: 1girl\nnegative: bad"
        result = self.parser.parse(text)
        assert result["positive"] == "1girl"

    def test_keywords_case_insensitive(self):
        text = "<@123456>\nPositive: 1girl\nNEGATIVE: bad"
        result = self.parser.parse(text)
        assert result["positive"] == "1girl"
        assert result["negative"] == "bad"

    def test_missing_positive_raises(self):
        text = "<@123456>\nnegative: bad quality"
        with pytest.raises(ValueError, match="positive"):
            self.parser.parse(text)

    def test_missing_negative_raises(self):
        text = "<@123456>\npositive: 1girl"
        with pytest.raises(ValueError, match="negative"):
            self.parser.parse(text)

    def test_strips_leading_trailing_whitespace_from_values(self):
        text = "<@123456>\npositive:   1girl   \nnegative:   bad   "
        result = self.parser.parse(text)
        assert result["positive"] == "1girl"
        assert result["negative"] == "bad"

    def test_image_orientation_omitted_returns_none(self):
        text = "<@123456>\npositive: 1girl\nnegative: bad"
        result = self.parser.parse(text)
        assert result["image_orientation"] is None

    def test_image_orientation_vertical(self):
        text = "<@123456>\npositive: 1girl\nnegative: bad\nimage_orientation: vertical"
        result = self.parser.parse(text)
        assert result["image_orientation"] == "vertical"

    def test_image_orientation_horizontal(self):
        text = (
            "<@123456>\npositive: 1girl\nnegative: bad\nimage_orientation: horizontal"
        )
        result = self.parser.parse(text)
        assert result["image_orientation"] == "horizontal"

    def test_image_orientation_case_insensitive(self):
        text = "<@123456>\npositive: 1girl\nnegative: bad\nimage_orientation: Vertical"
        result = self.parser.parse(text)
        assert result["image_orientation"] == "vertical"

    def test_image_orientation_square(self):
        text = "<@123456>\npositive: 1girl\nnegative: bad\nimage_orientation: square"
        result = self.parser.parse(text)
        assert result["image_orientation"] == "square"

    def test_image_orientation_invalid_raises(self):
        text = "<@123456>\npositive: 1girl\nnegative: bad\nimage_orientation: diagonal"
        with pytest.raises(ValueError, match="vertical"):
            self.parser.parse(text)

    def test_workflow_omitted_returns_none(self):
        text = "<@123456>\npositive: 1girl\nnegative: bad"
        result = self.parser.parse(text)
        assert result["workflow"] is None

    def test_workflow_specified(self):
        text = "<@123456>\nworkflow: anima\npositive: 1girl\nnegative: bad"
        result = self.parser.parse(text)
        assert result["workflow"] == "anima"

    def test_workflow_case_preserved(self):
        text = "<@123456>\nworkflow: AnimaRapid\npositive: 1girl\nnegative: bad"
        result = self.parser.parse(text)
        assert result["workflow"] == "AnimaRapid"

    def test_workflow_empty_returns_none(self):
        text = "<@123456>\nworkflow:\npositive: 1girl\nnegative: bad"
        result = self.parser.parse(text)
        assert result["workflow"] is None
