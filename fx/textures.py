"""Small pixel-art tiles laid over big surfaces by the toon shader (its `pattern` input, see
fx/shaders.py): deck plating with rivets, hull panels, grass, earth, rock in layers, leaves, and
cave rock run through with crystal. Each is 32 by 32, drawn here with numpy and shown with no
smoothing, so its pixels stay square. Grey 0.5 changes nothing; darker and lighter shade the
surface, in a few hard steps, never a blur."""
from random import Random

import numpy as np
from PIL import Image
from ursina import Texture

SIZE = 32
_made = {}


def plate(rng):
    """Deck plating: a seam round each plate, a rivet in each corner, two tread lines."""
    t = np.full((SIZE, SIZE), 0.5)
    t[0, :] = t[:, 0] = 0.28
    t[1, :] = t[:, 1] = 0.62
    for y, x in ((4, 4), (4, 27), (27, 4), (27, 27)):
        t[y - 1:y + 2, x - 1:x + 2] = 0.66
        t[y + 1, x - 1:x + 2] = 0.36
    for y in (12, 20):
        t[y, 8:24] = 0.42
        t[y + 1, 8:24] = 0.56
    return t


def panel(rng):
    """Hull panels: a seam down the middle and across, and a row of rivets under the top."""
    t = np.full((SIZE, SIZE), 0.5)
    t[:, 0] = t[0, :] = 0.3
    t[:, 16] = 0.36
    t[:, 17] = 0.6
    for x in range(3, SIZE, 6):
        t[3, x] = 0.68
        t[4, x] = 0.38
    return t


def grass(rng):
    """Tufts: short upright blades, lighter at the tip, scattered."""
    t = np.full((SIZE, SIZE), 0.5)
    for _ in range(46):
        x, y = rng.randrange(SIZE), rng.randrange(3, SIZE)
        tall = rng.choice((2, 3, 3, 4))
        for k in range(tall):
            t[(y - k) % SIZE, x] = 0.6 if k == tall - 1 else 0.42
    return t


def dirt(rng):
    """Earth: pebbles, each a lit top over a shadowed bottom."""
    t = np.full((SIZE, SIZE), 0.5)
    for _ in range(18):
        x, y = rng.randrange(SIZE), rng.randrange(SIZE)
        w = rng.choice((1, 2, 2, 3))
        t[y % SIZE, x:x + w] = 0.64
        t[(y + 1) % SIZE, x:x + w] = 0.36
    return t


def strata(rng):
    """Rock laid down in layers: dark cracks along the beds, a few broken across."""
    t = np.full((SIZE, SIZE), 0.5)
    y = 0
    while y < SIZE:
        t[y, :] = 0.34
        if y + 1 < SIZE:
            t[y + 1, :] = 0.58
        for _ in range(2):
            x = rng.randrange(SIZE)
            t[y:min(y + rng.randrange(3, 7), SIZE), x] = 0.38
        y += rng.randrange(5, 9)
    return t


def leaves(rng):
    """Leaves: overlapping ovals, a lit edge on top and a shadow under."""
    t = np.full((SIZE, SIZE), 0.5)
    for _ in range(14):
        cx, cy = rng.randrange(SIZE), rng.randrange(SIZE)
        for dx in range(-3, 4):
            t[cy % SIZE, (cx + dx) % SIZE] = 0.56
            t[(cy - 1) % SIZE, (cx + dx) % SIZE] = 0.64 if abs(dx) < 3 else 0.5
            t[(cy + 1) % SIZE, (cx + dx) % SIZE] = 0.38
    return t


def veins(rng):
    """Cave rock: cracks wandering across it, with bright flecks of crystal in them."""
    t = np.full((SIZE, SIZE), 0.5)
    for _ in range(4):
        x, y = rng.randrange(SIZE), rng.randrange(SIZE)
        for _ in range(26):
            t[y % SIZE, x % SIZE] = 0.32
            if rng.random() < 0.12:
                t[(y - 1) % SIZE, x % SIZE] = 0.74
            x += rng.choice((1, 1, 0))
            y += rng.choice((-1, 0, 1))
    return t


MAKERS = {'plate': plate, 'panel': panel, 'grass': grass, 'dirt': dirt, 'strata': strata, 'leaves': leaves,
          'veins': veins}


def tile(name):
    """The tile `name` as a texture, drawn the first time it is asked for."""
    if name not in _made:
        values = MAKERS[name](Random(name))
        grey = (np.clip(values, 0, 1) * 255).astype(np.uint8)
        image = Image.fromarray(np.dstack([grey, grey, grey, np.full_like(grey, 255)]), 'RGBA')
        _made[name] = Texture(image, filtering=None)
    return _made[name]
