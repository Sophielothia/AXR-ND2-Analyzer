import unittest
import json
from pathlib import Path
from unittest.mock import Mock, patch
import numpy as np
from analyze import run
from gui import App

BASE=Path(__file__).parent


class CarryoverTests(unittest.TestCase):
    def app(self, enabled=True):
        app=App.__new__(App)
        app.keep_roi=Mock(); app.keep_roi.get.return_value=enabled
        app.retained_roi=None; app.busy=False; app.status=Mock()
        app.source=Mock(); app.output=Mock()
        app.loaded_path=BASE/'first.nd2'
        app.loaded_cfg=json.loads((BASE/'settings.json').read_text())
        app.data={'bg_center':[30,30],'centers':[[80,80],[90,90],[100,100],[105,105]],
                  'valid':np.ones((4,160,160),bool),'pixel':[1.,1.]}
        return app

    def test_browse_preserves_all_centers_and_snapshot_is_independent(self):
        app=self.app(); original=app.data
        app.set_channel_count=Mock()
        with patch('gui.filedialog.askopenfilename',return_value=str(BASE/'second.nd2')), patch('gui.nd2.ND2File') as reader:
            reader.return_value.__enter__.return_value.sizes={'C':4}
            app.browse()
        self.assertIsNone(app.data)
        self.assertEqual(app.retained_roi['background_center_xy'],[30,30])
        self.assertEqual(app.retained_roi['response_centers_xy'],original['centers'])
        original['centers'][0][0]=0
        self.assertEqual(app.retained_roi['response_centers_xy'][0],[80,80])

    def test_disabled_does_not_carry_and_reset_clears(self):
        app=self.app(False); app.capture_roi(); self.assertIsNone(app.retained_roi)
        app.keep_roi.get.return_value=True; app.capture_roi()
        app.preview=Mock(); app.reset()
        self.assertIsNone(app.retained_roi); self.assertIsNone(app.data)
        app.preview.assert_called_once()

    def test_next_preview_receives_retained_roi_configuration(self):
        app=self.app(); app.capture_roi(); app.data=None
        app.source.get.return_value=str(BASE/'second.nd2')
        app.values=Mock(return_value=dict(app.loaded_cfg))
        app.launch=Mock()
        with patch('pathlib.Path.is_file',return_value=True):
            app.preview()
        self.assertEqual(app.pending_cfg['response_centers_xy'],app.retained_roi['response_centers_xy'])
        self.assertEqual(app.pending_cfg['required_roi_geometry']['source'],str(app.loaded_path.resolve()))
        app.launch.assert_called_once()

    def test_retained_analysis_never_auto_searches_and_rejects_geometry(self):
        app=self.app(); app.capture_roi(); ref=app.retained_roi
        cfg=dict(app.loaded_cfg)
        cfg.update(background_center_xy=ref['background_center_xy'],
                   response_centers_xy=ref['response_centers_xy'],required_roi_geometry=ref)
        rng=np.random.default_rng(4)
        a=rng.uniform(100,200,(30,4,160,160)).astype('float32')
        a[:,:,60:150,60:150]+=500
        with patch('analyze.read_nd2',return_value=(a,[1.,1.],None,{})), patch('analyze.find_roi') as search:
            result=run(BASE/'second.nd2',cfg,BASE/'unused',preview_only=True)
            search.assert_not_called()
        self.assertEqual(result['bg_center'],ref['background_center_xy'])
        self.assertEqual(result['centers'],ref['response_centers_xy'])
        with patch('analyze.read_nd2',return_value=(a,[2.,2.],None,{})):
            with self.assertRaisesRegex(ValueError,'identical image dimensions'):
                run(BASE/'second.nd2',cfg,BASE/'unused',preview_only=True)
        with patch('analyze.read_nd2',return_value=(a[:,:,:150,:],[1.,1.],None,{})):
            with self.assertRaisesRegex(ValueError,'identical image dimensions'):
                run(BASE/'second.nd2',cfg,BASE/'unused',preview_only=True)


if __name__=='__main__': unittest.main()
