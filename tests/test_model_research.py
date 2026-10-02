import math
import unittest
from datetime import date
from jacare_analytics.model_research import calendar_features, recursive


class ModelResearchTest(unittest.TestCase):
    def test_calendar_mean_uses_only_same_weekday_history(self):
        values = [float(i) for i in range(28)]
        features = calendar_features(values, date(2026, 10, 2))
        self.assertAlmostEqual(features[-2], (21+14+7+0)/4)
        self.assertEqual(features[-1], 4)

    def test_missing_targets_not_invented(self):
        values = [math.nan]*28
        features = calendar_features(values, date(2026, 10, 2))
        self.assertTrue(math.isnan(features[-2]))
        self.assertEqual(features[-1], 0)
        self.assertTrue(all(math.isnan(x) for x in values))

    def test_recursion_uses_own_estimates_and_calendar(self):
        class Model:
            def predict(self, rows):
                return [rows[0][3]+1]
        calendar={'open_weekdays':[1,2,3,4,5,6]}
        original=[1.]*28
        first=date(2026, 10, 4)
        result=recursive(Model(), original, first, 3, calendar)
        self.assertEqual(result,[2.,0.,1.])
        self.assertEqual(original,[1.]*28)

if __name__=='__main__': unittest.main()
