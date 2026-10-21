import datetime as dt
import json
import unittest

from helpers import synthetic_market, temp_config

from hub.derive import build_site, compute_statuses
from hub.normalize import build_snapshot
from hub.store import EmptySuspicious, save_snapshot
from hub.util import read_json


def snap(cfg, sid, day, tickers, origin="live", scores=None):
    s = cfg.strategy(sid)
    recs = [{"ticker": t, "state_code": None, "state": None, "strategy_score": (scores or {}).get(t, 50.0), "additional_metrics": {}} for t in tickers]
    return build_snapshot(s, day, recs, None, origin=origin, source_file="x.csv", source_sha256=None, generated_at="2026-01-01T00:00:00+07:00")


D = [dt.date(2026, 10, d) for d in (12, 13, 14, 15, 16)]


class StoreTests(unittest.TestCase):
    def setUp(self):
        self.cfg, _ = temp_config()

    def test_create_unchanged_replace(self):
        self.assertEqual(save_snapshot(self.cfg, snap(self.cfg, "VCP", D[0], ["AAA"])), "created")
        self.assertEqual(save_snapshot(self.cfg, snap(self.cfg, "VCP", D[0], ["AAA"])), "unchanged")  # chong trung
        self.assertEqual(save_snapshot(self.cfg, snap(self.cfg, "VCP", D[0], ["AAA", "BBB"])), "replaced")
        bak = list((self.cfg.archive_dir / "replaced").glob("*.json"))
        self.assertEqual(len(bak), 1)  # ban cu duoc luu lai de kiem tra
        m = read_json(self.cfg.data_dir / "snapshots" / D[0].isoformat() / "VCP.json")["meta"]
        self.assertEqual(m["revision"], 2)

    def test_empty_guard(self):
        save_snapshot(self.cfg, snap(self.cfg, "VCP", D[0], ["A%02d" % i for i in range(10)]))
        with self.assertRaises(EmptySuspicious):
            save_snapshot(self.cfg, snap(self.cfg, "VCP", D[1], []))
        with self.assertRaises(EmptySuspicious):  # khong de rong ghi de du lieu hop le cung phien
            save_snapshot(self.cfg, snap(self.cfg, "VCP", D[0], []))
        self.assertEqual(save_snapshot(self.cfg, snap(self.cfg, "VCP", D[1], []), allow_empty=True), "created")

    def test_backfill_does_not_override_live(self):
        save_snapshot(self.cfg, snap(self.cfg, "VCP", D[0], ["AAA"], origin="live"))
        self.assertEqual(save_snapshot(self.cfg, snap(self.cfg, "VCP", D[0], ["BBB"], origin="backfill")), "unchanged")


class StatusTests(unittest.TestCase):
    def test_new_continuing_dropped_returning(self):
        cfg, _ = temp_config()
        seq = [["AAA", "BBB"], ["AAA", "CCC"], ["CCC"], ["AAA", "CCC"]]
        snaps = {"VCP": {D[i].isoformat(): snap(cfg, "VCP", D[i], t) for i, t in enumerate(seq)}}
        st = compute_statuses(snaps)["VCP"]
        s0, s1, s2, s3 = (st[D[i].isoformat()] for i in range(4))
        self.assertEqual(s0["records"]["AAA"]["signal_status"], "UNKNOWN")  # phien dau: khong co phien so sanh
        self.assertEqual(s1["records"]["AAA"]["signal_status"], "CONTINUING")
        self.assertEqual(s1["records"]["CCC"]["signal_status"], "NEW")
        self.assertEqual([d["ticker"] for d in s1["dropped"]], ["BBB"])
        self.assertEqual([d["ticker"] for d in s2["dropped"]], ["AAA"])
        self.assertEqual(s3["records"]["AAA"]["signal_status"], "RETURNING")
        self.assertEqual(s3["records"]["AAA"]["episode_start"], D[3].isoformat())
        self.assertEqual(s3["records"]["AAA"]["first_seen"], D[0].isoformat())
        self.assertEqual(s3["records"]["CCC"]["streak"], 3)
        self.assertEqual(s1["compared_to"], D[0].isoformat())

    def test_entry_price_and_return_since_entry(self):
        cfg, _ = temp_config()
        px = {D[0]: 10.0, D[1]: 11.0, D[2]: 12.0, D[3]: 9.0}
        snaps = {"VCP": {}}
        for i, tk in enumerate([["AAA"], ["AAA", "BBB"], ["BBB"], ["AAA"]]):
            s = snap(cfg, "VCP", D[i], tk)
            for r in s["records"]:
                r["close"] = px[D[i]]
            snaps["VCP"][D[i].isoformat()] = s
        bench = {D[0].isoformat(): 100.0, D[1].isoformat(): 101.0, D[2].isoformat(): 102.0, D[3].isoformat(): 99.0}
        st = compute_statuses(snaps, bench=bench)["VCP"]
        b2 = st[D[2].isoformat()]["records"]["BBB"]      # BBB vao D1 gia 11 -> D2 gia 12
        self.assertEqual(b2["entry_price"], 11.0)
        self.assertAlmostEqual(b2["ret_since_entry"], 9.09, places=2)
        self.assertAlmostEqual(b2["vni_since_entry"], 0.99, places=2)
        self.assertFalse(b2["entry_censored"])
        self.assertTrue(st[D[0].isoformat()]["records"]["AAA"]["entry_censored"])   # phien dau: chua biet ngay vao that
        a3 = st[D[3].isoformat()]["records"]["AAA"]      # AAA quay lai D3 -> gia vao moi = 9
        self.assertEqual(a3["entry_price"], 9.0)
        self.assertEqual(a3["ret_since_entry"], 0.0)
        drop = st[D[2].isoformat()]["dropped"][0]          # AAA roi o D2: vao D0 gia 10, phien cuoi D1 gia 11
        self.assertEqual((drop["ticker"], drop["entry_price"], drop["last_price"], drop["ret_pct"]), ("AAA", 10.0, 11.0, 10.0))

    def test_signal_identity_is_per_strategy(self):
        cfg, _ = temp_config()
        snaps = {"VCP": {D[0].isoformat(): snap(cfg, "VCP", D[0], ["AAA"]), D[1].isoformat(): snap(cfg, "VCP", D[1], ["AAA"])},
                 "RS": {D[1].isoformat(): snap(cfg, "RS", D[1], ["AAA"])}}
        st = compute_statuses(snaps)
        self.assertEqual(st["VCP"][D[1].isoformat()]["records"]["AAA"]["signal_status"], "CONTINUING")
        self.assertEqual(st["RS"][D[1].isoformat()]["records"]["AAA"]["signal_status"], "UNKNOWN")


