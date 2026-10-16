"""Exercise ND2 axis decoding, per-channel exports and interactive layouts."""
import csv
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch
import numpy as np
import tifffile
from matplotlib.figure import Figure
from matplotlib.backends.backend_agg import FigureCanvasAgg
from analyze import run, read_nd2, mean
from gui import App

BASE=Path(__file__).parent

class ChannelTests(unittest.TestCase):
    def cfg(self):
        cfg=json.loads((BASE/'settings.json').read_text())
        cfg.update(background_diameter_um=6,response_diameter_um=10,sigma_px=0,
                   baseline_frames=[2,7],average_frames=[8,10],threshold_min=1)
        return cfg

    def data(self,c):
        a=np.ones((12,c,32,32),np.float32)*10
        for ch in range(c):
            a[:,ch,8:24,8:24]=100+10*ch
            a[7:,ch,8:24,8:24]+=20+ch
        return a

    def reader(self,c,omit_c=False):
        a=self.data(c)
        f=Mock(); f.sizes={'T':12,'C':c,'Y':32,'X':32}
        if omit_c:
            f.sizes.pop('C'); a=a[:,0]
        f.asarray.return_value=a
        f.voxel_size.return_value=SimpleNamespace(x=1,y=1)
        # voxel metadata is also converted to list by the reader.
        from collections import namedtuple
        f.voxel_size.return_value=namedtuple('Voxel','x y z')(1,1,1)
        f.metadata.channels=[SimpleNamespace(channel=SimpleNamespace(name=f'C{i+1}')) for i in range(c)]
        f.frame_metadata.side_effect=lambda i:SimpleNamespace(channels=[SimpleNamespace(time=SimpleNamespace(relativeTimeMs=i*1000))])
        return f

    def test_decode_one_to_four_and_missing_singleton_channel(self):
        for c,omit in [(1,True),(1,False),(2,False),(3,False),(4,False)]:
            with self.subTest(c=c,omit=omit), patch('analyze.nd2.ND2File') as reader:
                reader.return_value.__enter__.return_value=self.reader(c,omit)
                a,pixel,times,meta=read_nd2(BASE/'synthetic.nd2',self.cfg())
                self.assertEqual(a.shape,(12,c,32,32))
                np.testing.assert_array_equal(times,np.arange(12))

    def test_exports_and_layouts_for_all_counts(self):
        for c in range(1,5):
            with self.subTest(channels=c), tempfile.TemporaryDirectory(dir=BASE) as folder:
                cfg=self.cfg(); a=self.data(c)
                cfg['color_min']=[0]*c; cfg['color_max']=[.2+.1*i for i in range(c)]
                cfg['trace_colors']=cfg['trace_colors'][:c]
                with patch('analyze.read_nd2',return_value=(a,[1.,1.],np.arange(12),{})):
                    preview=run(BASE/'synthetic.nd2',cfg,Path(folder)/'preview',True)
                    out=run(BASE/'synthetic.nd2',cfg,Path(folder)/'export')
                self.assertEqual(preview['background_channel'],c)
                self.assertEqual(len(preview['centers']),c)
                with (out/'traces.csv').open(encoding='utf-8-sig') as f: rows=list(csv.DictReader(f))
                self.assertEqual(len(rows),12); self.assertEqual(len(rows[0]),2+2*c)
                self.assertEqual(len(list(out.glob('C*_dff_float32.tif'))),c)
                baseline=mean(tifffile.imread(out/'C1_dff_float32.tif')[1:7])
                np.testing.assert_allclose(baseline[np.isfinite(baseline)],0,atol=1e-6)
                app=App.__new__(App); app.data=preview; app.loaded_cfg=cfg
                app.fig=Figure(figsize=(10,8),layout='constrained'); app.canvas=FigureCanvasAgg(app.fig)
                app.draw(); app.canvas.draw()
                self.assertEqual(len(app.axes),c)
                self.assertEqual(len(app.trace_ax.lines),c+1)

    def test_background_selection_and_retained_channel_mismatch(self):
        cfg=self.cfg(); a=self.data(2); cfg['background_channel']=1
        with patch('analyze.read_nd2',return_value=(a,[1.,1.],None,{})):
            result=run(BASE/'synthetic.nd2',cfg,BASE/'unused',True)
            self.assertEqual(result['background_channel'],1)
            cfg['background_channel']=3
            with self.assertRaisesRegex(ValueError,'background_channel'):
                run(BASE/'synthetic.nd2',cfg,BASE/'unused',True)
            cfg['background_channel']=None
            cfg['required_roi_geometry']={'channel_count':3,'response_centers_xy':[[10,10]]*3}
            with self.assertRaisesRegex(ValueError,'identical channel counts'):
                run(BASE/'synthetic.nd2',cfg,BASE/'unused',True)

if __name__=='__main__': unittest.main()
