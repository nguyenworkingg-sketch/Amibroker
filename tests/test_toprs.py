import datetime as dt
import unittest

import numpy as np
import pandas as pd

from helpers import weekdays

from hub.market import MarketData
from hub.toprs import compute, rating_frame


def market_from(closes: dict[str, list[float]], bench: list[float], value: float = 100.0) -> MarketData:
    days = pd.DatetimeIndex(weekdays(dt.date(2026, 1, 5), len(bench)))
    c = pd.DataFrame(closes, index=days)
    v = (value * 1e6 / c)  # GTGD moi phien = value ty dong
    b = pd.Series(bench, index=days)
    m = MarketData(c, c, v, b, b, {t: "HOSE" for t in closes})
    m.MIN_SESSIONS = 0
    return m


class TopRsTests(unittest.TestCase):
    def test_rating_formula_matches_afl(self):
        # 4 ma, 1 cap bang nhau: hang = (so nho hon + (so bang + 1)/2) / n * 98 + 1
        v = pd.DataFrame([[1.0, 2.0, 2.0, 3.0]], columns=list("ABCD"))
        r = rating_frame(v, v.notna()).iloc[0]
        exp = [round((0 + 1) / 4 * 98 + 1), round((1 + 1.5) / 4 * 98 + 1), round((1 + 1.5) / 4 * 98 + 1), round((3 + 1) / 4 * 98 + 1)]
        self.assertEqual(list(r), exp)
        self.assertEqual(r["D"], 99)

    def test_hysteresis_enter_90_exit_80(self):
        # 20 ma "nen" tang deu de xep hang; ma X: manh -> hoi nhe (van >= 80) -> yeu han (< 80)
        n = 330
        base = {f"B{i:02d}": list(100 * np.cumprod(np.full(n, 1 + 0.0002 * i))) for i in range(20)}
        x = [100.0] * 255 + list(100 * np.cumprod(np.full(30, 1.02)))           # bung manh -> vao top
        x += [x[-1]] * 20                                                     # di ngang -> ty le giam dan
        x += list(x[-1] * np.cumprod(np.full(n - len(x), 0.97)))              # giam manh -> roi top
        m = market_from({**base, "X": x}, [100.0] * n)
        res = compute(m, enter=90, exit_=80, min_value=2.0, warmup=252)
        mid = res["mid"]["X"]
        eps = [e for e in res["closed"] + res["open"] if e["ticker"] == "X"]
        self.assertEqual(len(eps), 1)
        ep = eps[0]
        self.assertGreaterEqual(mid.iloc[ep["entry_i"]], 90)
        self.assertLess(mid.iloc[ep["entry_i"] - 1], 90)
        self.assertIn("exit_i", ep)
        self.assertLess(mid.iloc[ep["exit_i"]], 80)
        # trong khoang dang o top, co phien < 90 nhung >= 80 ma KHONG bi roi top (vung dem)
        held = mid.iloc[ep["entry_i"]:ep["exit_i"]]
        self.assertTrue(((held < 90) & (held >= 80)).any())
        self.assertTrue((held >= 80).all())

    def test_illiquid_not_ranked(self):
        n = 300
        cl = {f"B{i}": list(100 * np.cumprod(np.full(n, 1 + 0.001 * i))) for i in range(10)}
        m = market_from(cl, [100.0] * n, value=1.0)   # GTGD 1 ty < nguong 2 ty
        res = compute(m, min_value=2.0, warmup=252)
        self.assertTrue(res["mid"].iloc[-1].isna().all())
        self.assertEqual(res["open"], [])


    def test_exit_after_long_unranked(self):
        # X vao top roi mat thanh khoan (khong giao dich) > 10 phien -> roi top, ly do illiquid
        n = 300
        base = {f"B{i:02d}": list(100 * np.cumprod(np.full(n, 1 + 0.0002 * i))) for i in range(20)}
        x = [100.0] * 255 + list(100 * np.cumprod(np.full(30, 1.04))) + [np.nan] * (n - 285)
        m = market_from({**base, "X": x}, [100.0] * n)
        res = compute(m, warmup=252)
        ep = [e for e in res["closed"] if e["ticker"] == "X"]
        self.assertEqual(len(ep), 1)
        self.assertEqual(ep[0]["exit_reason"], "illiquid")
        self.assertEqual(ep[0]["exit_i"] - ep[0]["last_ranked"], 11)


if __name__ == "__main__":
    unittest.main()
