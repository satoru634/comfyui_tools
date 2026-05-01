"""テスト用 sys.path 設定"""

import sys
from pathlib import Path

# generate_image_bot/ を追加: modules.* と generate_image_bot モジュールを解決する
sys.path.insert(0, str(Path(__file__).parent.parent))
# test/ を追加: test_helper を解決する
sys.path.insert(0, str(Path(__file__).parent))
