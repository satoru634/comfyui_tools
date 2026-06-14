"""CaptioningTool のユニットテスト"""

import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from captioning_tool import (
    CaptioningTool,
    _collect_images,
    _parse_tag_list,
    _REPORT_FILENAME,
)


# ── ヘルパー ──────────────────────────────────────────────────────────────────


def _make_config(tmp_path, prepend=None, exclude=None) -> str:
    config = {
        "comfyui_url": "http://127.0.0.1:8188",
        "wd14_tagger": {
            "model_name": "wd-eva02-large-tagger-v3",
            "general_threshold": 0.35,
            "character_threshold": 0.85,
        },
        "prepend_tags": prepend or [],
        "exclude_tags": exclude or [],
    }
    config_file = tmp_path / "config.json"
    config_file.write_text(json.dumps(config), encoding="utf-8")
    return str(config_file)


def _make_tool(config_path, extra_prepend=None, extra_exclude=None) -> CaptioningTool:
    with patch("captioning_tool.Wd14TaggerRunner"):
        tool = CaptioningTool(config_path, extra_prepend, extra_exclude)
    tool._runner = MagicMock()
    return tool


# ── _parse_tag_list ───────────────────────────────────────────────────────────


class TestParseTagList:
    def test_basic(self):
        assert _parse_tag_list("1girl, solo, long hair") == [
            "1girl",
            "solo",
            "long hair",
        ]

    def test_strips_whitespace(self):
        assert _parse_tag_list("  1girl  ,  solo  ") == ["1girl", "solo"]

    def test_empty_string(self):
        assert _parse_tag_list("") == []

    def test_single_tag(self):
        assert _parse_tag_list("1girl") == ["1girl"]


# ── _collect_images ───────────────────────────────────────────────────────────


class TestCollectImages:
    def test_collects_supported_extensions(self, tmp_path):
        for name in ["a.jpg", "b.jpeg", "c.png", "d.webp"]:
            (tmp_path / name).touch()
        (tmp_path / "e.txt").touch()
        names = {p.name for p in _collect_images(tmp_path, recursive=False)}
        assert names == {"a.jpg", "b.jpeg", "c.png", "d.webp"}

    def test_ignores_unsupported_extension(self, tmp_path):
        (tmp_path / "a.bmp").touch()
        assert _collect_images(tmp_path, recursive=False) == []

    def test_non_recursive_excludes_subdirectory(self, tmp_path):
        sub = tmp_path / "sub"
        sub.mkdir()
        (tmp_path / "a.jpg").touch()
        (sub / "b.jpg").touch()
        result = _collect_images(tmp_path, recursive=False)
        assert len(result) == 1 and result[0].name == "a.jpg"

    def test_recursive_includes_subdirectory(self, tmp_path):
        sub = tmp_path / "sub"
        sub.mkdir()
        (tmp_path / "a.jpg").touch()
        (sub / "b.jpg").touch()
        names = {p.name for p in _collect_images(tmp_path, recursive=True)}
        assert names == {"a.jpg", "b.jpg"}

    def test_returns_sorted_paths(self, tmp_path):
        for name in ["c.jpg", "a.jpg", "b.jpg"]:
            (tmp_path / name).touch()
        result = _collect_images(tmp_path, recursive=False)
        assert [p.name for p in result] == ["a.jpg", "b.jpg", "c.jpg"]


# ── _apply_tag_filters ────────────────────────────────────────────────────────


