"""画像ディレクトリを一括タグ付けして .txt キャプションファイルを生成するツール"""

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "run_workflow"))
from modules.wd14_tagger_runner import Wd14TaggerRunner

_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}
_REPORT_FILENAME = "tags_report.txt"


def _load_config(config_path: str) -> dict:
    try:
        with open(config_path, encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        raise ValueError(f"設定ファイルが見つかりません: {config_path}")
    except json.JSONDecodeError as e:
        raise ValueError(f"設定ファイルのフォーマットが不正です: {e}")


def _parse_tag_list(tag_str: str) -> list[str]:
    return [t.strip() for t in tag_str.split(",") if t.strip()]


def _collect_images(directory: Path, recursive: bool) -> list[Path]:
    files = directory.rglob("*") if recursive else directory.glob("*")
    return sorted(
        p for p in files if p.is_file() and p.suffix.lower() in _IMAGE_EXTENSIONS
    )


class CaptioningTool:
    """ディレクトリ内の画像を一括タグ付けしてキャプションファイルを生成するクラス。"""

    def __init__(
        self,
        config_path: str = "config.json",
        extra_prepend: list[str] | None = None,
        extra_exclude: list[str] | None = None,
    ):
        config = _load_config(config_path)
        self._runner = Wd14TaggerRunner(config_path)
        self._prepend_tags = config.get("prepend_tags", []) + (extra_prepend or [])
        self._exclude_tags = config.get("exclude_tags", []) + (extra_exclude or [])

    def process_directory(
        self, directory: Path, recursive: bool = False, overwrite: bool = False
    ) -> tuple[int, int, int]:
        """ディレクトリ内の画像を処理し、(処理数, スキップ数, エラー数) を返す。"""
        images = _collect_images(directory, recursive)
        processed, skipped, errors = 0, 0, 0
        total = len(images)
        for i, image_path in enumerate(images, 1):
            if image_path.with_suffix(".txt").exists() and not overwrite:
                print(f"[{i}/{total}] {image_path.name} → スキップ")
                skipped += 1
                continue
            if self._process_image(image_path):
                print(f"[{i}/{total}] {image_path.name} → OK")
                processed += 1
            else:
                print(f"[{i}/{total}] {image_path.name} → エラー", file=sys.stderr)
                errors += 1
        print(f"完了: 処理 {processed}, スキップ {skipped}, エラー {errors}")
        return processed, skipped, errors

    def generate_report(self, directory: Path, recursive: bool = False) -> None:
        """ディレクトリ内の全 .txt を集計して tags_report.txt を出力する。"""
        tag_counts = self._collect_all_tags(directory, recursive)
        sorted_tags = sorted(tag_counts.items(), key=lambda x: (-x[1], x[0]))
        report_path = directory / _REPORT_FILENAME
        with open(report_path, "w", encoding="utf-8") as f:
            for tag, count in sorted_tags:
                f.write(f"{tag}: {count}\n")
        print(f"レポートを保存しました: {report_path}")

    def _process_image(self, image_path: Path) -> bool:
        """タグ取得 → フィルタ → .txt 書き込み。成功で True を返す。"""
        try:
            image_data = image_path.read_bytes()
            tags = self._runner.tag(image_data, image_path.name)
            filtered = self._apply_tag_filters(tags)
            image_path.with_suffix(".txt").write_text(filtered, encoding="utf-8")
            return True
        except (OSError, ValueError) as e:
            print(f"エラー ({image_path.name}): {e}", file=sys.stderr)
            return False

    def _apply_tag_filters(self, tags: str) -> str:
        """exclude 除去 → prepend 重複除去 → prepend 挿入の順でタグを処理する。"""
        exclude_lower = {t.lower() for t in self._exclude_tags}
        prepend_lower = {t.lower() for t in self._prepend_tags}
        tag_list = [t.strip() for t in tags.split(",") if t.strip()]
        tag_list = [t for t in tag_list if t.lower() not in exclude_lower]
        tag_list = [t for t in tag_list if t.lower() not in prepend_lower]
        return ", ".join(self._prepend_tags + tag_list)

    def _collect_all_tags(self, directory: Path, recursive: bool) -> dict[str, int]:
        """全 .txt からタグを収集し、{タグ名: 出現回数} を返す。tags_report.txt は除外する。"""
        txt_files = directory.rglob("*.txt") if recursive else directory.glob("*.txt")
        counter: Counter = Counter()
        for txt_path in txt_files:
            if txt_path.name == _REPORT_FILENAME or not txt_path.is_file():
                continue
            try:
                for tag in txt_path.read_text(encoding="utf-8").split(","):
                    tag = tag.strip()
                    if tag:
                        counter[tag] += 1
            except OSError:
                pass
        return dict(counter)


def main():
    parser = argparse.ArgumentParser(
        description="画像ディレクトリを一括タグ付けするツール"
    )
    parser.add_argument("directory", help="処理対象ディレクトリのパス")
    parser.add_argument(
        "-r",
        "--recursive",
        action="store_true",
        help="サブディレクトリも再帰的に処理する",
    )
    parser.add_argument(
        "--overwrite", action="store_true", help="既存の .txt ファイルを上書きする"
    )
    parser.add_argument("-p", "--prepend", help="冒頭に追記するタグ（カンマ区切り）")
    parser.add_argument("-e", "--exclude", help="除外するタグ（カンマ区切り）")
    parser.add_argument(
        "--report", action="store_true", help="処理完了後にタグ集計レポートを生成する"
    )
    parser.add_argument(
        "-c",
        "--config",
        default="config.json",
        help="設定ファイルのパス（省略時: config.json）",
    )
    args = parser.parse_args()

    directory = Path(args.directory)
    if not directory.is_dir():
        print(f"エラー: ディレクトリが存在しません: {directory}", file=sys.stderr)
        sys.exit(1)

    extra_prepend = _parse_tag_list(args.prepend) if args.prepend else []
    extra_exclude = _parse_tag_list(args.exclude) if args.exclude else []

    try:
        tool = CaptioningTool(args.config, extra_prepend, extra_exclude)
    except (OSError, ValueError) as e:
        print(f"エラー: {e}", file=sys.stderr)
        sys.exit(1)

    tool.process_directory(directory, args.recursive, args.overwrite)

    if args.report:
        try:
            tool.generate_report(directory, args.recursive)
        except OSError as e:
            print(f"エラー: レポートの書き込みに失敗しました: {e}", file=sys.stderr)
            sys.exit(1)


if __name__ == "__main__":
    main()
