import json
import unittest
import tempfile
from pathlib import Path
from unittest.mock import patch
import numpy as np
from PIL import Image
from analyze import resolve_range, display_cmap, rgb, run, PALETTES
import test_channels

BASE=Path(__file__).parent

class TimeDisplayTests(unittest.TestCase):
    def test_seconds_use_real_timestamps_and_include_endpoints(self):
        cfg={'baseline_unit':'seconds','baseline_seconds':[1.2,4.1]}
        times=np.array([0,1.2,2.6,4.1,5.8])
        result=resolve_range(cfg,'baseline',5,times)
        self.assertEqual((result.start,result.stop),(1,4))
        cfg['baseline_seconds']=[1.3,2.5]
        with self.assertRaisesRegex(ValueError,'no frame'): resolve_range(cfg,'baseline',5,times)
        with self.assertRaisesRegex(ValueError,'timestamps'): resolve_range(cfg,'baseline',5,None)
        cfg['baseline_seconds']=[0,6]
        with self.assertRaises(ValueError): resolve_range(cfg,'baseline',5,times)

    def test_all_palettes_reverse_and_swapped_endpoints(self):
        values=np.array([[0,.1,.2,.3,np.nan]])
        for palette in PALETTES:
            with self.subTest(palette=palette):
                cfg={'colormap':palette,'color_min':0,'color_max':.3}
                forward=rgb(values,cfg)
                reverse=rgb(values,{**cfg,'reverse_colormap':True})
                swapped=rgb(values,{**cfg,'color_min':.3,'color_max':0})
                np.testing.assert_array_equal(reverse,swapped)
                np.testing.assert_array_equal(forward[0,0],reverse[0,3])
                self.assertTrue((reverse[0,-1]==0).all())
                both=rgb(values,{**cfg,'color_min':.3,'color_max':0,'reverse_colormap':True})
                np.testing.assert_array_equal(both,forward)

    def test_seconds_export_and_display_do_not_change_quantitation(self):
        helper=test_channels.ChannelTests(); cfg=helper.cfg(); a=helper.data(1); times=np.arange(12,dtype=float)
        cfg.update(baseline_unit='seconds',baseline_seconds=[1,6],average_unit='seconds',average_seconds=[7,9])
        with patch('analyze.read_nd2',return_value=(a,[1.,1.],times,{})):
            preview=run(BASE/'synthetic.nd2',cfg,BASE/'unused',True)
            cfg.update(colormap=['GreenFireBlue'],reverse_colormap=[True],color_min=[-.3],color_max=[.3])
            other=run(BASE/'synthetic.nd2',cfg,BASE/'unused',True)
            np.testing.assert_array_equal(preview['dff'],other['dff'])
            self.assertEqual(other['resolved_ranges']['baseline_frames'],[2,7])
            with tempfile.TemporaryDirectory(dir=BASE) as folder:
                out=run(BASE/'synthetic.nd2',cfg,Path(folder)/'export')
                report=json.loads((out/'analysis.json').read_text())
                self.assertEqual(report['resolved_ranges']['average_frames'],[8,10])
                bmp=np.asarray(Image.open(out/'C1_average_GreenFireBlue.bmp'))
                np.testing.assert_array_equal(bmp,rgb(other['displays'][0],cfg))

if __name__=='__main__': unittest.main()