class TestApplyTagFilters:
    def test_exclude_removes_tags(self, tmp_path):
        tool = _make_tool(_make_config(tmp_path, exclude=["rating:general"]))
        assert tool._apply_tag_filters("1girl, solo, rating:general") == "1girl, solo"

    def test_exclude_is_case_insensitive(self, tmp_path):
        tool = _make_tool(_make_config(tmp_path, exclude=["rating:general"]))
        assert tool._apply_tag_filters("1girl, Rating:General") == "1girl"

    def test_prepend_inserts_at_front(self, tmp_path):
        tool = _make_tool(_make_config(tmp_path, prepend=["my_chara"]))
        assert tool._apply_tag_filters("1girl, solo") == "my_chara, 1girl, solo"

    def test_prepend_removes_duplicate_from_wd14(self, tmp_path):
        tool = _make_tool(_make_config(tmp_path, prepend=["1girl"]))
        assert (
            tool._apply_tag_filters("1girl, solo, long hair")
            == "1girl, solo, long hair"
        )

    def test_prepend_duplicate_is_case_insensitive(self, tmp_path):
        tool = _make_tool(_make_config(tmp_path, prepend=["1Girl"]))
        assert tool._apply_tag_filters("1girl, solo") == "1Girl, solo"

    def test_exclude_before_prepend_dedup(self, tmp_path):
        tool = _make_tool(
            _make_config(
                tmp_path, prepend=["my_chara", "1girl"], exclude=["rating:general"]
            )
        )
        result = tool._apply_tag_filters("1girl, solo, long hair, rating:general")
        assert result == "my_chara, 1girl, solo, long hair"

    def test_extra_prepend_and_exclude(self, tmp_path):
        tool = _make_tool(
            _make_config(tmp_path), extra_prepend=["trigger"], extra_exclude=["bad_tag"]
        )
        assert (
            tool._apply_tag_filters("solo, bad_tag, long hair")
            == "trigger, solo, long hair"
        )

    def test_config_prepend_before_extra_prepend(self, tmp_path):
        tool = _make_tool(
            _make_config(tmp_path, prepend=["config_tag"]), extra_prepend=["cli_tag"]
        )
        assert tool._apply_tag_filters("solo") == "config_tag, cli_tag, solo"

    def test_empty_tags_returns_empty(self, tmp_path):
        tool = _make_tool(_make_config(tmp_path))
        assert tool._apply_tag_filters("") == ""


# ── _process_image ────────────────────────────────────────────────────────────


class TestProcessImage:
    def test_success_writes_txt(self, tmp_path):
        tool = _make_tool(_make_config(tmp_path))
        img = tmp_path / "photo.jpg"
        img.write_bytes(b"fake_image")
        tool._runner.tag.return_value = "1girl, solo"

        assert tool._process_image(img) is True
        assert (tmp_path / "photo.txt").read_text(encoding="utf-8") == "1girl, solo"

    def test_tag_error_returns_false(self, tmp_path):
        tool = _make_tool(_make_config(tmp_path))
        img = tmp_path / "photo.jpg"
        img.write_bytes(b"fake_image")
        tool._runner.tag.side_effect = ValueError("ComfyUI エラー")

        assert tool._process_image(img) is False

    def test_missing_image_returns_false(self, tmp_path):
        tool = _make_tool(_make_config(tmp_path))
        assert tool._process_image(tmp_path / "missing.jpg") is False


# ── process_directory ─────────────────────────────────────────────────────────


class TestProcessDirectory:
    def test_counts_processed_skipped_errors(self, tmp_path):
        tool = _make_tool(_make_config(tmp_path))
        (tmp_path / "a_err.jpg").write_bytes(b"img")
        img_ok = tmp_path / "b_ok.jpg"
        img_ok.write_bytes(b"img")
        (tmp_path / "c_skip.jpg").write_bytes(b"img")
        (tmp_path / "c_skip.txt").write_text("existing", encoding="utf-8")
        tool._runner.tag.side_effect = [ValueError("エラー"), "1girl, solo"]

        processed, skipped, errors = tool.process_directory(tmp_path)

        assert (processed, skipped, errors) == (1, 1, 1)

    def test_overwrite_processes_existing_txt(self, tmp_path):
        tool = _make_tool(_make_config(tmp_path))
        (tmp_path / "photo.jpg").write_bytes(b"img")
        (tmp_path / "photo.txt").write_text("old", encoding="utf-8")
        tool._runner.tag.return_value = "new_tag"

        processed, skipped, _ = tool.process_directory(tmp_path, overwrite=True)

        assert processed == 1 and skipped == 0
        assert (tmp_path / "photo.txt").read_text(encoding="utf-8") == "new_tag"

    def test_recursive_processes_subdirectory(self, tmp_path):
        tool = _make_tool(_make_config(tmp_path))
        sub = tmp_path / "sub"
        sub.mkdir()
        (tmp_path / "a.jpg").write_bytes(b"img")
        (sub / "b.jpg").write_bytes(b"img")
        tool._runner.tag.return_value = "1girl"

        processed, _, _ = tool.process_directory(tmp_path, recursive=True)

        assert processed == 2

    def test_non_recursive_ignores_subdirectory(self, tmp_path):
        tool = _make_tool(_make_config(tmp_path))
        sub = tmp_path / "sub"
        sub.mkdir()
        (tmp_path / "a.jpg").write_bytes(b"img")
        (sub / "b.jpg").write_bytes(b"img")
        tool._runner.tag.return_value = "1girl"

        processed, _, _ = tool.process_directory(tmp_path, recursive=False)

        assert processed == 1


