"""Nikon AXR TCYX analysis. Frame ranges are 1-based and inclusive."""
import argparse
import csv
import json
import warnings
from pathlib import Path
import os
os.environ.setdefault('MPLCONFIGDIR', str(Path(__file__).parent/'.mplconfig'))
import numpy as np
import nd2
from scipy.ndimage import gaussian_filter
from scipy.signal import fftconvolve
import tifffile
from PIL import Image
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Ellipse
from matplotlib.colors import LinearSegmentedColormap, ListedColormap

PALETTES = ['jet', 'Fire', 'GreenFireBlue', 'mpl-viridis', 'mpl-plasma', 'inferno', 'magma', 'coolwarm', 'gray']


def channel_value(cfg, key, ch, default):
    value = cfg.get(key, default)
    return value[ch] if isinstance(value, list) else value


def display_cmap(cfg, ch):
    name = channel_value(cfg, 'colormap', ch, 'jet')
    if name == 'Fire':
        # ImageJ LutLoader.fire 32 control colors and its nColors/256 interpolation.
        r = [0,0,1,25,49,73,98,122,146,162,173,184,195,207,217,229,240,252,255,255,255,255,255,255,255,255,255,255,255,255,255,255]
        g = [0,0,0,0,0,0,0,0,0,0,0,0,0,14,35,57,79,101,117,133,147,161,175,190,205,219,234,248,255,255,255,255]
        b = [0,61,96,130,165,192,220,227,210,181,151,122,93,64,35,5,0,0,0,0,0,0,0,0,0,0,0,35,98,160,223,255]
        lut = np.stack([np.interp(np.arange(256)*32/256,np.arange(32),v) for v in (r,g,b)],axis=1).astype('uint8')
        cmap = ListedColormap(lut/255, name='Fire')
    elif name == 'GreenFireBlue':
        from cmap import Colormap
        cmap = Colormap('imagej:GreenFireBlue').to_matplotlib()
    else:
        cmap = matplotlib.colormaps[name.removeprefix('mpl-')].copy()
    lo = channel_value(cfg,'color_min',ch,0)
    hi = channel_value(cfg,'color_max',ch,.3)
    if bool(channel_value(cfg,'reverse_colormap',ch,False)) ^ (lo > hi):
        cmap = cmap.reversed()
    return cmap.with_extremes(bad='black')


def resolve_range(cfg, prefix, t, times):
    unit = cfg.get(prefix+'_unit', 'frames')
    key = prefix+'_seconds' if unit == 'seconds' else prefix+'_frames'
    start, stop = cfg[key]
    if unit == 'seconds':
        if times is None:
            raise ValueError('Seconds mode requires valid timestamps or frame_interval_s.')
        if not np.isfinite([start,stop]).all() or start < 0 or start > stop or stop > times[-1]+1e-7:
            raise ValueError(f'{prefix}: seconds must satisfy 0 <= start <= end <= {times[-1]:.6g}')
        indices = np.flatnonzero((times >= start-1e-7) & (times <= stop+1e-7))
        if not len(indices): raise ValueError(f'{prefix}: no frame timestamps in this seconds range')
        return slice(int(indices[0]),int(indices[-1])+1)
    if unit != 'frames': raise ValueError('Range unit must be frames or seconds')
    if not (isinstance(start,int) and isinstance(stop,int) and 1 <= start <= stop <= t):
        raise ValueError(f'{key} must be integer inclusive frame range within 1..{t}')
    return slice(start-1,stop)


def mean(a, axis=0):
    valid = np.isfinite(a)
    n = valid.sum(axis=axis)
    return np.divide(np.where(valid, a, 0).sum(axis=axis), n,
                     out=np.full(np.shape(n), np.nan, dtype=np.float32), where=n > 0)


def disk(radius, pixel):
    px, py = pixel
    rx, ry = int(np.floor(radius / px)), int(np.floor(radius / py))
    y, x = np.mgrid[-ry:ry+1, -rx:rx+1]
    return (x*px)**2 + (y*py)**2 <= radius**2


def roi_mask(shape, kernel, center):
    x, y = map(int, center)
    ry, rx = np.array(kernel.shape)//2
    h, w = shape
    if not (rx <= x < w-rx and ry <= y < h-ry):
        raise ValueError('ROI extends outside image; reduce radius or change center.')
    out = np.zeros(shape, bool)
    out[y-ry:y+ry+1, x-rx:x+rx+1] = kernel
    return out


