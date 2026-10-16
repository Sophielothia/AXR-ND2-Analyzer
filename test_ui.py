"""Build the actual Tk interface without showing a desktop window."""
import unittest
import tkinter as tk
from gui import App


class InterfaceTests(unittest.TestCase):
    def setUp(self):
        try:
            self.root=tk.Tk()
        except tk.TclError as exc:
            self.skipTest(f'Tk unavailable: {exc}')
        self.root.withdraw()
        self.app=App(self.root)
        self.root.update_idletasks()

    def tearDown(self):
        if hasattr(self,'root'): self.root.destroy()

    def test_tabs_ranges_and_channel_controls(self):
        self.assertEqual([self.app.notebook.tab(t,'text') for t in self.app.notebook.tabs()],
                         ['Analysis','Display','Advanced'])
        self.app.units['baseline'].set('seconds')
        self.app.range_entries['baseline'][0].set('3.324361000061')
        self.app.range_entries['baseline'][1].set('19.90748199987')
        self.app.range_entries['average'][0].set('8')
        self.app.range_entries['average'][1].set('15')
        cfg=self.app.values()
        self.assertEqual(cfg['baseline_seconds'],[3.324361000061,19.90748199987])
        self.assertEqual(cfg['average_frames'],[8,15])
        self.app.set_channel_count(2)
        self.assertEqual(tuple(self.app.background_box['values']),('Auto (last)','C1','C2'))
        self.assertEqual(str(self.app.channel_widgets[2][0]['state']),'disabled')
        self.app.background.set('C2')
        self.assertEqual(self.app.values()['background_channel'],2)

    def test_frame_decimal_rejected(self):
        self.app.range_entries['baseline'][0].set('2.5')
        with self.assertRaisesRegex(ValueError,'whole frame numbers'): self.app.values()


if __name__=='__main__': unittest.main()