class BuildTests(unittest.TestCase):
    def test_build_deterministic_and_multi(self):
        cfg, _ = temp_config()
        for i, (v, r) in enumerate([(["AAA", "BBB"], ["AAA"]), (["AAA"], ["AAA", "BBB"])]):
            save_snapshot(cfg, snap(cfg, "VCP", D[i], v))
            save_snapshot(cfg, snap(cfg, "RS", D[i], r))
        build_site(cfg, None, build_time="T")
        files = {p: p.read_text(encoding="utf-8") for p in cfg.data_dir.rglob("*.json")}
        info = build_site(cfg, None, build_time="T")
        self.assertEqual(info["files_changed"], 0)  # cung dau vao -> khong file nao doi
        self.assertEqual(files, {p: p.read_text(encoding="utf-8") for p in cfg.data_dir.rglob("*.json")})
        sess = json.loads((cfg.data_dir / "sessions" / f"{D[1].isoformat()}.json").read_text(encoding="utf-8"))
        a = [r for r in sess["records"] if r["ticker"] == "AAA"]
        self.assertEqual({r["n_strategies"] for r in a}, {2})
        self.assertEqual(a[0]["multi_streak"], 2)
        summ = read_json(cfg.data_dir / "latest" / "summary.json")["latest"]
        self.assertEqual(summ["multi2"], 1)  # chi AAA dat ca VCP va RS (BBB chi con RS)
        self.assertEqual(summ["dropped"], 1)  # BBB roi VCP
        meta = read_json(cfg.data_dir / "meta.json")
        self.assertEqual(meta["latest_session"], D[1].isoformat())
        self.assertFalse(meta["demo"])

    def test_forward_with_market(self):
        cfg, _ = temp_config()
        m, days = synthetic_market(80)
        save_snapshot(cfg, snap(cfg, "VCP", days[10], ["CCC"]))
        save_snapshot(cfg, snap(cfg, "VCP", days[11], ["AAA", "CCC"]))
        save_snapshot(cfg, snap(cfg, "VCP", days[-3], ["BBB"]))
        build_site(cfg, m, build_time="T")
        t = read_json(cfg.data_dir / "tickers" / "AAA.json")
        ep = t["episodes"][0]
        self.assertEqual(ep["status"], "NEW")
        f5 = ep["forward"]["5"]
        self.assertEqual(f5["entry_date"], days[12].isoformat())  # vao lenh phien KE TIEP
        self.assertAlmostEqual(f5["gross"], (1.01 ** 5 - 1) * 100, places=2)
        self.assertAlmostEqual(f5["net"], f5["gross"] - 0.6, places=2)
        bbb = read_json(cfg.data_dir / "tickers" / "BBB.json")
        self.assertIsNone(bbb["episodes"][0]["forward"]["5"])  # cua so chua du -> khong tinh

    def test_refuses_short_price_history(self):
        # Su co 19/10/2026: import\*.csv chi con ~20 phien -> khong duoc dung lai web voi lich su cut
        cfg, _ = temp_config()
        m, days = synthetic_market(30)
        m.MIN_SESSIONS = 250
        save_snapshot(cfg, snap(cfg, "VCP", days[-1], ["AAA"]))
        with self.assertRaises(ValueError):
            build_site(cfg, m, build_time="T")
        self.assertFalse((cfg.data_dir / "meta.json").exists())


if __name__ == "__main__":
    unittest.main()
