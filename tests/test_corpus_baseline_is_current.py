"""baseline 檔必須是 measure_corpus() 此刻的輸出。

這條 guard 讓「語料變動了但沒有人重新產生 baseline」變成一個明確的紅燈，而不是讓其他
guard 各自以難懂的方式失敗。它同時也是 baseline 檔非手寫的保證：手改一個數字，這裡就紅。

CONDITIONAL：沒有語料時 skip（TW-075：本檔屬於 CI 不執行的那 19 條之一）。
"""
import pytest

from tests.corpus_measure import load_baseline, measure_corpus
from tests.mech_fixtures import CORPUS

pytestmark = pytest.mark.skipif(not CORPUS.is_dir(),
                                 reason="consumer corpus not present")


def test_baseline_matches_a_fresh_measurement():
    assert measure_corpus() == load_baseline(), (
        "語料已變動而 baseline 未更新。跑 `python -m tests.corpus_measure --write`，"
        "然後複查 diff —— 那份 diff 就是這次語料變動做了什麼。")
