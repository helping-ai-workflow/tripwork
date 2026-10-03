# 教育部《國語小字典》— Taiwan Mandarin readings

tripwork reads the 注音 readings in this dictionary to check whether a day title
really rhymes (same rhyme group and same tone, Taiwan readings). The files here are
the Ministry's release, **unmodified**; tripwork only reads them
(`scripts/zhuyin.py`, standard library only).

- 姓名標示：中華民國教育部（Ministry of Education, R.O.C.）。《國語小字典》（版本編號：2019_20260929）網址：http://dict.mini.moe.edu.tw/
- 授權：創用 CC－姓名標示－禁止改作 臺灣 3.0 版（CC BY-ND 3.0 TW），
  http://creativecommons.org/licenses/by-nd/3.0/tw/legalcode
- 使用說明：`minidict_10312.pdf`（教育部「公眾授權使用說明」，依其要求完整保留）
- 來源：https://language.moe.gov.tw/001/Upload/Files/site_content/M0001/respub/dict_mini_download.html
- 版本編號：2019_20260929（2019 年版，教育部 2026-09-29 發布）
- 下載日期：2026-10-01

| file | sha256 |
|---|---|
| dict_mini_2019_20260929.xlsx | 94546b7d330a6334b828c1a8a516dd2378f9e0dfcf6ea1d301516fe5680c6edd |
| minidict_10312.pdf | 535c2dd49b1adf9528c515fe0bb20dd61f235686056cf825eb8330aeb6da4667 |

`tests/test_zhuyin.py` recomputes both hashes, so an edited file fails the suite.

## Updating

Download the new 文字資料庫 zip from the page above, put its xlsx here unchanged
(delete the old one), keep the current 使用說明 PDF, and update the version, date and
hashes in this file and `XLSX` in `scripts/zhuyin.py`.
