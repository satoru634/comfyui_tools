"""Discord ボット: ユーザーメッセージのパースロジックを提供するモジュール"""

import re

from modules.const import (
    VALID_ORIENTATIONS,
)

# ── メッセージパース ───────────────────────────────────────────────────────────


class MessageParser:
    # メンション除去用と行頭キーワード検出用の正規表現
    _MENTION = re.compile(r"<@!?\d+>")
    _KEYWORD = re.compile(
        r"^(workflow|loras|positive|negative|image_orientation)\s*:", re.IGNORECASE
    )

    def parse(self, text: str) -> dict:
        """メンションメッセージをパースして workflow / loras / positive / negative / image_orientation を返す。
        positive / negative が欠落している場合は ValueError を送出する。"""
        cleaned = self._MENTION.sub("", text)
        sections = self._collect_sections(cleaned)
        self._validate_required(sections)
        result = {
            "workflow": sections.get("workflow") or None,
            "loras": self._parse_loras(sections.get("loras", "")),
            "positive": sections["positive"],
            "negative": sections["negative"],
            "image_orientation": None,
        }
        if "image_orientation" in sections:
            orientation = sections["image_orientation"].lower()
            if orientation not in VALID_ORIENTATIONS:
                raise ValueError(
                    f"'image_orientation' は 'vertical'、'horizontal'、'square' で指定してください"
                    f"（指定値: {sections['image_orientation']!r}）"
                )
            result["image_orientation"] = orientation
        return result

    def _collect_sections(self, text: str) -> dict:
        """テキストを行ごとに走査し、キーワード行で区切られたセクションを収集する。
        キーワード行以外は直前のセクションの継続行として扱う。"""
        sections = {}
        current_key = None
        current_lines = []

        for raw_line in text.splitlines():
            line = raw_line.strip()
            m = self._KEYWORD.match(line)
            if m:
                # 新しいキーワードが始まる前に直前のセクションを確定する
                if current_key is not None:
                    sections[current_key] = "\n".join(current_lines).strip()
                current_key = m.group(1).lower()
                value_start = line[m.end() :].strip()
                current_lines = [value_start] if value_start else []
            elif current_key is not None:
                # キーワード行以外は継続行として追記する
                # プロンプト内の "face:1.3" 等の ":" はここで安全に処理される
                current_lines.append(line)

        # ループ終了後に最後のセクションを確定する
        if current_key is not None:
            sections[current_key] = "\n".join(current_lines).strip()

        return sections

    def _validate_required(self, sections: dict) -> None:
        """positive / negative が両方存在することを確認する。"""
        for key in ("positive", "negative"):
            if key not in sections:
                raise ValueError(f"'{key}' キーが見つかりません")

    def _parse_loras(self, loras_str: str) -> list:
        """カンマ区切りの LoRA 名文字列をリストに変換する。空文字列は空リストを返す。"""
        if not loras_str:
            return []
        return [name.strip() for name in loras_str.split(",") if name.strip()]
