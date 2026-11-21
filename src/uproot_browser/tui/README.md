# Help

Welcome to uproot-browser's help!

## Navigation

Use the arrow keys to navigate the tree view. Press `enter` to select an
object to plot. Press `spacebar` to open/close a directory or tree. You can
also use the VIM keys: `j` to move down, `k` to move up, `l` to open a folder,
and `h` to close a folder.

Type a positive count (up to four digits) before `down`, `up`, `j`, or `k` to
move that many visible rows. For example, `12j` moves down twelve rows.
Movement stops at the first or last visible row. Press `enter` to plot the
highlighted object.

The pending count appears as `Move: 12` in a separate row above the footer.
The row disappears after a move, another key, or focus leaving the tree.
Scrolling keeps two rows visible above and below the cursor when space permits.

Press `/` to open a fuzzy finder: start typing a branch or field name and the
list narrows as you type (`fzf`-style). Use the arrow keys to pick a match and
press `enter` to jump to it in the tree (plotting it if it's plottable), or
`esc` to cancel.

You can also open the command palette with `ctrl-p` or the icon at the top
left. It has commands to show this help, change the theme, write out an SVG,
or quit the program.

## Plotting

Histograms, rectangular simple data (e.g. TTree's), and jagged arrays can
be plotted. Click on an item or press `enter` to plot. The tree shows items
that cannot be plotted with dim labels; selecting one shows a notification,
and the current plot stays. An item that fails to load or draw shows a
scrollable error traceback. An item with no finite values shows a
notification. If you think an item should be plottable, open an issue. 2D histograms draw as heatmaps
(text mode needs plotext 6 or newer; `--image` mode always supports them).

A slow operation (a remote file that opens, a directory that lists, a plot
that reads data) shows the logo and a progress bar in place of the plot.

To plot two numeric branches or fields against each other, press `m` on the
first one (the x axis) to mark it, then press `m` on the second one (the y
axis). The pair is filled into a 2D histogram, and the tree labels the two
items with `x:` and `y:`. A per-entry value pairs with each value of a jagged
branch from the same entry. Press `m` on a marked item to clear the marks.
The footer shows `m` dimmed when the cursor item is not numeric.
Shift+click plots the item at the cursor (x) against the clicked item (y).

Press `e` to open the expression input, and `esc` to close it. The input is
in the plot window, so `e` is dimmed in the footer until an item is plotted. Type an
expression and press `enter` to apply it. The expression sees `h`, the default
histogram, and `tree`, the containing TTree or RNTuple when available. Use the
normal uproot API to read branches, for example `tree["branch"].array()`.
The modules `ak`, `np`, and `hist` are also available. A `hist.Hist` result is
drawn as is; an array result is flattened, filtered to finite values, and
histogrammed with the default bin count. For example, a cut:

```python
tree["fTracks.fPx"].array()[tree["fTracks.fPy"].array() < 0]
```

Invalid expressions and cuts with no finite results show a notification while
keeping the selection and input available for correction. Clear the expression
and apply it to restore the default histogram.

## Panels

The panel on the left can be hidden or shown with `b`. It has `Tree` and `Info`
tabs. The panel on the right can be hidden or shown with `t`. It has the axis
ranges, the image scale (with `--image`), and the theme selector. Press `esc`
in the right panel to go back to the tree. Drag the bar next to a panel to
resize it.


## Leaving

Press `q` to quit. The `esc` key does not quit; it closes the entry box,
leaves the right panel, and closes dialogs. Press `d` to quit with a dump of
the current plot and standalone Python code (uproot, hist, and plotext or
matplotlib) that reproduces it.

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