# ── _collect_all_tags ─────────────────────────────────────────────────────────


class TestCollectAllTags:
    def test_aggregates_tags_across_files(self, tmp_path):
        tool = _make_tool(_make_config(tmp_path))
        (tmp_path / "a.txt").write_text("1girl, solo, long hair", encoding="utf-8")
        (tmp_path / "b.txt").write_text("1girl, blue eyes", encoding="utf-8")

        result = tool._collect_all_tags(tmp_path, recursive=False)

        assert result == {"1girl": 2, "solo": 1, "long hair": 1, "blue eyes": 1}

    def test_excludes_report_file(self, tmp_path):
        tool = _make_tool(_make_config(tmp_path))
        (tmp_path / "a.txt").write_text("1girl", encoding="utf-8")
        (tmp_path / _REPORT_FILENAME).write_text("1girl: 1", encoding="utf-8")

        result = tool._collect_all_tags(tmp_path, recursive=False)

        assert result == {"1girl": 1}

    def test_recursive_includes_subdirectory(self, tmp_path):
        tool = _make_tool(_make_config(tmp_path))
        sub = tmp_path / "sub"
        sub.mkdir()
        (tmp_path / "a.txt").write_text("1girl", encoding="utf-8")
        (sub / "b.txt").write_text("1girl", encoding="utf-8")

        result = tool._collect_all_tags(tmp_path, recursive=True)

        assert result["1girl"] == 2

    def test_non_recursive_excludes_subdirectory(self, tmp_path):
        tool = _make_tool(_make_config(tmp_path))
        sub = tmp_path / "sub"
        sub.mkdir()
        (tmp_path / "a.txt").write_text("1girl", encoding="utf-8")
        (sub / "b.txt").write_text("solo", encoding="utf-8")

        result = tool._collect_all_tags(tmp_path, recursive=False)

        assert "1girl" in result and "solo" not in result


# ── generate_report ───────────────────────────────────────────────────────────


class TestGenerateReport:
    def test_writes_sorted_report(self, tmp_path):
        tool = _make_tool(_make_config(tmp_path))
        (tmp_path / "a.txt").write_text("1girl, solo", encoding="utf-8")
        (tmp_path / "b.txt").write_text("1girl, long hair", encoding="utf-8")

        tool.generate_report(tmp_path)

        lines = (
            (tmp_path / _REPORT_FILENAME)
            .read_text(encoding="utf-8")
            .strip()
            .splitlines()
        )
        assert lines[0] == "1girl: 2"
        assert set(lines[1:]) == {"solo: 1", "long hair: 1"}

    def test_same_count_sorted_alphabetically(self, tmp_path):
        tool = _make_tool(_make_config(tmp_path))
        (tmp_path / "a.txt").write_text("zebra, apple", encoding="utf-8")

        tool.generate_report(tmp_path)

        lines = (
            (tmp_path / _REPORT_FILENAME)
            .read_text(encoding="utf-8")
            .strip()
            .splitlines()
        )
        assert lines == ["apple: 1", "zebra: 1"]

    def test_report_file_not_counted_on_rerun(self, tmp_path):
        tool = _make_tool(_make_config(tmp_path))
        (tmp_path / "a.txt").write_text("1girl", encoding="utf-8")
        tool.generate_report(tmp_path)
        tool.generate_report(tmp_path)

        report = (tmp_path / _REPORT_FILENAME).read_text(encoding="utf-8")
        assert report == "1girl: 1\n"
