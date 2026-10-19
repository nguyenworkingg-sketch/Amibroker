import datetime as dt
import subprocess
import sys
import unittest
from unittest import mock

from helpers import ROOT, synthetic_market, temp_config, write

from hub import pipeline
from hub.market import frames_from_records
from hub.util import VN_TZ, read_json


class MarketTests(unittest.TestCase):
    def test_no_lookahead(self):
        m, days = synthetic_market(100)
        d = days[70]
        e1 = m.enrich("AAA", d)
        # them du lieu tuong lai bat thuong -> gia tri tai d khong doi
        recs = []
        for t in ("AAA", "BBB", "CCC", "VNINDEX"):
            for i, x in enumerate(days):
                c = float(m.bench_close.iloc[i]) if t == "VNINDEX" else float(m.close[t].iloc[i])
                o = float(m.bench_open.iloc[i]) if t == "VNINDEX" else float(m.open[t].iloc[i])
                if x > d:
                    c, o = c * 3, o * 3
                recs.append({"ticker": t, "date": x.isoformat(), "open": o, "close": c, "volume": 1e6, "exchange": "HOSE"})
        m2 = frames_from_records(recs)
        self.assertEqual(e1, m2.enrich("AAA", d))

    def test_trading_session_returns(self):
        m, days = synthetic_market(60)
        e = m.enrich("AAA", days[40])
        self.assertAlmostEqual(e["ret_5d"], (1.01 ** 5 - 1) * 100, places=6)
        self.assertAlmostEqual(e["avg_trading_value_20"], sum(20 * 1.01 ** (i + 1) for i in range(21, 41)) * 1e6 / 1e6 / 20, places=3)
        self.assertIsNone(m.enrich("AAA", days[5])["avg_trading_value_20"])  # chua du 20 phien -> null
        self.assertEqual(m.prev_session(days[10]), days[9])
        self.assertEqual(m.session_gap(days[3], days[8]), 5)

    def test_breadth(self):
        m, days = synthetic_market(230)
        b = m.breadth([days[-1]])[0]["ALL"]
        self.assertEqual(b["n"], 3)
        self.assertAlmostEqual(b["above_ma20"], 100 / 3, places=1)  # chi AAA tang -> tren MA20


class PipelineTests(unittest.TestCase):
    def setUp(self):
        self.cfg, self.tmp = temp_config()

    def test_lock_prevents_concurrent_runs(self):
        with pipeline.run_lock(self.cfg):
            with self.assertRaises(pipeline.Busy):
                with pipeline.run_lock(self.cfg):
                    pass
        with pipeline.run_lock(self.cfg):  # khoa duoc giai phong
            pass

    def test_intraday_session_refused(self):
        m, days = synthetic_market(30)
        fake_now = dt.datetime.combine(days[-1], dt.time(11, 0), VN_TZ)
        with mock.patch.object(pipeline, "now_vn", return_value=fake_now):
            with self.assertRaises(pipeline.HubError):
                pipeline.expected_session(self.cfg, m)
        late = dt.datetime.combine(days[-1], dt.time(16, 0), VN_TZ)
        with mock.patch.object(pipeline, "now_vn", return_value=late):
            self.assertEqual(pipeline.expected_session(self.cfg, m), days[-1])

    def test_invalid_file_keeps_previous_data(self):
        m, days = synthetic_market(30)
        s = self.cfg.strategy("VCP")
        good = write(self.tmp / "g.csv", "Ticker,DateNum,StateCode,State,Score\nAAA,%d,2,x,80\n" % (int(days[-1].strftime("%Y%m%d")) - 19000000))
        rr = pipeline.RunRecorder(self.cfg, "manual")
        self.assertEqual(pipeline.ingest_file(self.cfg, s, good, m, days[-1], origin="manual", rr=rr), 1)
        bad = write(self.tmp / "b.csv", "Symbol,Foo\nAAA,1\n")
        self.assertEqual(pipeline.ingest_file(self.cfg, s, bad, m, days[-1], origin="manual", rr=rr), 0)
        snap = read_json(self.cfg.data_dir / "snapshots" / days[-1].isoformat() / "VCP.json")
        self.assertEqual(snap["records"][0]["ticker"], "AAA")  # du lieu hop le van con
        self.assertEqual(rr.rec["steps"][-1]["status"], "invalid")
        rr.finish("partial", "test")
        st = read_json(self.cfg.data_dir / "status.json")
        self.assertEqual(st["strategies"]["VCP"]["last_status"], "invalid")
        self.assertEqual(st["strategies"]["VCP"]["last_success_session"], days[-1].isoformat())

    def test_manual_import_cli(self):
        sample = ROOT / "exporter" / "samples" / "demo_vcp_explore.csv"
        p = subprocess.run([sys.executable, "-I", str(ROOT / "exporter" / "import_csv.py"), "--strategy", "VCP", "--file", str(sample),
                            "--range", "--session", "2026-10-16", "--no-market", "--origin", "demo", "--data-dir", str(self.cfg.data_dir)],
                           capture_output=True, text=True, encoding="utf-8", errors="replace",
                           env={"HUB_ARCHIVE_DIR": str(self.cfg.archive_dir), "SYSTEMROOT": "C:\\Windows"})
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        meta = read_json(self.cfg.data_dir / "meta.json")
        self.assertTrue(meta["demo"])
        self.assertEqual(meta["latest_session"], "2026-10-16")
        self.assertGreaterEqual(len(meta["sessions"]), 2)


if __name__ == "__main__":
    unittest.main()
