# Dont want to read any of this? Watch the video instead:

## [https://youtu.be/iBHTiHVNeNI](https://youtu.be/iBHTiHVNeNI)

---

# Card Centering Studio

A Windows desktop tool for repeatable, manual centering measurements from flatbed-scanner images. Version 1 deliberately measures geometry only; it does not predict grades or make grading-company claims.

Built with Python, PySide6, OpenCV, Pillow, and SQLite.

## What it does

- Imports separate front and back scans (PNG is the primary format).
- Shows each scan in a pannable, zoomable viewer.
- Straightens imperfectly placed scans from two points on any physical card edge.
- Rotates from the original pixels at 1:1 scale on an expanded canvas, so no scan area is cropped.
- Provides eight manually adjustable guides on each side:
  - four solid cyan guides for the physical card edges;
  - four dashed amber guides for the printed-image edges.
- Supports drag placement, direct 0.1 px numeric entry, and keyboard nudging.
- Calculates border distances directly from guide positions in pixels.
- Reports left/right and top/bottom ratios to one decimal place, such as `49.2/50.8`.
- Adds color-coded, plain-English severity bands and explains which direction the print is shifted.
- Reads scanner DPI metadata when present and displays optional millimetre equivalents. DPI never affects the centering ratio.
- Saves independent front L/R, front T/B, back L/R, and back T/B results to SQLite.
- Stores an embedded PNG report with every new saved measurement.
- Provides an interactive history table with report preview/export, rename, delete, and two-copy comparison actions.
- Compares checked copies by worst-axis deviation from 50/50 while keeping the result explicitly separate from grading.
- Exports a high-resolution PNG report with the annotated front and back side by side, plus ratios, pixel distances, optional millimetres, and the plain-English assessment.
- Includes a persistent dark mode, a one-click canvas reset, application branding, and built-in About information.

## Install and run on Windows

Python 3.11 or newer is recommended.

Double-click **Launch Card Centering Studio.bat**. It starts the local environment when it is already installed; on first run it opens PowerShell to create the environment and install the dependencies.

You can also right-click `install_and_run.ps1` and choose **Run with PowerShell**. If PowerShell script execution is restricted, open PowerShell in this folder and run:

```powershell
Set-ExecutionPolicy -Scope Process Bypass
.\install_and_run.ps1
```

