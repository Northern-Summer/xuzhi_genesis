# conftest.py — pytest 统一路径配置（pytest 自动先加载此文件）
import sys
import os

# conftest.py 位于 harness/tests/
#   dirname(__file__)             = harness/tests/
#   dirname( dirname(__file__) )  = harness/
#   dirname( dirname( dirname(__file__) ) ) = engineering/  ← 正确
_HARNESS_PARENT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _HARNESS_PARENT not in sys.path:
    sys.path.insert(0, _HARNESS_PARENT)
