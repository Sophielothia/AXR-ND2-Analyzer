"""Tk interface styling and layout; analysis lives in analyze.py."""
import json
import tkinter as tk
from tkinter import ttk
from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from analyze import PALETTES, channel_value

BG = '#eef3f7'
INK = '#172d40'
MUTED = '#627589'
ACCENT = '#008080'


def build_ui(app, root):
    root.title('AXR · ND2 Analyzer')
    root.geometry('1480x960')
    root.minsize(1120, 760)
    root.configure(background=BG)
    style = ttk.Style(root)
    style.theme_use('clam')
    root.option_add('*Font', ('Segoe UI', 10))
    style.configure('.', font=('Segoe UI', 10), foreground=INK, background='white')
    style.configure('TFrame', background='white')
    style.configure('Shell.TFrame', background=BG)
    style.configure('TLabel', background='white', foreground=INK)
    style.configure('Muted.TLabel', foreground=MUTED, font=('Segoe UI', 9))
    style.configure('Heading.TLabel', font=('Segoe UI Semibold', 12))
    style.configure('TEntry', padding=(7, 6), fieldbackground='#f7f9fb', bordercolor='#d6e0e9', lightcolor='#d6e0e9')
    style.configure('TCombobox', padding=(6, 5), fieldbackground='#f7f9fb', bordercolor='#d6e0e9', arrowsize=12)
    style.map('TCombobox', fieldbackground=[('readonly', '#f7f9fb')], foreground=[('disabled', '#a2adba')])
    style.configure('TButton', padding=(12, 8), background='#edf3f6', borderwidth=0, foreground=INK)
    style.map('TButton', background=[('active', '#dfecef'), ('disabled', '#f0f3f5')])
    style.configure('Primary.TButton', background=ACCENT, foreground='white', font=('Segoe UI Semibold', 10))
    style.map('Primary.TButton', background=[('active', '#006d6d'), ('disabled', '#91b8b8')], foreground=[('disabled', 'white')])
    style.configure('TCheckbutton', background='white', padding=(0, 4))
    style.configure('TRadiobutton', background='white', padding=(0, 4))
    style.configure('TNotebook', background=BG, borderwidth=0, tabmargins=0)
    style.configure('TNotebook.Tab', padding=(13, 10), background='#e6edf3', foreground=MUTED)
    style.map('TNotebook.Tab', background=[('selected', 'white')], foreground=[('selected', ACCENT)])
    style.configure('Horizontal.TProgressbar', troughcolor='#dde8ee', background=ACCENT, borderwidth=0, thickness=3)

    header = tk.Frame(root, background=INK, padx=24, pady=16)
    header.pack(fill='x')
    tk.Label(header, text='AXR  /  ND2 Analyzer', foreground='white', background=INK,
             font=('Segoe UI Semibold', 20)).pack(side='left')
    tk.Label(header, text='1–4 CHANNELS    ·    ΔF/F₀    ·    ROI REVIEW', foreground='#9ec9d0',
             background=INK, font=('Segoe UI', 10)).pack(side='right')

    body = ttk.Frame(root, style='Shell.TFrame', padding=(16, 14))
    body.pack(fill='both', expand=True)
    sidebar = ttk.Frame(body, width=420, style='Shell.TFrame')
    sidebar.pack(side='left', fill='y', padx=(0, 14)); sidebar.pack_propagate(False)

    def card(parent, title, subtitle=None):
        frame = ttk.Frame(parent, padding=14)
        frame.pack(fill='x', pady=(0, 12))
        ttk.Label(frame, text=title, style='Heading.TLabel').pack(anchor='w', pady=(0, 8))
        if subtitle:
            ttk.Label(frame, text=subtitle, style='Muted.TLabel', wraplength=380).pack(anchor='w', pady=(0, 8))
        return frame

    source_card = card(sidebar, '01   Input & output')
    app.source = tk.StringVar(); app.output = tk.StringVar()
    for title, var, command in [('ND2 file', app.source, app.browse), ('Results folder', app.output, app.browse_output)]:
        ttk.Label(source_card, text=title, style='Muted.TLabel').pack(anchor='w', pady=(3, 3))
        row = ttk.Frame(source_card); row.pack(fill='x', pady=(0, 6))
        ttk.Entry(row, textvariable=var).pack(side='left', fill='x', expand=True)
        ttk.Button(row, text='Browse', command=command, width=7).pack(side='right', padx=(6, 0))

    notebook = ttk.Notebook(sidebar); notebook.pack(fill='both', expand=True)
    app.notebook = notebook

    def scroll_tab(title):
        outer = ttk.Frame(notebook); notebook.add(outer, text=title)
        canvas = tk.Canvas(outer, background='white', borderwidth=0, highlightthickness=0)
        bar = ttk.Scrollbar(outer, orient='vertical', command=canvas.yview)
        canvas.configure(yscrollcommand=bar.set)
        bar.pack(side='right', fill='y'); canvas.pack(side='left', fill='both', expand=True)
        page = ttk.Frame(canvas, padding=(14, 12)); item = canvas.create_window((0, 0), window=page, anchor='nw')
        page.bind('<Configure>', lambda e: canvas.configure(scrollregion=canvas.bbox('all')))
        canvas.bind('<Configure>', lambda e: canvas.itemconfigure(item, width=e.width))
        def wheel(event):
            if str(event.widget).startswith(str(outer)) and event.delta:
                canvas.yview_scroll(-int(event.delta / 120), 'units')
        root.bind_all('<MouseWheel>', wheel, add='+')
        return page

    analysis = scroll_tab('Analysis')
    display = scroll_tab('Display')
    advanced = scroll_tab('Advanced')
    app.range_entries = {}; app.units = {}; app.entries = {}
    ttk.Label(analysis, text='Time windows', style='Heading.TLabel').pack(anchor='w', pady=(0, 8))
    for prefix, title in [('baseline', 'Baseline · F₀'), ('average', 'Average · response map')]:
        frame = ttk.Frame(analysis); frame.pack(fill='x', pady=(0, 12))
        top = ttk.Frame(frame); top.pack(fill='x')
        ttk.Label(top, text=title).pack(side='left')
        unit = tk.StringVar(value=app.cfg.get(prefix+'_unit', 'frames')); app.units[prefix] = unit
        box = ttk.Combobox(top, textvariable=unit, values=['frames', 'seconds'], state='readonly', width=8)
        box.pack(side='right'); box.bind('<<ComboboxSelected>>', lambda e, p=prefix: app.change_unit(p))
        row = ttk.Frame(frame); row.pack(fill='x', pady=(5, 0))
        pair = [tk.StringVar(value=format(v, '.12g')) for v in app.cfg[prefix+'_'+unit.get()]]
        app.range_entries[prefix] = pair
        for j, (label, var) in enumerate(zip(('Start / a', 'End / b'), pair)):
            col = ttk.Frame(row); col.pack(side='left', fill='x', expand=True, padx=(0, 8) if j==0 else (0, 0))
            ttk.Label(col, text=label, style='Muted.TLabel').pack(anchor='w')
            ttk.Entry(col, textvariable=var, width=18).pack(fill='x', pady=(3, 0))
    ttk.Separator(analysis).pack(fill='x', pady=8)
    ttk.Label(analysis, text='ROI selection', style='Heading.TLabel').pack(anchor='w', pady=(4, 8))

    def field(parent, key, label):
        row = ttk.Frame(parent); row.pack(fill='x', pady=4)
        ttk.Label(row, text=label).pack(side='left')
        app.entries[key] = tk.StringVar(value=json.dumps(app.cfg.get(key)))
        ttk.Entry(row, textvariable=app.entries[key], width=14).pack(side='right')

    field(analysis, 'background_diameter_um', 'Background diameter · µm')
    field(analysis, 'response_diameter_um', 'Response diameter · µm')
    ttk.Label(analysis, text='Background reference', style='Muted.TLabel').pack(anchor='w', pady=(8, 3))
    app.background = tk.StringVar(value='Auto (last)' if app.cfg.get('background_channel') is None else f'C{app.cfg["background_channel"]}')
    app.background_box = ttk.Combobox(analysis, textvariable=app.background, values=['Auto (last)', 'C1', 'C2', 'C3', 'C4'], state='readonly')
    app.background_box.pack(fill='x')
    ttk.Label(analysis, text='Response ROI mode', style='Muted.TLabel').pack(anchor='w', pady=(8, 3))
    app.mode = tk.StringVar(value=app.cfg['response_mode'])
    ttk.Combobox(analysis, textvariable=app.mode, values=['independent', 'shared'], state='readonly').pack(fill='x')
    field(analysis, 'response_channel', 'Shared reference · channel')
    app.keep_roi = tk.BooleanVar(value=False)
    ttk.Checkbutton(analysis, text='Keep ROIs for the next file / 保留 ROI', variable=app.keep_roi, command=app.toggle_keep).pack(anchor='w', pady=(7, 4))
    ttk.Button(analysis, text='Reset automatic ROIs', command=app.reset).pack(fill='x', pady=(4, 8))

    ttk.Label(display, text='Channel appearance', style='Heading.TLabel').pack(anchor='w')
    ttk.Label(display, text='Display settings do not change quantitative data.', style='Muted.TLabel', wraplength=360).pack(anchor='w', pady=(4, 12))
    app.limits=[]; app.colors=[]; app.channel_widgets=[]; app.palettes=[]; app.reverses=[]
    for ch in range(4):
        frame = ttk.Frame(display); frame.pack(fill='x', pady=(0, 12))
        widgets=[]
        top = ttk.Frame(frame); top.pack(fill='x')
        color = tk.StringVar(value=app.cfg['trace_colors'][ch]); app.colors.append(color)
        swatch=tk.Label(top, text='●', foreground=color.get(), background='white', font=('Segoe UI', 12))
        swatch.pack(side='left')
        def refresh_swatch(*args, var=color, label=swatch):
            try: label.configure(foreground=var.get())
            except tk.TclError: pass
        color.trace_add('write',refresh_swatch)
        ttk.Label(top, text=f'  Channel {ch+1}', style='Heading.TLabel').pack(side='left')
        row = ttk.Frame(frame); row.pack(fill='x', pady=5)
        pair=[tk.StringVar(value=str(channel_value(app.cfg,key,ch,default))) for key,default in [('color_min',0),('color_max',.3)]]
        app.limits.append(pair)
        for j,(label,var) in enumerate(zip(('Endpoint 1', 'Endpoint 2'),pair)):
            col=ttk.Frame(row); col.pack(side='left', fill='x', expand=True, padx=(0, 6) if j==0 else (0, 0))
            ttk.Label(col,text=label,style='Muted.TLabel').pack(anchor='w')
            widget=ttk.Entry(col,textvariable=var,width=15); widget.pack(fill='x'); widgets.append(widget)
        palette=tk.StringVar(value=channel_value(app.cfg,'colormap',ch,'jet')); app.palettes.append(palette)
        row=ttk.Frame(frame); row.pack(fill='x',pady=3)
        widget=ttk.Combobox(row,textvariable=palette,values=PALETTES,state='readonly',width=18)
        widget.pack(side='left',fill='x',expand=True); widgets.append(widget)
        reverse=tk.BooleanVar(value=channel_value(app.cfg,'reverse_colormap',ch,False)); app.reverses.append(reverse)
        widget=ttk.Checkbutton(row,text='Reverse',variable=reverse); widget.pack(side='right',padx=(7,0)); widgets.append(widget)
        row=ttk.Frame(frame); row.pack(fill='x',pady=3)
        ttk.Label(row,text='Trace color',style='Muted.TLabel').pack(side='left')
        widget=ttk.Entry(row,textvariable=color,width=12); widget.pack(side='right'); widgets.append(widget)
        ttk.Separator(display).pack(fill='x',pady=(0,10))
        app.channel_widgets.append(widgets)
    ttk.Button(display,text='Apply display ranges / colors',command=app.apply_colors).pack(fill='x',pady=(0,10))

    ttk.Label(advanced,text='Signal processing',style='Heading.TLabel').pack(anchor='w',pady=(0,8))
    for key,label in [('sigma_px','Initial Gaussian σ · px'),('display_sigma_px','Display Gaussian σ · px'),
                      ('threshold_min','F₀ threshold · min'),('threshold_max','F₀ threshold · max'),
                      ('min_valid_fraction','Auto ROI · valid fraction')]: field(advanced,key,label)
    ttk.Separator(advanced).pack(fill='x',pady=12)
    ttk.Label(advanced,text='Calibration overrides',style='Heading.TLabel').pack(anchor='w',pady=(0,8))
    ttk.Label(advanced,text='Keep null to use ND2 metadata.',style='Muted.TLabel').pack(anchor='w',pady=(0,8))
    field(advanced,'pixel_size_um_xy','Pixel size [x, y] · µm')
    field(advanced,'frame_interval_s','Frame interval · s')

    actions=ttk.Frame(sidebar,padding=(0,12,0,0),style='Shell.TFrame'); actions.pack(fill='x')
    app.preview_button=ttk.Button(actions,text='1. Load / recompute preview',style='Primary.TButton',command=app.preview)
    app.preview_button.pack(fill='x',pady=(0,7))
    app.save_button=ttk.Button(actions,text='2. Save reviewed results',command=app.save)
    app.save_button.pack(fill='x')

    review=ttk.Frame(body,padding=14); review.pack(side='right',fill='both',expand=True)
    top=ttk.Frame(review); top.pack(fill='x',pady=(0,8))
    ttk.Label(top,text='02   Review & refine',style='Heading.TLabel').pack(side='left')
    app.summary=tk.StringVar(value='No file loaded')
    ttk.Label(top,textvariable=app.summary,style='Muted.TLabel').pack(side='right')
    tools=ttk.Frame(review); tools.pack(fill='x',pady=(0,8))
    app.target=tk.StringVar(value='response')
    ttk.Radiobutton(tools,text='Response ROI · white',variable=app.target,value='response').pack(side='left')
    ttk.Radiobutton(tools,text='Background ROI · cyan',variable=app.target,value='background').pack(side='left',padx=14)
    app.fig=Figure(figsize=(10,8),layout='constrained',facecolor='white')
    ax=app.fig.add_subplot(111); ax.axis('off')
    ax.text(.5,.59,'Your response maps, together.',ha='center',va='center',fontsize=21,color=INK,transform=ax.transAxes)
    ax.text(.5,.49,'Choose an ND2 file and load the preview.\nDrag ROIs to compare the same regions across channels.',
            ha='center',va='center',fontsize=11,color=MUTED,linespacing=1.8,transform=ax.transAxes)
    app.canvas=FigureCanvasTkAgg(app.fig,master=review); app.canvas.get_tk_widget().pack(fill='both',expand=True)
    ttk.Label(review,text='Drag within a circle. Response traces update live; background recalculates on release.',style='Muted.TLabel').pack(anchor='w',pady=(8,0))
    app.axes=[]
    for name,callback in [('button_press_event',app.press),('motion_notify_event',app.motion),('button_release_event',app.release)]:
        app.canvas.mpl_connect(name,callback)
    footer=ttk.Frame(root,padding=(20,8)); footer.pack(fill='x')
    app.status=tk.StringVar(value='Ready · Select an ND2 file to begin.')
    ttk.Label(footer,textvariable=app.status,style='Muted.TLabel',wraplength=1150).pack(side='left')
    app.progress=ttk.Progressbar(footer,mode='indeterminate',length=120)
    app.progress.pack(side='right',padx=(12,0))
