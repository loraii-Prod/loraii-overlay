# OverDrive Wildcard 2026: bracket overlay

A 1920×1080 transparent bracket overlay for OBS with a controller, in a single file (`index.html`).
This branch only holds the bracket. It shares no files with the loraii overlays on `main`.

- **Part 1:** upper bracket (Round 1, quarter-finals, upper qualifiers)
- **Part 2:** lower bracket (lower rounds 2–4, lower qualifiers)

## Addresses

| What | Address |
|---|---|
| Overlay, shows the part that is on air | `https://<site>.onrender.com/` |
| Overlay pinned to Part 1 or Part 2 | `…/#part1`, `…/#part2` |
| Controller | `…/#control` |

## Deploy on Render

1. Render → **New → Blueprint** → pick this repository and the branch `overdrive-wildcard-bracket`.
2. Render reads `render.yaml` and creates a free static site. There is nothing to build.
3. Every push to this branch updates the site.

## Use in OBS

1. Add a **Browser Source**, 1920×1080, with the site address. Untick "Local file".
2. Add a **Custom Browser Dock** (Docks → Custom Browser Docks) with the address ending in `#control`.
3. Overlay and dock share storage inside OBS, so score changes reach the stream within a second.
   A controller opened in a normal browser does **not** reach OBS. Use the dock.

## Controller

- Scores with + / − (best of 5, first to 3), WO for walkover wins, Go live to tag the current match.
- Winners and losers move through the bracket automatically.
- Part 1 / Part 2 on air, or switch automatically every N seconds.
- Pull results from the tournament's Google Sheet once or every 45 s.
- Header, times, seeds, box opacity and an optional fire backdrop.
- Copy backup / Restore backup to move the bracket state between machines.
