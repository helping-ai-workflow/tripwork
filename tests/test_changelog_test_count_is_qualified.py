"""CHANGELOG 最新條目的測試數字必須說明它是在哪個環境量的。

TW-075：v0.34.0 公布 `Tests: 1047 → 1082, zero skipped or xfailed.`，但那 1082 是掛上
消費端語料（corpus）才量得到的數字——corpus-backed guard 全部 `skipif`-ed on the corpus
directory existing，而 CI 只 checkout 這個 repo 本身，corpus 目錄不存在。所以 CI 實際跑出
來的是較低的 passed 數 + 一批 skip，「zero skipped」跟已公布的 corpus 數字在同一個環境下
不可能同時成立。那句話描述的是作者工作站，不是 CI（真正 gate merge 的環境）。

只檢查最新條目：歷史條目（v0.33.0 / v0.32.0）是當時的紀錄，改了會失去 changelog 的時序
意義；新規則從 v0.35.0 起適用。
"""
import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parent.parent
COUNT_LINE = re.compile(r"^Tests:.*\d+.*$", re.M)


def _newest_entry():
    text = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    heads = [m.start() for m in re.finditer(r"^##\s*\d+\.\d+\.\d+", text, re.M)]
    assert heads, "CHANGELOG has no `## X.Y.Z` heading"
    end = heads[1] if len(heads) > 1 else len(text)
    return text[heads[0]:end]


def test_the_newest_changelog_entry_qualifies_its_test_count():
    entry = _newest_entry()
    lines = COUNT_LINE.findall(entry)
    assert lines, "最新條目沒有 `Tests:` 行"
    for line in lines:
        assert "CI" in line or "corpus" in line, (
            f"測試數字必須說明量測環境（CI 或 corpus）: {line!r}")


def test_readme_pytest_line_qualifies_its_test_count():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    m = re.search(r"^pytest\s+#\s*(.+)$", readme, re.M)
    assert m, "README 的 pytest 指令行不見了"
    assert "CI" in m.group(1) or "corpus" in m.group(1), m.group(1)
