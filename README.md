# AXR ND2 Analyzer

A Windows desktop tool for semi-automated **1–4 channel Nikon ND2 time-series analysis**. Compute background-corrected ΔF/F₀, inspect response maps, drag circular ROIs, and export traces and quantitative image stacks.

[中文使用说明](README_zh.md)

## Start

1. Install **Python 3.12 or later** from [python.org](https://www.python.org/downloads/windows/), with Tcl/Tk support.
2. Download this repository and extract it to a writable folder.
3. Run `Setup.bat` once to install the dependencies. Then run `Start.bat`.
4. Choose an ND2, set the baseline/response windows, and click **Load / recompute preview**.
5. Review and drag the ROIs, then click **Save reviewed results**.

## Workspace

- **Analysis**: baseline and response windows with independent start/end fields and frames/seconds units, physical ROI diameters, background reference, ROI sharing, and carryover to the next file.
- **Display**: independent channel ranges, color maps, reversal, and trace colors.
- **Advanced**: Gaussian blur, F₀ thresholds, valid-pixel fraction, and optional calibration overrides.
- **Review**: channel response maps and traces in one panel, with white response ROIs and a cyan background ROI. Processing runs in the background with a progress indicator.

The default background/response **diameters are 50/100 µm**, respectively. Seconds use actual ND2 timestamps relative to the first frame. Display settings never change the quantitative ΔF/F₀ data.

## Outputs

Each run creates a separate results directory next to the input by default. Outputs include quantitative float32 TIFF stacks with NaNs, RGB pseudocolor TIFF stacks, averaged response TIFF/BMP images, ROI inspection PNG, trace PNG/SVG, CSV, ROI masks, and a JSON record of the settings and selected frames. The CSV has `2 + 2 × channel_count` columns: frame, time, each channel's mean pixelwise ΔF/F₀, and each channel's background intensity.

## Command line

```powershell
.\.venv\Scripts\python.exe analyze.py "D:\data\recording.nd2" --config settings.json --output "D:\analysis\recording_01"
```

The command refuses to overwrite a non-empty output directory. Without `--output`, it uses `<ND2 directory>/results/<ND2 stem>`.

## Tests

```powershell
.\.venv\Scripts\python.exe -m unittest discover -p "test_*.py" -v
```

Synthetic data cover 1–4 channel reading, export, ROI optimization, timestamp ranges, color reversal, and ROI carryover. Optional real-file tests run only when a local example exists, or when `AXR_TEST_ND2` is set to a compatible four-channel ND2. Raw experimental images and personal paths are not distributed with this repository.

## Interpretation

The primary trace is the mean of **pixelwise** `(F − F₀) / F₀` over valid pixels within the ROI. Auto-selection maximizes the mean response on the selected response window; it does not find negative-response minima. For off responses, choose the ROI manually and set a negative display range. Same-data ROI optimization is exploratory. ROI carryover preserves image coordinates and checks geometry; it does not register moving samples. Multi-Z/multi-position data must be reduced to a single plane/position first.

## Dependencies and attribution

[nd2](https://talleylambert.com/nd2/), NumPy, SciPy, Matplotlib, tifffile, Pillow, and [cmap](https://cmap-docs.readthedocs.io/). Fire color controls are derived from [ImageJ's LutLoader](https://github.com/imagej/ImageJ/blob/master/ij/plugin/LutLoader.java); GreenFireBlue is provided by cmap's ImageJ collection. See [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).