def find_roi(a, kernel, maximize=True, fraction=1):
    if any(k > s for k, s in zip(kernel.shape, a.shape)):
        raise ValueError('ROI diameter exceeds field of view; check radius and pixel calibration.')
    valid = np.isfinite(a)
    count = np.rint(fftconvolve(valid.astype(float), kernel, mode='valid'))
    total = fftconvolve(np.where(valid, a, 0), kernel, mode='valid')
    eligible = (count >= np.ceil(kernel.sum()*fraction)) & (count > 0)
    score = np.divide(total, count, out=np.zeros_like(total), where=count > 0)
    if not eligible.any():
        raise ValueError('No eligible ROI: adjust F0 thresholds, radius or min_valid_fraction.')
    score[~eligible] = -np.inf if maximize else np.inf
    y, x = np.unravel_index(np.argmax(score) if maximize else np.argmin(score), score.shape)
    ry, rx = np.array(kernel.shape)//2
    return [int(x+rx), int(y+ry)]


def smooth_display(a, sigma):
    if sigma == 0:
        return a.copy()
    ok = np.isfinite(a)
    weight = gaussian_filter(ok.astype(np.float32), sigma=(0, sigma, sigma))
    value = gaussian_filter(np.where(ok, a, 0), sigma=(0, sigma, sigma))
    out = np.divide(value, weight, out=np.full_like(value, np.nan), where=weight > 1e-6)
    out[~ok] = np.nan  # preserve the baseline mask; do not fill masked pixels
    return out


def color_range(cfg, ch):
    lo, hi = cfg['color_min'], cfg['color_max']
    if any(isinstance(v, list) and len(v) <= ch for v in (lo, hi)):
        raise ValueError(f'Missing color range for C{ch+1}')
    lo = lo[ch] if isinstance(lo, list) else lo
    hi = hi[ch] if isinstance(hi, list) else hi
    if not np.isfinite([lo, hi]).all() or hi == lo:
        raise ValueError(f'C{ch+1}: display endpoints must be finite and different')
    return min(lo,hi), max(lo,hi)


def rgb(a, cfg, ch=0):
    lo, hi = color_range(cfg, ch)
    scaled = (a-lo)/(hi-lo)
    out = (display_cmap(cfg,ch)(np.clip(np.nan_to_num(scaled), 0, 1))[..., :3]*255).astype('uint8')
    out[~np.isfinite(a)] = 0
    return out


def read_nd2(path, cfg):
    with nd2.ND2File(path) as f:
        axes = list(f.sizes)
        a = f.asarray()
        for ax in list(axes):
            if ax not in 'TCYX':
                i = axes.index(ax)
                if a.shape[i] != 1:
                    raise ValueError(f'Unsupported dimension {ax}: {a.shape[i]}; select one position/Z first.')
                a = np.squeeze(a, axis=i)
                axes.pop(i)
        if 'C' not in axes:
            a = np.expand_dims(a, axis=0)
            axes.insert(0, 'C')
        if set(axes) != set('TCYX'):
            raise ValueError(f'Expected TCYX axes, got {axes}')
        a = np.transpose(a, [axes.index(ax) for ax in 'TCYX']).astype(np.float32)
        v = f.voxel_size()
        pixel = cfg['pixel_size_um_xy'] or [v.x, v.y]
        times = None
        try:
            times = np.array([f.frame_metadata(i).channels[0].time.relativeTimeMs/1000
                              for i in range(a.shape[0])])
            times -= times[0]
        except (AttributeError, IndexError, TypeError):
            pass
        meta = {'source_sizes': dict(f.sizes), 'voxel_size_um': list(v),
                'channel_names': [c.channel.name for c in f.metadata.channels]}
    if not 1 <= a.shape[1] <= 4:
        raise ValueError(f'Expected 1–4 channels, got {a.shape[1]}')
    if not np.all(np.isfinite(pixel)) or min(pixel) <= 0:
        raise ValueError('Missing pixel calibration. Set pixel_size_um_xy explicitly.')
    if cfg['frame_interval_s'] is not None:
        if cfg['frame_interval_s'] <= 0:
            raise ValueError('frame_interval_s must be positive')
        times = np.arange(len(a))*cfg['frame_interval_s']
    if times is not None and (not np.isfinite(times).all() or np.any(np.diff(times) <= 0)):
        times = None
    return a, pixel, times, meta


