"""The green rule: neon green means "this can be parried", so nothing else may be painted in it.
`offenders()` lists every colour constant, pixel palette, weapon paint and menu paint that falls in
the neon range and is not one of the parry colours themselves. Run on its own it prints them."""
import colorsys
import importlib
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

MODULES = ('game.foes.base', 'game.foes.astronauts', 'game.foes.crocodiles', 'game.foes.cave', 'game.foes.snipers',
           'game.maps.arena', 'game.maps.blender', 'game.maps.jungle', 'game.maps.cave', 'game.pickups', 'game.clouds',
           'game.heart', 'game.beacon', 'game.katana', 'game.weapons', 'game.variants', 'game.body', 'ui.hud',
           'ui.health', 'ui.menus', 'ui.shop', 'ui.score', 'ui.tally', 'fx.blast', 'fx.particles')
PARRY = {'NEON', 'GREEN', 'PARRY_GREEN', 'PARRY'}      # the parry colours: these are meant to be green
PARRY_LOOKS = {'neon', 'mint', 'rush'}                  # pixel looks for parries, heals and the rainbow
HUD_ONLY = {'BAR_HUES'}                                 # the speed bar's rainbow is on the HUD, not in the arena


def neon(r, g, b):
    hue, saturation, value = colorsys.rgb_to_hsv(r, g, b)
    return 85 <= hue * 360 <= 150 and saturation >= 0.55 and value >= 0.6


def offenders():
    from ursina import color
    found = []
    for name in MODULES:
        module = importlib.import_module(name)
        for key, value in vars(module).items():
            if key in PARRY or key in HUD_ONLY or key.startswith('_'):
                continue
            if isinstance(value, color.Color) or (isinstance(value, tuple) and len(value) in (3, 4)
                                                  and all(isinstance(c, (int, float)) for c in value)
                                                  and all(0 <= c <= 1 for c in value)):
                if neon(value[0], value[1], value[2]):
                    found.append(f'{name}.{key}')
    from fx.pixels import PALETTES
    found += [f'pixels {look}' for look, steps in PALETTES.items()
              if look not in PARRY_LOOKS and any(neon(*step) for step in steps)]
    from game.weapons import SLOTS
    from game.variants import VARIANTS
    for kind in (*SLOTS, *VARIANTS.values()):
        for attribute in ('hue', 'accent_hue'):
            if 85 <= getattr(kind, attribute) <= 150:
                found.append(f'{kind.__name__}.{attribute}')
    from game.maps.arena import gate_hue     # the boost gates and the cave's great crystal cycle through it
    if any(85 <= gate_hue(t / 7) <= 150 for t in range(700)):
        found.append('gate_hue')
    from ui.menus import PAINTS
    found += [f'paint {label}' for hue, label in PAINTS if hue is not None and 85 <= hue <= 150]
    return found


if __name__ == '__main__':
    from ursina import Ursina
    Ursina(window_type='offscreen')
    print(offenders() or 'nothing green but what can be parried')
