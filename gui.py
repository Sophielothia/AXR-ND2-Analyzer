"""Interactive ROI review for 1–4 channels."""
import os, sys, json, threading, queue, subprocess
from pathlib import Path
from datetime import datetime
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
BASE = Path(__file__).parent
if (BASE/'tcl/tcl8.6/init.tcl').exists():
    os.environ['TCL_LIBRARY'] = str(BASE/'tcl/tcl8.6')
    os.environ['TK_LIBRARY'] = str(BASE/'tcl/tk8.6')
from analyze import run, roi_mask, mean, color_range, display_cmap, PALETTES
import nd2
import numpy as np
from matplotlib.figure import Figure
from matplotlib.patches import Ellipse
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib import colormaps
from matplotlib.colors import to_rgba

class App:
    def __init__(self, root):
        self.root=root; self.data=None; self.drag=None; self.busy=False; self.queue=queue.Queue()
        self.retained_roi=None
        self.channel_count=4
        self.cfg=json.loads((BASE/'settings.json').read_text(encoding='utf-8'))
        from ui import build_ui
        build_ui(self, root)
        root.after(100,self.poll)

    def browse(self):
        if self.busy: return
        name=filedialog.askopenfilename(filetypes=[('ND2','*.nd2')])
        if name:
            try:
                with nd2.ND2File(name) as f:
                    count=f.sizes.get('C',1)
                if not 1 <= count <= 4: raise ValueError(f'Expected 1–4 channels, got {count}')
            except Exception as exc:
                messagebox.showerror('ND2',str(exc)); return
            self.capture_roi()
            self.source.set(name); self.output.set(str(Path(name).parent)); self.data=None
            self.set_channel_count(count)
            self.status.set('ROI retained for next file.' if self.keep_roi.get() and self.retained_roi else 'Load preview to select automatic ROIs.')

    def capture_roi(self):
        if self.keep_roi.get() and self.data is not None:
            self.retained_roi={
                'background_center_xy':list(self.data['bg_center']),
                'response_centers_xy':[list(p) for p in self.data['centers']],
                'shape_yx':list(self.data['valid'].shape[-2:]),
                'channel_count':int(self.data['valid'].shape[0]),
                'pixel_size_um_xy':list(self.data['pixel']),
                'background_diameter_um':self.loaded_cfg['background_diameter_um'],
                'response_diameter_um':self.loaded_cfg['response_diameter_um'],
                'source':str(self.loaded_path.resolve())}

    def toggle_keep(self):
        if self.keep_roi.get():
            self.capture_roi()
            self.status.set('Keep ROIs enabled: current background and response ROIs will carry over.')
        else:
            self.retained_roi=None
            self.status.set('Keep ROIs disabled: next file uses automatic ROIs.')

    def browse_output(self):
        name=filedialog.askdirectory(initialdir=self.output.get() or str(BASE))
        if name: self.output.set(name)

    def set_channel_count(self,count):
        self.channel_count=count
        self.background_box.configure(values=['Auto (last)']+[f'C{i+1}' for i in range(count)])
        if self.background.get() not in self.background_box['values']: self.background.set('Auto (last)')
        for ch,widgets in enumerate(self.channel_widgets):
            for widget in widgets:
                widget.configure(state=('readonly' if isinstance(widget,ttk.Combobox) else 'normal') if ch<count else 'disabled')

    def change_unit(self,prefix):
        unit=self.units[prefix].get(); key=prefix+'_frames'
        fallback=[0,10] if prefix=='baseline' else [10,20]
        if unit=='seconds' and self.data is not None and self.data['times'] is not None:
            a,b=self.data.get('resolved_ranges',self.loaded_cfg)[key]
            value=[float(self.data['times'][a-1]),float(self.data['times'][b-1])]
        else: value=self.cfg.get(prefix+'_'+unit,fallback)
        for var,number in zip(self.range_entries[prefix],value): var.set(format(number,'.12g'))

    def values(self):
        cfg=dict(self.cfg); cfg.update({k:json.loads(v.get()) for k,v in self.entries.items()})
        for prefix,unit in self.units.items():
            cfg[prefix+'_unit']=unit.get()
            try:
                values=[float(var.get().strip()) for var in self.range_entries[prefix]]
                if not np.isfinite(values).all(): raise ValueError()
                if unit.get()=='frames':
                    if any(not value.is_integer() for value in values): raise ValueError()
                    values=[int(value) for value in values]
            except ValueError:
                raise ValueError(f'{prefix}: enter two finite numbers'+(' (whole frame numbers)' if unit.get()=='frames' else ' in seconds')) from None
            cfg[prefix+'_'+unit.get()]=values
        cfg['background_channel']=None if self.background.get()=='Auto (last)' else int(self.background.get()[1:])
        cfg['response_mode']=self.mode.get()
        cfg['color_min']=[float(p[0].get()) for p in self.limits]
        cfg['color_max']=[float(p[1].get()) for p in self.limits]
        cfg['trace_colors']=[v.get() for v in self.colors]
        cfg['colormap']=[v.get() for v in self.palettes]
        cfg['reverse_colormap']=[v.get() for v in self.reverses]
        for ch in range(self.channel_count): color_range(cfg,ch); display_cmap(cfg,ch); to_rgba(cfg['trace_colors'][ch])
        return cfg

    def launch(self,work,kind):
        self.busy=True; self.status.set('Computing...' if kind=='preview' else 'Saving...')
        self.progress.start(12)
        self.preview_button.configure(state='disabled'); self.save_button.configure(state='disabled')
        def worker():
            try: self.queue.put((kind,work(),None))
            except Exception as exc: self.queue.put((kind,None,str(exc)))
        threading.Thread(target=worker,daemon=True).start()

    def preview(self):
        if self.busy: return
        try:
            path=Path(self.source.get())
            if not path.is_file(): raise ValueError('Select a valid ND2 file')
            cfg=self.values()
            if self.data is not None and path==self.loaded_path:
                cfg['background_center_xy']=self.data['bg_center']
                cfg['response_centers_xy']=self.data['centers']
                if self.loaded_cfg.get('required_roi_geometry'):
                    cfg['required_roi_geometry']=self.loaded_cfg['required_roi_geometry']
            elif self.keep_roi.get():
                self.capture_roi()
                if self.retained_roi:
                    retained=self.retained_roi
                    for key in ('background_diameter_um','response_diameter_um'):
                        if cfg[key]!=retained[key]:
                            raise ValueError('Retained ROI diameter changed. Restore the original diameter, or disable Keep ROIs / Reset automatic ROIs.')
                    cfg['background_center_xy']=list(retained['background_center_xy'])
                    cfg['response_centers_xy']=[list(p) for p in retained['response_centers_xy']]
                    cfg['required_roi_geometry']=dict(retained)
            self.pending_cfg=cfg; self.pending_path=path
            self.launch(lambda:run(path,cfg,BASE/'preview_unused',preview_only=True),'preview')
        except Exception as exc: messagebox.showerror('Preview',str(exc))

    def poll(self):
        try:
            kind,result,error=self.queue.get_nowait(); self.busy=False
            self.progress.stop()
            self.preview_button.configure(state='normal'); self.save_button.configure(state='normal')
            if error: self.status.set('Failed. Recompute before saving.'); self.data=None; messagebox.showerror('Analysis',error)
            elif kind=='preview':
                self.data=result; self.loaded_cfg=self.pending_cfg; self.loaded_path=self.pending_path
                self.set_channel_count(result['valid'].shape[0])
                count=result['valid'].shape[0]; frames=result['dff'].shape[0]
                self.summary.set(f'{count} channels  ·  {frames} frames  ·  {self.loaded_path.name}')
                self.capture_roi()
                self.draw(); self.status.set('Preview ready — retained ROIs applied.' if self.loaded_cfg.get('required_roi_geometry') else 'Preview ready. Drag ROIs, then save.')
            else: self.status.set('Saved: '+str(result))
        except queue.Empty: pass
        self.root.after(100,self.poll)

    def draw(self):
        d=self.data; count=d['valid'].shape[0]; self.fig.clear()
        cols=min(count,2); rows=(count+cols-1)//cols
        grid=self.fig.add_gridspec(rows+1,cols)
        self.axes=[self.fig.add_subplot(grid[i//cols,i%cols]) for i in range(count)]
        self.trace_ax=self.fig.add_subplot(grid[rows,:]); self.patches=[]
        for ch,ax in enumerate(self.axes):
            cmap=display_cmap(self.loaded_cfg,ch); lo,hi=color_range(self.loaded_cfg,ch)
            im=ax.imshow(d['displays'][ch],cmap=cmap,vmin=lo,vmax=hi)
            self.fig.colorbar(im,ax=ax,fraction=.046,pad=.02)
            pair=[]
            for center,key,color in [(d['bg_center'],'background_diameter_um','cyan'),(d['centers'][ch],'response_diameter_um','white')]:
                p=Ellipse(center,self.loaded_cfg[key]/d['pixel'][0],self.loaded_cfg[key]/d['pixel'][1],fill=False,edgecolor=color,lw=1.5)
                ax.add_patch(p); pair.append(p)
            frames=d.get('resolved_ranges',self.loaded_cfg)['average_frames']
            self.patches.append(pair); ax.set_title(f'C{ch+1}: average frames {frames}')
            ax.tick_params(labelsize=8,colors='#627589')
        self.update_traces()

    def update_traces(self):
        d=self.data; ax=self.trace_ax; ax.clear()
        x=d['times'] if d['times'] is not None else np.arange(1,len(d['dff'])+1)
        for ch in range(d['valid'].shape[0]):
            mask=roi_mask(d['valid'][ch].shape,d['rk'],d['centers'][ch]) & d['valid'][ch]
            trace=mean(d['dff'][:,ch,mask],axis=1)
            ax.plot(x,trace,color=self.loaded_cfg['trace_colors'][ch],label=f'C{ch+1} ({mask.sum()/d["rk"].sum():.0%} valid)')
        ax.set_xlabel('Time (s)' if d['times'] is not None else 'Frame'); ax.set_ylabel('Mean pixel dF/F0')
        ax.spines[['top','right']].set_visible(False)
        ax.grid(axis='y',color='#e7eef3',linewidth=.6)
        ax.legend(ncol=2,fontsize=8); ax.axhline(0,color='gray',lw=.5); self.canvas.draw_idle()

    def apply_colors(self):
        if self.data is None or self.busy: return
        try:
            cfg=self.values()
            for k in ('color_min','color_max','trace_colors','colormap','reverse_colormap'): self.loaded_cfg[k]=cfg[k]
            self.draw()
        except Exception as exc: messagebox.showerror('Colors',str(exc))

    def press(self,e):
        if self.busy or self.data is None or e.button!=1 or e.inaxes not in self.axes: return
        ch=self.axes.index(e.inaxes); bg=self.target.get()=='background'
        center=self.data['bg_center'] if bg else self.data['centers'][ch]
        key='background_diameter_um' if bg else 'response_diameter_um'
        dx=(e.xdata-center[0])*self.data['pixel'][0]; dy=(e.ydata-center[1])*self.data['pixel'][1]
        if dx*dx+dy*dy <= (self.loaded_cfg[key]/2)**2: self.drag=(ch,bg,e.xdata-center[0],e.ydata-center[1])

    def motion(self,e):
        if self.drag is None or self.busy: return
        ch,bg,dx,dy=self.drag
        if e.inaxes!=self.axes[ch]: return
        d=self.data; kernel=d['bgk'] if bg else d['rk']; ry,rx=np.array(kernel.shape)//2; h,w=d['valid'][ch].shape
        center=[int(np.clip(round(e.xdata-dx),rx,w-rx-1)),int(np.clip(round(e.ydata-dy),ry,h-ry-1))]
        if bg:
            d['bg_center']=center
            for pair in self.patches: pair[0].center=center
            self.canvas.draw_idle()
        else:
            channels=range(d['valid'].shape[0]) if self.loaded_cfg['response_mode']=='shared' else [ch]
            for i in channels: d['centers'][i]=center.copy(); self.patches[i][1].center=center
            self.update_traces()
        self.status.set(f'{"Background" if bg else "Response C"+str(ch+1)} center: {center}')

    def release(self,e):
        if self.drag is None: return
        bg=self.drag[1]; self.drag=None
        if bg: self.preview()

    def reset(self):
        if not self.busy:
            self.data=None; self.retained_roi=None; self.preview()

    def save(self):
        if self.busy: return
        try:
            if self.data is None: raise ValueError('Load and review preview first')
            cfg=self.values()
            keys=list(self.entries)+['background_channel','baseline_unit','average_unit','baseline_seconds','average_seconds','baseline_frames','average_frames']
            if any(cfg.get(k)!=self.loaded_cfg.get(k) for k in keys) or cfg['response_mode']!=self.loaded_cfg['response_mode']:
                raise ValueError('Parameters changed: recompute preview before saving')
            if Path(self.source.get())!=self.loaded_path: raise ValueError('Input changed: load preview first')
            cfg['background_center_xy']=self.data['bg_center']; cfg['response_centers_xy']=self.data['centers']
            if self.loaded_cfg.get('required_roi_geometry'):
                cfg['required_roi_geometry']=self.loaded_cfg['required_roi_geometry']
            if not self.output.get().strip(): raise ValueError('Choose an output folder')
            stamp=datetime.now().strftime('%Y%m%d_%H%M%S_%f')
            out=Path(self.output.get())/(self.loaded_path.stem+'_results_'+stamp)
            config=BASE/'runs'/('review_'+stamp+'.json'); config.parent.mkdir(exist_ok=True)
            config.write_text(json.dumps(cfg,indent=2),encoding='utf-8'); path=self.loaded_path
            def export():
                p=subprocess.run([sys.executable,str(BASE/'analyze.py'),str(path),'--config',str(config),'--output',str(out)],
                    capture_output=True,text=True,encoding='utf-8',errors='replace',creationflags=subprocess.CREATE_NO_WINDOW)
                config.with_suffix('.log').write_text(p.stdout+p.stderr,encoding='utf-8')
                if p.returncode: raise RuntimeError(p.stdout+p.stderr)
                return out
            self.launch(export,'save')
        except Exception as exc: messagebox.showerror('Save',str(exc))

if __name__=='__main__':
    root=tk.Tk(); app=App(root); root.mainloop()