def run(path, cfg, out, preview_only=False):
    if not preview_only and out.exists() and any(out.iterdir()):
        raise ValueError(f'Output directory is not empty: {out}. Choose a new directory.')
    for key in ('sigma_px', 'display_sigma_px'):
        if cfg[key] < 0:
            raise ValueError(f'{key} must be nonnegative')
    if cfg['threshold_max'] < cfg['threshold_min']:
        raise ValueError('Invalid display range or threshold range')
    if not 0 < cfg['min_valid_fraction'] <= 1:
        raise ValueError('min_valid_fraction must be in (0,1]')
    if min(cfg['background_diameter_um'], cfg['response_diameter_um']) <= 0:
        raise ValueError('ROI diameters must be positive')
    a, pixel, times, meta = read_nd2(path, cfg)
    t, c, h, w = a.shape
    if not 1 <= c <= 4:
        raise ValueError('Expected 1–4 channels')
    for ch in range(c):
        color_range(cfg, ch)
        display_cmap(cfg, ch)
    if len(cfg['trace_colors']) < c:
        raise ValueError(f'trace_colors requires at least {c} colors')
    bg_channel = cfg.get('background_channel')
    bg_channel = c if bg_channel is None else bg_channel
    if not isinstance(bg_channel, int) or not 1 <= bg_channel <= c:
        raise ValueError(f'background_channel must be null (last channel) or 1..{c}')
    reference = cfg.get('required_roi_geometry')
    if reference:
        if reference.get('channel_count', len(reference['response_centers_xy'])) != c:
            raise ValueError('Retained ROIs require identical channel counts. Disable Keep ROIs or Reset automatic ROIs.')
        if list(a.shape[-2:]) != reference['shape_yx'] or not np.allclose(
                pixel, reference['pixel_size_um_xy'], rtol=1e-6, atol=1e-9):
            raise ValueError('Retained ROIs require identical image dimensions and pixel calibration. '
                             'Disable Keep ROIs or Reset automatic ROIs for this file.')
        if any(cfg[key] != reference[key] for key in ('background_diameter_um','response_diameter_um')):
            raise ValueError('Retained ROI diameters must match the reference file.')
    baseline, average = [resolve_range(cfg,key,t,times) for key in ('baseline','average')]
    resolved = {'baseline_frames':[baseline.start+1,baseline.stop], 'average_frames':[average.start+1,average.stop]}
    bgk = disk(cfg['background_diameter_um'] / 2, pixel)
    rk = disk(cfg['response_diameter_um'] / 2, pixel)
    bg_image = a[:, bg_channel-1].mean(axis=0)
    bg_center = cfg['background_center_xy'] or find_roi(bg_image, bgk, False)
    bg = roi_mask((h, w), bgk, bg_center)
    print(f'TCYX={a.shape}, pixel um={pixel}, background center={bg_center}', flush=True)
    filtered = gaussian_filter(a, sigma=(0, 0, cfg['sigma_px'], cfg['sigma_px']))
    background_values = filtered[:, :, bg].mean(axis=-1)
    corrected = filtered-background_values[:, :, None, None]
    f0 = corrected[baseline].mean(axis=0)
    valid = (f0 >= cfg['threshold_min']) & (f0 <= cfg['threshold_max']) & (f0 > 0)
    f0[~valid] = np.nan
    dff = (corrected-f0)/f0
    avg = mean(dff[average], axis=0)
    centers = cfg['response_centers_xy']
    if centers is None:
        if cfg['response_mode'] == 'shared':
            ch = cfg['response_channel']-1
            if not isinstance(ch, int) or not 0 <= ch < c:
                raise ValueError(f'response_channel must be 1..{c}')
            centers = [find_roi(avg[ch], rk, True, cfg['min_valid_fraction'])]*c
        elif cfg['response_mode'] == 'independent':
            centers = [find_roi(im, rk, True, cfg['min_valid_fraction']) for im in avg]
        else:
            raise ValueError('response_mode must be independent or shared')
    if len(centers) != c:
        raise ValueError(f'response_centers_xy must contain {c} [x,y] centers')
    traces, fractions = [], []
    for ch, center in enumerate(centers):
        mask = roi_mask((h, w), rk, center) & valid[ch]
        fractions.append(float(mask.sum()/rk.sum()))
        if mask.sum() == 0:
            raise ValueError(f'Channel {ch+1} response ROI has no valid F0 pixels')
        traces.append(mean(dff[:, ch, mask], axis=1))
    if preview_only:
        displays = np.stack([mean(smooth_display(dff[:, ch], cfg['display_sigma_px'])[average], axis=0)
                             for ch in range(c)])
        return dict(dff=dff, displays=displays, pixel=pixel, times=times, centers=centers,
                    bg_center=bg_center, rk=rk, bgk=bgk, valid=valid, traces=traces,
                    channel_count=c, background_channel=bg_channel, resolved_ranges=resolved)
    out.mkdir(parents=True, exist_ok=True)
    fig, axs = plt.subplots(2, c, figsize=(max(5,4*c), 8), squeeze=False, layout='constrained')
    for ch in range(c):
        display = smooth_display(dff[:, ch], cfg['display_sigma_px'])
        tifffile.imwrite(out/f'C{ch+1}_dff_float32.tif', dff[:, ch], imagej=True,
                         metadata={'axes': 'TYX', 'unit': 'um'}, resolution=(1/pixel[0], 1/pixel[1]))
        tifffile.imwrite(out/f'C{ch+1}_F0.tif', f0[ch])
        palette = channel_value(cfg,'colormap',ch,'jet')
        tifffile.imwrite(out/f'C{ch+1}_dff_{palette}.tif', rgb(display, cfg, ch), photometric='rgb')
        avdisplay = mean(display[average], axis=0)
        tifffile.imwrite(out/f'C{ch+1}_average_dff.tif', avg[ch])
        Image.fromarray(rgb(avdisplay, cfg, ch)).save(out/f'C{ch+1}_average_{palette}.bmp')
        axs[0, ch].imshow(a[:, ch].mean(axis=0), cmap='gray')
        cmap = display_cmap(cfg,ch)
        lo, hi = color_range(cfg, ch)
        im = axs[1, ch].imshow(avdisplay, cmap=cmap, vmin=lo, vmax=hi)
        fig.colorbar(im, ax=axs[1, ch], fraction=.046, pad=.04, label='dF/F0')
        for ax in axs[:, ch]:
            for center, diameter, color in [(bg_center, cfg['background_diameter_um'], 'cyan'),
                                          (centers[ch], cfg['response_diameter_um'], 'white')]:
                ax.add_patch(Ellipse(center, diameter/pixel[0], diameter/pixel[1], fill=False, edgecolor=color))
            ax.axis('off')
        axs[0, ch].set_title(f'C{ch+1}: mean intensity')
        axs[1, ch].set_title(f'C{ch+1}: average dF/F0')
    fig.savefig(out/'ROI_preview.png', dpi=160)
    plt.close(fig)
    fig, ax = plt.subplots(figsize=(10, 5))
    x = times if times is not None else np.arange(1, t+1)
    for ch in range(c):
        ax.plot(x, traces[ch], color=cfg['trace_colors'][ch], label=f'C{ch+1}', marker='.')
    ax.set(xlabel='Time (s)' if times is not None else 'Frame (1-based)', ylabel='Mean pixel dF/F0')
    ax.axhline(0, color='gray', lw=.5)
    ax.legend()
    fig.tight_layout()
    fig.savefig(out/'traces.png', dpi=200)
    fig.savefig(out/'traces.svg')
    plt.close(fig)
    with (out/'traces.csv').open('w', newline='', encoding='utf-8-sig') as f:
        writer = csv.writer(f)
        writer.writerow(['frame', 'time_s']+[f'C{i+1}_mean_pixel_dff' for i in range(c)]+
                        [f'C{i+1}_background' for i in range(c)])
        for i in range(t):
            writer.writerow([i+1, times[i] if times is not None else '']+
                            [v[i] for v in traces]+list(background_values[i]))
    report = {'source': str(path.resolve()), 'shape_TCYX': list(a.shape), 'pixel_size_um_xy': list(pixel),
              'time_s': times.tolist() if times is not None else None, 'metadata': meta, 'settings': cfg,
              'background_center_xy': bg_center, 'response_centers_xy': centers,
              'response_valid_fractions': fractions, 'channel_count': c, 'background_channel': bg_channel,
              'resolved_ranges': resolved,
              'trace_definition': 'mean of pixelwise dF/F0 before display blur',
              'selection_note': 'ROI is optimized on the same data; use fixed/independent ROIs for confirmatory analysis'}
    (out/'analysis.json').write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding='utf-8')
    np.savez_compressed(out/'roi_masks.npz', background=bg,
                        response=np.stack([roi_mask((h,w), rk, p) for p in centers]))
    print(f'Done: {out}', flush=True)
    return out


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('input', nargs='?', type=Path)
    parser.add_argument('--config', type=Path, default=Path(__file__).with_name('settings.json'))
    parser.add_argument('--output', type=Path)
    parser.add_argument('--show', action='store_true')
    args = parser.parse_args()
    if args.input is None:
        import tkinter as tk
        from tkinter import filedialog
        root = tk.Tk(); root.withdraw()
        name = filedialog.askopenfilename(title='Select Nikon ND2', filetypes=[('Nikon ND2', '*.nd2')])
        root.destroy()
        if not name:
            return
        args.input = Path(name)
    cfg = json.loads(args.config.read_text(encoding='utf-8-sig'))
    out = run(args.input, cfg, args.output or args.input.parent/'results'/args.input.stem)
    if args.show:
        import os
        os.startfile(out/'ROI_preview.png')
        os.startfile(out/'traces.png')


if __name__ == '__main__':
    main()
