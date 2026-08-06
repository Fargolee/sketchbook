# Sketchbook

A page-flipping sketchbook of Singapore, built as one static HTML file. Drag a page and the leaf bends the way paper bends, then drag the brass magnifier across the spread to read the ink up close.

[**View the live site**](https://mengto.com)

![The sketchbook open on the Marina Bay skyline, with the magnifier resting on the ink](assets/sketchbook-preview.jpg)

## Inspiration

Built after seeing [Matthew Yu's](https://x.com/matthewyuart) personal portfolio concept, which he open-sourced at [matthewyuart/personalportfolio](https://github.com/matthewyuart/personalportfolio). That repository is what made this possible rather than a rough approximation of it.

Books and pages are some of the most interesting UIs to explore, and an agent will only give you the basics unless you hand it a solid open-source project to work from. Everything past that came from asking for one behaviour at a time: drag to paginate, then many rounds of fixes for shadows, clipping, alpha masks and turn logic, then a magnifier that has to move out of the way when a page sweeps past it.

## What is inside

- Nine watercolour spreads of Singapore, from Marina Bay Sands to the Botanic Gardens, with an index that jumps to any plate.
- Drag the spread to turn a page, or throw it and let the velocity decide whether the leaf commits or falls back.
- A magnifier that lies on the desk above the paper. Drag it anywhere, and it slides aside when a turning leaf sweeps through it.
- A pointer parallax that leans the book toward the cursor without dragging the magnifier along with it.
- An opening riffle that flicks through the book on load, with directional motion blur on the leaves.
- Paper textures, watercolour washes and botanical ornaments layered behind the page.
- No build step, no dependencies, and no external requests. Fonts and artwork are served from the repository.

## How it is made

**The page turn.** The turning leaf is not a flat panel on a hinge. It is a chain of nested strips whose tangent sweeps through an arc, so the surface curves along its width and the paper bends instead of pivoting like a door. Each strip carries a front and back face with `backface-visibility` doing the flip, plus a shading gradient and a specular wash that track the leaf's angle to the light.

**The magnifier.** The lens holds a second copy of the book, scaled about whichever page point sits under the glass and masked to a circle. That copy lives outside the parallax transform, so leaning the book never drags the glass with it, and the copy fades out as the glass wanders off the paper so you are left looking through plain glass rather than at a sliver of page floating on the desk.

**The artwork.** The spreads were generated with gpt image 2, which is very good at these Singapore sketches. The paper grain, watercolour washes and botanical ornaments are what give the page its personality.

**The type.** Instrument Serif and Newsreader, subset to the characters the page actually uses so the three font files come to 164KB.

Everything lives in [`index.html`](index.html): layout, styles, the page-turn geometry, the loupe, and the interaction state. It is 48KB. The `sketchbook/` folder holds the art and the fonts.

## Run locally

Serve the folder with any static file server, then open the local URL:

```sh
python3 -m http.server 4173
```

Opening `index.html` straight off disk works too, though the fonts load more reliably over http.

## Accessibility and input

The magnifier is hidden on touch devices, where there is no cursor to drag it with, and the book falls back to tap-to-turn. `prefers-reduced-motion` skips the opening riffle and settles page turns without animation.

## Deployment

GitHub Pages builds from `main` through [the Actions workflow](.github/workflows/pages.yml) and serves at [mengto.com](https://mengto.com).

## Credits

- Concept and original open source: [Matthew Yu](https://github.com/matthewyuart/personalportfolio)
- Sketches: gpt image 2
- Built with Claude Code