Or install manually:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python run_app.py
```

## Measurement workflow

1. Enter a card ID/name. Include a copy identifier when comparing duplicates.
2. Import a front PNG and a back PNG.
3. Before placing guides, choose **Pick 2 points on a card edge**. Click two far-apart points along the same physical edge. The app rotates that edge to the nearest horizontal or vertical axis. You can repeat this or enter a correction angle directly.
4. Zoom in and place the cyan lines at the physical outer card edges.
5. Place the amber lines at the corresponding edges of the inner printed image.
6. Fine-tune a selected guide with the arrow keys:
   - Arrow: 1 px
   - Shift+Arrow: 0.1 px
   - Ctrl+Arrow: 10 px
7. Review the four ratios and save the measurement.
8. Choose **Export report…** (or press **Ctrl+E**) to create a shareable front/back comparison image.
9. Use **Reset canvas** (or **Ctrl+N**) to clear both working scans without changing saved history.

Changing the rotation preserves the current zoom, viewing position, and guide placement by mapping them into the newly rotated canvas. Because the lines remain axis-aligned, give them a quick visual fine-tune after a meaningful angle change. Point-selection mode shows a magenta instruction banner, a crosshair cursor, and a visible marker after the first click. Use **Fit card** after roughly positioning the cyan guides for a crop-like close view; this changes only the view and never removes image data.

### Reading the result

The larger ratio number is the wider border. For example, `45.7/54.3` means the second border is wider and the result is 4.3 percentage points away from perfect 50/50 balance. The app also states the direction the printed image sits.

The color bands are descriptive geometry aids only:

- 50.0–52.0: Very even
- 52.1–55.0: Slight offset
- 55.1–60.0: Noticeable offset
- 60.1–65.0: Strong offset
- Over 65.0: Heavy offset

They are not grading predictions and do not reproduce any grading company's standards.

### Exported report

The PNG report uses the straightened working images rather than screenshots, so viewer zoom and window size do not affect its quality. Each face is cropped loosely around the cyan physical-card guides and includes the cyan outer-edge lines, amber dashed print-edge lines, horizontal and vertical ratios, raw pixel distances, optional DPI-based millimetres, straightening correction, and descriptive severity. Exporting does not create a database record; use **Save measurement** separately when you want the result in history.

Every new saved measurement also embeds this report in SQLite. Click **View report**, double-click a history row, or right-click a row to preview or save it later. Rows created by older app versions remain available, but they cannot have a report retroactively reconstructed when the original guides were not stored.

### Working with saved copies

- Check exactly two rows and choose **Compare checked copies** for a side-by-side data comparison.
- Right-click a row to view or export its report, rename it, compare it with another saved copy, or delete it.
- Renaming also updates the title embedded in its stored report.
- The comparison calls the copy with the smaller worst-axis deviation from 50/50 more evenly centered. This is a transparent geometry comparison, not a card grade.

Use **View → Dark mode** for a persistent low-light theme. **Help → About Card Centering Studio** shows the publisher and licensing summary.

For the most repeatable results, scan copies with the same scanner settings and orientation, zoom in deeply for placement, and use a consistent visual rule for anti-aliased or soft edges.

## Calculation

```text
left   = inner_left - outer_left
right  = outer_right - inner_right
top    = inner_top - outer_top
bottom = outer_bottom - inner_bottom

horizontal = 100 × left/(left+right)  /  100 × right/(left+right)
vertical   = 100 × top/(top+bottom)   /  100 × bottom/(top+bottom)
```

All four calculations use pixel distances. Millimetres are display-only and are computed as `pixels × 25.4 / DPI`.

## Data location

By default, the SQLite file is stored in the Windows application-data location reported in the app status bar. To use a specific file:

```powershell
python run_app.py --database "D:\Card Data\measurements.sqlite3"
```

You can also pre-open images:

```powershell
python run_app.py --front front.png --back back.png
```

## Architecture

- `card_centering/measurement.py` — pure pixel measurement and ratio logic.
- `card_centering/image_processing.py` — OpenCV scan loading, DPI extraction, and the `CardEdgeDetector` protocol reserved for future automatic edge detection.
- `card_centering/viewer.py` — zoom/pan graphics view and constrained guides.
- `card_centering/side_editor.py` — one front/back measurement workspace.
- `card_centering/database.py` — explicit SQLite fields for each face and axis.
- `card_centering/report_export.py` — high-resolution annotated front/back PNG composition.
- `card_centering/dialogs.py` — stored-report preview and saved-copy comparison dialogs.
- `card_centering/theme.py` — light and dark application themes.
- `card_centering/main_window.py` — application workflow and saved-copy comparison.

No automatic detector is implemented in V1. A future OpenCV detector can implement `CardEdgeDetector.detect()` and return the same `GuidePositions` model used by the manual UI.

## Project scope

The current release prioritizes transparent, repeatable measurement over automated interpretation. Planned extensions can include optional OpenCV-assisted edge proposals, reusable guide presets, and structured CSV/JSON export, while keeping manual verification and pixel-based calculations as the source of truth.

Contributions and well-described bug reports are welcome. Please avoid attaching copyrighted card scans or personal SQLite databases to public issues unless you have checked what they contain.

## License

Card Centering Studio is released under the [MIT License](LICENSE). Copyright © 2026 Lambda Core Engineering LLC. The software is provided “as is,” without warranty; see the license text for the complete terms.

## Tests

The calculation and persistence tests use Python's standard-library test runner:

```powershell
python -m unittest discover -v
```

