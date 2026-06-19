"""テスト用 sys.path 設定"""

import sys
from pathlib import Path

# run_workflow/ を追加: modules.* を解決する
sys.path.insert(0, str(Path(__file__).parent.parent))
# test/ を追加: test_helper を解決する
sys.path.insert(0, str(Path(__file__).parent))
# comfyui_tools/ を追加: common_libs.* を解決する
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
