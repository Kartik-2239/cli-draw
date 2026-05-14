# cli-draw (Made with [lightcode](https://github.com/Kartik-2239/lightcode))

A small terminal drawing tool with mouse support.

![cli-draw demo](assets/cli-draw.gif)
## Install

Clone the repo:

```bash
git clone https://github.com/Kartik-2239/cli-draw.git
cd cli-draw
```

Install with `uv`:

```bash
uv sync
```

Run it:

```bash
uv run cli-draw
```

## Open Or Save A File

Open an existing drawing:

```bash
uv run cli-draw artwork.txt
```

Set the save path:

```bash
uv run cli-draw --save output.txt
```

Open a file and save back to another path:

```bash
uv run cli-draw artwork.txt --save output.txt
```

## Controls

- Left click: draw
- Left click + drag: draw continuously
- `0` to `7`: change color
- `b`: change brush character
- `c`: clear
- `u`: undo
- `e`: eraser
- `s`: save
- `y`: copy ANSI-colored output to clipboard
- `q` or `Esc`: quit

## Notes

- Files saved by the app keep ANSI colors.
- If mouse drag does not work, use a terminal with mouse reporting enabled.

## Config

The app stores config here:

```bash
~/.cli-draw/config.json
```

It is created automatically the first time you run `cli-draw`.

Example:

```json
{
  "colors": [
    { "id": 0, "name": "black", "hex": "#000000" },
    { "id": 1, "name": "red", "hex": "#FF0000" },
    { "id": 2, "name": "green", "hex": "#00FF00" },
    { "id": 3, "name": "yellow", "hex": "#FFFF00" },
    { "id": 4, "name": "blue", "hex": "#0000FF" },
    { "id": 5, "name": "magenta", "hex": "#FF00FF" },
    { "id": 6, "name": "cyan", "hex": "#00FFFF" },
    { "id": 7, "name": "white", "hex": "#FFFFFF" }
  ]
}
```

You can change:
- `colors`: the 8 colors used by keys `0` to `7`

Color values should be hex strings like `#FF0000`.
