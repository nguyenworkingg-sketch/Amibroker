import unittest

from helpers import temp_config

from hub import notify


class FakeTg:
    def __init__(self):
        self.sent = []
        self.flags = {"eod": True, "intraday": True}
        self.configured = True

    def send(self, text):
        self.sent.append(text)
        return True


DOC = {"available": True, "session": "2026-10-19",
       "rule": {"enter": 90, "exit": 80, "min_value_bil": 2.0, "short_sessions": 20},
       "summary": {"in_top": 2, "universe": 200, "pct_positive": 50.0, "median_ret_pct": 1.2},
       "rows": [{"ticker": "AAA", "sector": "Ngân hàng", "sm_mid": 91, "sm_short": None, "price": 12.5, "new_today": True},
                {"ticker": "BBB", "sector": None, "sm_mid": 85, "sm_short": 70, "price": 5.0, "new_today": False}],
       "recent_exits": [{"ticker": "CCC", "exit_date": "2026-10-19", "exit_reason": "illiquid", "sessions": 12, "ret_pct": -3.0, "vni_ret_pct": 1.0},
                        {"ticker": "DDD", "exit_date": "2026-10-10", "exit_reason": "rs", "sessions": 5, "ret_pct": 2.0, "vni_ret_pct": 0.5}]}


class NotifyTests(unittest.TestCase):
    def setUp(self):
        self.cfg, _ = temp_config()

    def test_eod_once_per_session(self):
        tg = FakeTg()
        text = notify.eod_toprs(self.cfg, DOC, tg)
        self.assertIn("AAA", text)
        self.assertIn("CCC", text)          # roi top hom nay
        self.assertNotIn("DDD", text)       # roi top phien truoc -> khong bao lai
        self.assertNotIn("BBB", text)       # khong phai moi vao
        self.assertLess(len(text), 600)          # tin gon: chi ma vao / ma ra
        self.assertNotIn(" < ", text)          # "<" tran phai escape, Telegram HTML tu choi
        self.assertIsNone(notify.eod_toprs(self.cfg, DOC, tg))   # chay lai cung phien -> khong gui trung
        self.assertEqual(len(tg.sent), 1)

    def test_intraday_dedup_per_ticker(self):
        tg = FakeTg()
        e = [{"ticker": "AAA", "sector": None, "sm_mid": 92.0, "sm_short": None, "price": 1.0, "exit": 80}]
        x = [{"ticker": "BBB", "sector": None, "sm_mid": 78.0, "sm_short": 60.0, "price": 2.0, "exit": 80}]
        self.assertIsNotNone(notify.intraday_alerts(self.cfg, e, x, "10:00", tg))
        self.assertIsNone(notify.intraday_alerts(self.cfg, e, x, "10:15", tg))      # da bao trong ngay
        e2 = e + [{"ticker": "EEE", "sector": None, "sm_mid": 95.0, "sm_short": 90.0, "price": 3.0, "exit": 80}]
        text = notify.intraday_alerts(self.cfg, e2, x, "10:30", tg)
        self.assertIn("EEE", text)
        self.assertNotIn("AAA", text)
        self.assertNotIn("(< ", text)
        self.assertEqual(len(tg.sent), 2)


if __name__ == "__main__":
    unittest.main()
