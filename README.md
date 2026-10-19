# Rush Dash or Crash

A fast-paced, low-graphics, very colourful single-player FPS in a neon toybox. The faster you move, the harder you hit.

> **Made entirely with [Claude Code](https://claude.com/claude-code).** Every line of code, the procedural sound and the design document were written by Claude in conversation with the project owner.
>
> **Work in progress:** updates will keep coming. Expect changes, rough edges and new content.

## The idea

You are a tiny fighter in an arena full of hostile geometric shapes. Slides, dashes, wall-kicks and shotgun-jumps fill the **Rush** meter, and kills in quick succession raise the **Chain** multiplier. As both climb, the game gets louder, brighter and faster. Feedback (sound, particles, score numbers) is modelled on the feel of Balatro, though there are no cards.

See [DESIGN.md](DESIGN.md) for the full design and the running change log.

## Requirements

- Python 3.11 or newer
- [Ursina](https://www.ursinaengine.org/) and NumPy (see `requirements.txt`)

## Run it

```bash
python -m venv .venv
.venv\Scripts\activate        # Windows; on macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
python main.py
```

Sound effects are generated procedurally with NumPy on first run, so there are no audio assets to download.

## Default controls

Controls can be rebound in the menu (ESC).

| Action | Key |
|---|---|
| Move | W A S D |
| Jump / double jump / wall-kick | Space |
| Dash | Left Shift |
| Slide | Left Ctrl or C |
| Fire | Left mouse |
| Scope (Longshot) | Right mouse |
| Katana slash and parry | F |
| Reload | R |
| Weapons | 1-5, mouse wheel |
| Respawn | Backspace |
| Menu / pause | Esc |

## Tests

```bash
python tests/smoke.py
```

## Project layout

| Folder | Contents |
|---|---|
| `main.py` | App setup and scene switching |
| `game/` | Player, weapons, enemies, maps, Rush and Chain |
| `fx/` | Juice, particles, toon-style models, post effects |
| `audio/` | Procedural sound and music |
| `ui/` | HUD, menus, tally screen |
| `data/` | Tuning numbers, controls, settings, progress |
| `tests/` | Smoke tests and screenshot tools |

## License

[MIT](LICENSE)
