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
        "measure_corpus() 現在量出來的結果跟 tests/corpus-baseline.json 對不上。三種原因都會讓"
        "這裡紅，光看這條 assert 本身分不出是哪一種：\n"
        "  1) 語料變了（消費端改了 trips/ 底下的資料）\n"
        "  2) measure_corpus() 呼叫的 shipped code 變了（scripts/gate.py、scripts/rederive.py 等"
        "——同一份語料，量法變了，數字自然跟著變，不是語料的問題）\n"
        "  3) baseline 檔本身被手改過（沒有經過 --write 產生）\n"
        "分辨：`git diff --stat tests/corpus-baseline.json` 看 baseline 是否被直接編輯過"
        "（正常只會由 --write 整份重寫，手改通常只動一兩個數字、diff 形狀不齊）；"
        "再看這次改動有沒有觸及 `scripts/`（有 —— 多半是原因 2；沒有，且消費端語料真的動過 "
        "—— 是原因 1）。無論哪一種，都跑 `python -m tests.corpus_measure --write`，"
        "然後複查 diff —— 那份 diff 就是實際變動的內容，據此判斷是哪一種原因。")
