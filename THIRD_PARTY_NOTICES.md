# Third-party components

Dependencies are installed separately through pip and retain their respective licenses. Their source code and license information are available from their official projects:

- nd2: https://github.com/tlambert03/nd2
- NumPy: https://github.com/numpy/numpy
- SciPy: https://github.com/scipy/scipy
- Matplotlib: https://github.com/matplotlib/matplotlib
- tifffile: https://github.com/cgohlke/tifffile
- Pillow: https://github.com/python-pillow/Pillow
- cmap: https://github.com/pyapp-kit/cmap
- Python / Tcl / Tk: https://www.python.org/ and https://www.tcl-lang.org/

The Fire control-point arrays and their interpolation convention in `analyze.py` come from the ImageJ `ij/plugin/LutLoader.java` implementation:
https://github.com/imagej/ImageJ/blob/master/ij/plugin/LutLoader.java

GreenFireBlue is loaded using cmap's `imagej:GreenFireBlue` definition. Other display palettes come from Matplotlib. Tcl/Tk runtime files and Python virtual environments from the local development machine are excluded from the repository.
