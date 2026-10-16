import unittest
import numpy as np
from analyze import disk, find_roi, roi_mask, smooth_display, mean


class NumericalTests(unittest.TestCase):
    def test_search_matches_exhaustive_physical_disk(self):
        rng = np.random.default_rng(17)
        a = rng.normal(size=(25, 30))
        a[10:13, 15:18] = np.nan
        kernel = disk(3.2, [0.8, 1.2])
        ry, rx = np.array(kernel.shape)//2
        scores = []
        for y in range(ry, a.shape[0]-ry):
            for x in range(rx, a.shape[1]-rx):
                values = a[roi_mask(a.shape, kernel, [x,y])]
                if np.isfinite(values).sum() >= np.ceil(kernel.sum()*.8):
                    scores.append((np.nanmean(values), [x,y]))
        for maximize in (False, True):
            expected = (max if maximize else min)(scores, key=lambda p:p[0])[1]
            self.assertEqual(find_roi(a,kernel,maximize,.8), expected)

    def test_constant_signal_and_nan_smoothing(self):
        a = np.ones((4,15,15), np.float32)*.25
        a[:,7,7] = np.nan
        out = smooth_display(a,1)
        self.assertTrue(np.isnan(out[:,7,7]).all())
        np.testing.assert_allclose(out[np.isfinite(out)],.25,atol=1e-6)
        self.assertTrue(np.isnan(mean(np.array([np.nan,np.nan]))))

    def test_edge_and_empty_search_fail(self):
        k = disk(4,[1,1])
        with self.assertRaises(ValueError):
            roi_mask((20,20),k,[0,0])
        with self.assertRaises(ValueError):
            find_roi(np.full((20,20),np.nan),k)


if __name__ == '__main__':
    unittest.main()
