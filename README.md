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
| One source that switches parts every 20 s and pulls scores from the sheet | `…/#rotate=20&sheet` |
| Controller | `…/#control` |

## Deploy on Render

1. Render → **New → Blueprint** → pick this repository and the branch `overdrive-wildcard-bracket`.
2. Render reads `render.yaml` and creates a free static site. There is nothing to build.
3. Every push to this branch updates the site.

## Use in OBS

1. Add a **Browser Source**, 1920×1080, with the site address. Untick "Local file".
2. Add a **Custom Browser Dock** (Docks → Custom Browser Docks) with the address ending in `#control`.
3. The controller and the overlay share scores through browser storage. OBS can keep docks and browser
   sources apart, and a controller in a normal browser never reaches OBS. If changes don't show on stream,
   use `#sheet` (scores from the Google Sheet) plus `rotate=` or Interact for switching parts.

## Gameplay scene: match updates

`…/#gameplay` is a separate transparent view for the gameplay scene. It checks the sheet every 20 s and pops up
a banner bottom-left when a map is won (score, who leads, match point) or a match ends (who advances, drops,
is eliminated or qualifies for the Major). Source 1920×1160, crop bottom 80; the strip has Test map popup,
Test match popup, Replay last and Check sheet now (via Interact). Refreshing doesn't replay old results.

## Switching parts in a single OBS source

- Add `rotate=N` to the address to alternate Part 1 and Part 2 every N seconds.
- Or set the source to **1920×1160** and crop **80 px** off the bottom (Edit Transform → Crop Bottom 80).
  The strip below the picture has **Part 1**, **Part 2** and **Auto switch** buttons: right-click the
  source → **Interact** to click them. Viewers never see the strip. Keys **1** / **2** work too.
- Both play the slide-in animation and need no controller.

## Controller

- Scores with + / − (best of 5, first to 3), WO for walkover wins, Go live to tag the current match.
- Winners and losers move through the bracket automatically.
- Part 1 / Part 2 on air, or switch automatically every N seconds.
- Pull results from the tournament's Google Sheet once or every 45 s.
- Header, times, seeds, box opacity and an optional fire backdrop.
- Copy backup / Restore backup to move the bracket state between machines.
