import unittest
import json
import csv
import os
import tempfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock
import numpy as np
import tifffile
from matplotlib.figure import Figure
from matplotlib.backends.backend_agg import FigureCanvasAgg
from analyze import run, color_range, rgb, mean, roi_mask
from gui import App

BASE=Path(__file__).parent
SOURCE=Path(os.environ.get('AXR_TEST_ND2','__optional_example_not_supplied__.nd2'))

class InteractiveTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not SOURCE.is_file(): raise unittest.SkipTest('Set AXR_TEST_ND2 to run optional four-channel real-file tests')
        cls.folder=tempfile.TemporaryDirectory(dir=BASE)
        cls.out=Path(cls.folder.name)/'export'
        cls.cfg=json.loads((BASE/'settings.json').read_text())
        cls.preview=run(SOURCE,cls.cfg,BASE/'preview_unused',preview_only=True)
        run(SOURCE,cls.cfg,cls.out)

    @classmethod
    def tearDownClass(cls):
        cls.folder.cleanup()

    def app(self):
        app=App.__new__(App)
        app.data=dict(self.preview)
        app.data['centers']=[p.copy() for p in self.preview['centers']]
        app.loaded_cfg=dict(self.cfg); app.busy=False; app.drag=None
        app.fig=Figure(figsize=(10,8),layout='constrained'); app.canvas=FigureCanvasAgg(app.fig)
        app.target=Mock(); app.target.get.return_value='response'; app.status=Mock()
        app.draw()
        return app

    def test_response_drag_and_shared_roi(self):
        app=self.app(); old=app.data['centers'][0].copy()
        app.press(SimpleNamespace(button=1,inaxes=app.axes[0],xdata=old[0],ydata=old[1]))
        app.motion(SimpleNamespace(inaxes=app.axes[0],xdata=old[0]+3,ydata=old[1]+2))
        self.assertEqual(app.data['centers'][0],[old[0]+3,old[1]+2])
        self.assertEqual(app.data['centers'][1],self.preview['centers'][1])
        app.loaded_cfg['response_mode']='shared'
        app.motion(SimpleNamespace(inaxes=app.axes[0],xdata=120,ydata=120))
        self.assertTrue(all(p==[120,120] for p in app.data['centers']))
        app.canvas.draw()
        app.fig.savefig(self.out/'interactive_preview.png',dpi=130)

    def test_background_drag_clamps_and_recomputes(self):
        app=self.app(); app.target.get.return_value='background'; app.preview=Mock()
        x,y=app.data['bg_center']
        app.press(SimpleNamespace(button=1,inaxes=app.axes[3],xdata=x,ydata=y))
        app.motion(SimpleNamespace(inaxes=app.axes[3],xdata=-100,ydata=-100))
        ry,rx=np.array(app.data['bgk'].shape)//2
        self.assertEqual(app.data['bg_center'],[int(rx),int(ry)])
        app.release(None); app.preview.assert_called_once()

    def test_channel_ranges_and_csv(self):
        cfg=dict(self.cfg); cfg['color_max']=[.1,.2,.4,.8]
        self.assertNotEqual(rgb(np.array([[.08]]),cfg,0).tolist(),rgb(np.array([[.08]]),cfg,3).tolist())
        p=self.out
        with (p/'traces.csv').open(encoding='utf-8-sig') as f: rows=list(csv.DictReader(f))
        self.assertEqual(len(rows),len(self.preview['dff'])); self.assertEqual(len(rows[0]),10)
        self.assertFalse(any('roi_mean' in k for k in rows[0]))
        for ch in range(4):
            a=tifffile.imread(p/f'C{ch+1}_dff_float32.tif')
            mask=roi_mask(a.shape[1:],self.preview['rk'],self.preview['centers'][ch]) & self.preview['valid'][ch]
            np.testing.assert_allclose(mean(a[:,mask],axis=1),[float(r[f'C{ch+1}_mean_pixel_dff']) for r in rows],atol=1e-6)

if __name__=='__main__': unittest.main()
