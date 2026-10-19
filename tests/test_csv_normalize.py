import datetime as dt
import unicodedata
import unittest

from helpers import temp_config, write

from hub.csvio import parse_num, read_table
from hub.normalize import ValidationError, build_snapshot, parse_export, rank_records
from hub.util import parse_date

VCP_CSV = """Ticker,DateNum,StateCode,State,Score,Strict,BaseDays,TCount,FinalTightPct,VDU,Pivot,DistPivotPct,RVol,RS63Pct,Stop,RiskPct,Val20
AAA,1261016,2,PRE-BREAKOUT,81.5,1,40,3,6.2,0.55,25.4,2.1,0.8,12.0,23.1,7.5,35.2
BBB,1261016,1,FORMING,64,0,30,2,9.8,0.9,15.0,8.4,1.1,5.0,13.9,7.0,{EMPTY}
CCC,1261015,3,BREAKOUT,70,1,28,3,5.0,0.6,40.0,-1.0,2.1,20.0,37.5,6.2,120
"""


class CsvTests(unittest.TestCase):
    def setUp(self):
        self.cfg, self.tmp = temp_config()

    def test_parse_num(self):
        self.assertEqual(parse_num("1,234.5"), 1234.5)
        self.assertEqual(parse_num("1,5"), 1.5)
        self.assertEqual(parse_num("1.234,5", decimal=","), 1234.5)
        self.assertIsNone(parse_num(""))
        self.assertIsNone(parse_num("-"))
        self.assertIsNone(parse_num("{EMPTY}"))
        self.assertIsNone(parse_num("-1e10"))  # Null noi bo cua AmiBroker
        self.assertEqual(parse_num("12%"), 12.0)
        self.assertEqual(parse_num("0"), 0.0)  # 0 that van la 0

    def test_dates(self):
        self.assertEqual(parse_date("1261016"), dt.date(2026, 10, 16))
        self.assertEqual(parse_date("20261016"), dt.date(2026, 10, 16))
        self.assertEqual(parse_date("16/10/2026"), dt.date(2026, 10, 16))
        self.assertEqual(parse_date("2026-10-16"), dt.date(2026, 10, 16))
        self.assertIsNone(parse_date("abc"))

    def test_encoding_and_semicolon_decimal_comma(self):
        # Windows-1258 luu dau tieng Viet dang to hop (NFD) -> doc ra phai chuan hoa ve NFC
        raw = "Ma;Ngành;Điểm\nFPT;Công nghệ;81,5\n"  # e^ + dau hoi/nang to hop
        p = write(self.tmp / "x.csv", raw, "cp1258")
        t = read_table(p)
        self.assertEqual(t.delimiter, ";")
        self.assertEqual(t.decimal, ",")
        self.assertEqual(t.header, ["Ma", "Ngành", unicodedata.normalize("NFC", "Điểm")])
        self.assertEqual(t.rows[0][1], "Công nghệ")
        self.assertEqual(parse_num(t.rows[0][2], t.decimal), 81.5)

    def test_utf8_bom_and_trailing_delimiter(self):
        p = write(self.tmp / "y.csv", "﻿Ticker,Score,\nAAA,1,\n")
        t = read_table(p)
        self.assertEqual(t.header, ["Ticker", "Score"])


class NormalizeTests(unittest.TestCase):
    def setUp(self):
        self.cfg, self.tmp = temp_config()
        self.vcp = self.cfg.strategy("VCP")

    def test_parse_range_and_metrics(self):
        p = write(self.tmp / "vcp.csv", VCP_CSV)
        pe = parse_export(self.vcp, p, session=dt.date(2026, 10, 16))
        self.assertEqual(sorted(pe.by_date), [dt.date(2026, 10, 15), dt.date(2026, 10, 16)])
        a = [r for r in pe.by_date[dt.date(2026, 10, 16)] if r["ticker"] == "AAA"][0]
        self.assertEqual(a["state"], "Pre-Breakout")  # nhan tu strategy_config, khong phai chuoi tho
        self.assertEqual(a["strategy_score"], 81.5)
        self.assertTrue(a["additional_metrics"]["strict"])
        b = [r for r in pe.by_date[dt.date(2026, 10, 16)] if r["ticker"] == "BBB"][0]
        self.assertIsNone(b["additional_metrics"].get("val20"))  # cot khong khai bao -> khong co
        # only_session: bo dong ngay khac
        pe2 = parse_export(self.vcp, p, session=dt.date(2026, 10, 16), only_session=True)
        self.assertEqual(list(pe2.by_date), [dt.date(2026, 10, 16)])

    def test_missing_column_is_error(self):
        p = write(self.tmp / "bad.csv", "Symbol,Close\nAAA,1\n")
        with self.assertRaises(ValidationError):
            parse_export(self.vcp, p, session=dt.date(2026, 10, 16))

    def test_future_date_is_error(self):
        p = write(self.tmp / "fut.csv", VCP_CSV)
        with self.assertRaises(ValidationError):
            parse_export(self.vcp, p, session=dt.date(2026, 10, 15))

    def test_pass_rule_and_no_date_column(self):
        rs = self.cfg.strategy("RS")
        p = write(self.tmp / "rs.csv", "Ma,Nganh,Diem,RS Rating,Tin hieu\nAAA,X,80,92,Manh\nBBB,X,70,79,Yeu\nCCC,X,60,,-\n")
        with self.assertRaises(ValidationError):
            parse_export(rs, p, session=None)  # khong cot ngay -> bat buoc --session
        pe = parse_export(rs, p, session=dt.date(2026, 10, 16))
        self.assertEqual([r["ticker"] for r in pe.by_date[dt.date(2026, 10, 16)]], ["AAA"])  # RS Rating >= 80; thieu -> khong dat

    def test_duplicates_dropped(self):
        p = write(self.tmp / "dup.csv", "Ticker,DateNum,StateCode,State,Score\nAAA,1261016,1,F,50\nAAA,1261016,1,F,55\n")
        pe = parse_export(self.vcp, p, session=dt.date(2026, 10, 16))
        self.assertEqual(len(pe.by_date[dt.date(2026, 10, 16)]), 1)
        self.assertTrue(any("trung" in w for w in pe.warnings))

    def test_rank_ties_and_nulls(self):
        recs = rank_records([{"ticker": "B", "strategy_score": 80}, {"ticker": "A", "strategy_score": 80},
                             {"ticker": "C", "strategy_score": None}, {"ticker": "D", "strategy_score": 90}])
        self.assertEqual([(r["ticker"], r["strategy_rank"]) for r in recs], [("D", 1), ("A", 2), ("B", 2), ("C", None)])

    def test_snapshot_deterministic(self):
        p = write(self.tmp / "vcp.csv", VCP_CSV)
        pe = parse_export(self.vcp, p, session=dt.date(2026, 10, 16))
        recs = pe.by_date[dt.date(2026, 10, 16)]
        a = build_snapshot(self.vcp, dt.date(2026, 10, 16), recs, None, origin="manual", source_file=str(p), source_sha256="x", generated_at="t1")
        b = build_snapshot(self.vcp, dt.date(2026, 10, 16), list(reversed(recs)), None, origin="manual", source_file=str(p), source_sha256="x", generated_at="t2")
        self.assertEqual(a["meta"]["content_hash"], b["meta"]["content_hash"])
        self.assertEqual(a["records"], b["records"])
        self.assertIsNone(a["records"][0]["avg_trading_value_20"])  # khong co du lieu gia -> null, khong phai 0


if __name__ == "__main__":
    unittest.main()
