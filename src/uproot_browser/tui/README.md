# Help

Welcome to uproot-browser's help!

## Navigation

Use the arrow keys to navigate the tree view. Press `enter` to select a
something to plot. Press `spacebar` to open/close a directory or tree. You can
also use the VIM keys: `j` to move down, `k` to move up, `l` to open a folder,
and `h` to close a folder.

## Plotting

Histograms, rectangular simple data (e.g. TTree's), and jagged arrays can
be plotted. Click on an item or press `enter` to plot. If something can't
be plotted, you'll see a scrollable error traceback. If you think it should
be plottable, feel free to open an issue. 2D plots are not yet supported.

## Themes

You can press `t` to toggle light and dark mode.

## Leaving

You can press `q` to quit. You can also press `d` to quit with a dump of the
current plot and how to get the object being plotted in Python uproot code.

## Exiting the help.

You can press `esc` or `q` to exit this help screen. You can also use `tab` to
switch between the panes in the help screen. You can use `F1` (or `?`) to access
the help again.

# Credits

Uproot browser was created by Henry Schreiner and Aman Goel. It was rewritten
by Elie Svoll and Jose Ayala Garcia to use the modern CSS-based Textual
library.

Uproot browser is made possible by the Scikit-HEP ecosystem, including uproot
and awkward-array for data reading, hist and boost-histogram for computation.
The TUI (terminal user interface) was built using the Textual library.
Text-based plotting is provided by plotext.
