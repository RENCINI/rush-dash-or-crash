"""The game's lettering: a pixel alphabet drawn here, five pixels by seven, set either as 3D toon
blocks or flat with a drop shadow. `Label` stands in for ursina's Text wherever words are shown.

Block letters are extruded: their face, then the same shape stepped back down and to the right
in darker shades for the sides, all inside a dark outline like the rest of the game (fx/toon.py),
so they look solid even on the flat UI camera. Flat letters are squares on a dark rim with a shadow below them, for small print that has
to stay sharp. Glyphs are built white and tinted by the label's colour. A string's mesh is its
glyphs' baked arrays laid side by side, kept in a cache, so a number that changes every frame
costs little. With `letters=True` every glyph is its own entity instead, free to bounce.
"""
from collections import OrderedDict
from math import pi, sin

import numpy as np
from panda3d.core import (ColorAttrib, Geom, GeomNode, GeomTriangles, GeomVertexData, GeomVertexFormat, NodePath,
                          TransparencyAttrib)
from ursina import Entity, Vec3, Vec4, camera
from ursina.scripts.property_generator import generate_properties_for_class

from fx.toon import OUTLINE, fan

CELL = 0.025 / 9            # a pixel of a letter at scale 1: a line as tall as ursina's Text
LINE = 10                   # pixels from one line down to the next
SLANT = 0.6                 # how far a block letter's back sits to the right of and below its face...
EXTRUDE = 3                 # ...in this many steps
SIDE = (0.68, 0.48)         # how bright its sides are, at the face and at the back
RIM = 0.18                  # the dark edge round a letter
SHADOW = 0.4                # how far a flat letter's shadow falls
BLOCK_FROM = 1.2            # labels this big and bigger are set in blocks unless told otherwise
CACHE = 800                 # strings whose meshes are kept
VERTEX = np.dtype([('pos', '<f4', 3), ('col', 'u1', 4)])
MISSING = set()             # characters asked for that the alphabet hasn't got: the tests look

# every glyph as rows from the top, X lit; widths vary, the height is always seven
GLYPHS = {
    'A': ('.XXX.', 'X...X', 'X...X', 'XXXXX', 'X...X', 'X...X', 'X...X'),
    'B': ('XXXX.', 'X...X', 'X...X', 'XXXX.', 'X...X', 'X...X', 'XXXX.'),
    'C': ('.XXX.', 'X...X', 'X....', 'X....', 'X....', 'X...X', '.XXX.'),
    'D': ('XXXX.', 'X...X', 'X...X', 'X...X', 'X...X', 'X...X', 'XXXX.'),
    'E': ('XXXXX', 'X....', 'X....', 'XXXX.', 'X....', 'X....', 'XXXXX'),
    'F': ('XXXXX', 'X....', 'X....', 'XXXX.', 'X....', 'X....', 'X....'),
    'G': ('.XXX.', 'X...X', 'X....', 'X.XXX', 'X...X', 'X...X', '.XXXX'),
    'H': ('X...X', 'X...X', 'X...X', 'XXXXX', 'X...X', 'X...X', 'X...X'),
    'I': ('XXX', '.X.', '.X.', '.X.', '.X.', '.X.', 'XXX'),
    'J': ('..XXX', '...X.', '...X.', '...X.', 'X..X.', 'X..X.', '.XX..'),
    'K': ('X...X', 'X..X.', 'X.X..', 'XX...', 'X.X..', 'X..X.', 'X...X'),
    'L': ('X....', 'X....', 'X....', 'X....', 'X....', 'X....', 'XXXXX'),
    'M': ('X...X', 'XX.XX', 'X.X.X', 'X.X.X', 'X...X', 'X...X', 'X...X'),
    'N': ('X...X', 'X...X', 'XX..X', 'X.X.X', 'X..XX', 'X...X', 'X...X'),
    'O': ('.XXX.', 'X...X', 'X...X', 'X...X', 'X...X', 'X...X', '.XXX.'),
    'P': ('XXXX.', 'X...X', 'X...X', 'XXXX.', 'X....', 'X....', 'X....'),
    'Q': ('.XXX.', 'X...X', 'X...X', 'X...X', 'X.X.X', 'X..X.', '.XX.X'),
    'R': ('XXXX.', 'X...X', 'X...X', 'XXXX.', 'X.X..', 'X..X.', 'X...X'),
    'S': ('.XXXX', 'X....', 'X....', '.XXX.', '....X', '....X', 'XXXX.'),
    'T': ('XXXXX', '..X..', '..X..', '..X..', '..X..', '..X..', '..X..'),
    'U': ('X...X', 'X...X', 'X...X', 'X...X', 'X...X', 'X...X', '.XXX.'),
    'V': ('X...X', 'X...X', 'X...X', 'X...X', 'X...X', '.X.X.', '..X..'),
    'W': ('X...X', 'X...X', 'X...X', 'X.X.X', 'X.X.X', 'X.X.X', '.X.X.'),
    'X': ('X...X', 'X...X', '.X.X.', '..X..', '.X.X.', 'X...X', 'X...X'),
    'Y': ('X...X', 'X...X', '.X.X.', '..X..', '..X..', '..X..', '..X..'),
    'Z': ('XXXXX', '....X', '...X.', '..X..', '.X...', 'X....', 'XXXXX'),
    '0': ('.XXX.', 'X...X', 'X..XX', 'X.X.X', 'XX..X', 'X...X', '.XXX.'),
    '1': ('.X.', 'XX.', '.X.', '.X.', '.X.', '.X.', 'XXX'),
    '2': ('.XXX.', 'X...X', '....X', '...X.', '..X..', '.X...', 'XXXXX'),
    '3': ('XXXX.', '....X', '....X', '.XXX.', '....X', '....X', 'XXXX.'),
    '4': ('...X.', '..XX.', '.X.X.', 'X..X.', 'XXXXX', '...X.', '...X.'),
    '5': ('XXXXX', 'X....', 'XXXX.', '....X', '....X', 'X...X', '.XXX.'),
    '6': ('.XXX.', 'X....', 'X....', 'XXXX.', 'X...X', 'X...X', '.XXX.'),
    '7': ('XXXXX', '....X', '...X.', '..X..', '.X...', '.X...', '.X...'),
    '8': ('.XXX.', 'X...X', 'X...X', '.XXX.', 'X...X', 'X...X', '.XXX.'),
    '9': ('.XXX.', 'X...X', 'X...X', '.XXXX', '....X', '....X', '.XXX.'),
    ' ': ('...', '...', '...', '...', '...', '...', '...'),
    '!': ('X', 'X', 'X', 'X', 'X', '.', 'X'),
    '?': ('.XXX.', 'X...X', '....X', '...X.', '..X..', '.....', '..X..'),
    '.': ('.', '.', '.', '.', '.', '.', 'X'),
    ',': ('..', '..', '..', '..', '..', '.X', 'X.'),
    ':': ('.', 'X', '.', '.', '.', 'X', '.'),
    ';': ('..', '.X', '..', '..', '..', '.X', 'X.'),
    "'": ('X', 'X', '.', '.', '.', '.', '.'),
    '"': ('X.X', 'X.X', '...', '...', '...', '...', '...'),
    '`': ('X.', '.X', '..', '..', '..', '..', '..'),
    '-': ('....', '....', '....', 'XXXX', '....', '....', '....'),
    '+': ('.....', '..X..', '..X..', 'XXXXX', '..X..', '..X..', '.....'),
    '=': ('.....', '.....', 'XXXXX', '.....', 'XXXXX', '.....', '.....'),
    '*': ('.....', 'X.X.X', '.XXX.', 'XXXXX', '.XXX.', 'X.X.X', '.....'),
    '/': ('....X', '....X', '...X.', '..X..', '.X...', 'X....', 'X....'),
    '%': ('XX..X', 'XX..X', '...X.', '..X..', '.X...', 'X..XX', 'X..XX'),
    '#': ('.X.X.', '.X.X.', 'XXXXX', '.X.X.', 'XXXXX', '.X.X.', '.X.X.'),
    '&': ('.XX..', 'X..X.', 'X.X..', '.X...', 'X.X.X', 'X..X.', '.XX.X'),
    '(': ('..X', '.X.', 'X..', 'X..', 'X..', '.X.', '..X'),
    ')': ('X..', '.X.', '..X', '..X', '..X', '.X.', 'X..'),
    '[': ('XX', 'X.', 'X.', 'X.', 'X.', 'X.', 'XX'),
    ']': ('XX', '.X', '.X', '.X', '.X', '.X', 'XX'),
    '{': ('.XX', '.X.', '.X.', 'X..', '.X.', '.X.', '.XX'),
    '}': ('XX.', '.X.', '.X.', '..X', '.X.', '.X.', 'XX.'),
    '<': ('...X', '..X.', '.X..', 'X...', '.X..', '..X.', '...X'),
    '>': ('X...', '.X..', '..X.', '...X', '..X.', '.X..', 'X...'),
    '_': ('.....', '.....', '.....', '.....', '.....', '.....', 'XXXXX'),
    '|': ('X', 'X', 'X', 'X', 'X', 'X', 'X'),
    '~': ('.....', '.....', '.XX.X', 'X.XX.', '.....', '.....', '.....'),
    '^': ('..X..', '.X.X.', 'X...X', '.....', '.....', '.....', '.....'),
    '@': ('.XXX.', 'X...X', 'X.XXX', 'X.X.X', 'X.XXX', 'X....', '.XXXX'),
    '$': ('..X..', '.XXXX', 'X.X..', '.XXX.', '..X.X', 'XXXX.', '..X..'),
}
BOX = ('XXXX', 'X..X', 'X..X', 'X..X', 'X..X', 'X..X', 'XXXX')     # for a character it hasn't got


def rows(char):
    glyph = GLYPHS.get(char.upper())
    if glyph is None:
        MISSING.add(char)
        return BOX
    return glyph


def advance(char):
    return len(rows(char)[0]) + 1


def text_width(line):
    """How many pixels wide a line is."""
    return max(0, sum(advance(c) for c in line) - 1)


# --- meshes ---

_glyphs = {}


def squares(cells, grow=0.0, shift=(0.0, 0.0, 0.0)):
    """One square per cell, facing the camera, `grow` bigger all round and moved by `shift`."""
    out = []
    for i, j in cells:
        x0, y0, x1, y1 = i - grow + shift[0], j - grow + shift[1], i + 1 + grow + shift[0], j + 1 + grow + shift[1]
        out.append(np.array(((x0, y0, shift[2]), (x0, y1, shift[2]), (x1, y1, shift[2]), (x1, y0, shift[2]))))
    return out


def glyph_arrays(char, style):
    """(corners, colours) of one glyph's triangles in pixels, its bottom left at the origin. The
    layers go back to front: the dark rim, then the sides (block) or the shadow (flat), then the
    face."""
    key = (char.upper(), style)
    if key in _glyphs:
        return _glyphs[key]
    glyph = rows(char)
    cells = [(i, 6 - j) for j, row in enumerate(glyph) for i, mark in enumerate(row) if mark != '.']
    dark = (*OUTLINE, 1)
    layers = []
    if style == 'block':
        # the extrusion is the face again, stepped back down and to the right, darker the deeper
        steps = [(k / EXTRUDE, SLANT * k / EXTRUDE) for k in range(1, EXTRUDE + 1)]
        for k, step in steps:
            layers.append((squares(cells, RIM, (step, -step, 0.6 + 0.1 * k)), dark))
        layers.append((squares(cells, RIM, (0, 0, 0.6)), dark))
        for k, step in reversed(steps):
            side = SIDE[0] + (SIDE[1] - SIDE[0]) * k
            layers.append((squares(cells, 0, (step, -step, 0.1 + 0.3 * k)), (side, side, side, 1)))
    else:
        layers.append((squares(cells, RIM, (SHADOW, -SHADOW, 0.6)), dark))
        layers.append((squares(cells, RIM, (0, 0, 0.5)), dark))
    layers.append((squares(cells), (1, 1, 1, 1)))
    v, c = [], []
    for quads, tint in layers:
        for corners in quads:
            triangles = fan(corners)
            v += triangles
            c += [tint] * len(triangles)
    arrays = (np.array(v, np.float32).reshape(-1, 3), (np.array(c, np.float32).reshape(-1, 4) * 255).astype(np.uint8))
    _glyphs[key] = arrays
    return arrays


def layout(text, origin):
    """[(char, x, y), ...]: each glyph's bottom left in pixels, every line placed by `origin`
    the way ursina's Text places it, and the whole block's width and height."""
    lines = text.split('\n')
    height = len(lines) * LINE - (LINE - 7)
    widest = max(text_width(line) for line in lines)
    top = height * (0.5 - origin[1])
    placed = []
    for n, line in enumerate(lines):
        x = -text_width(line) * (origin[0] + 0.5)
        y = top - n * LINE - 7
        for char in line:
            placed.append((char, x, y))
            x += advance(char)
    return placed, widest, height


def make_geom(corners, colours):
    data = GeomVertexData('label', GeomVertexFormat.getV3c4(), Geom.UHStatic)
    n = len(corners)
    data.uncleanSetNumRows(n)
    if n:
        buffer = np.zeros(n, VERTEX)
        buffer['pos'] = corners
        buffer['col'] = colours
        data.modifyArray(0).modifyHandle().copyDataFrom(buffer.tobytes())
    triangles = GeomTriangles(Geom.UHStatic)
    if n:
        triangles.addConsecutiveVertices(0, n)
    geom = Geom(data)
    geom.addPrimitive(triangles)
    return geom


_strings = OrderedDict()


def string_geom(text, style, origin):
    key = (text, style, origin[0], origin[1])
    geom = _strings.get(key)
    if geom is not None:
        _strings.move_to_end(key)
        return geom
    placed, _, _ = layout(text, origin)
    parts = [(glyph_arrays(char, style), x, y) for char, x, y in placed]
    if parts:
        corners = np.concatenate([v + np.array((x, y, 0), np.float32) for (v, _), x, y in parts]) * CELL
        colours = np.concatenate([c for (_, c), _, _ in parts])
    else:
        corners, colours = np.zeros((0, 3), np.float32), np.zeros((0, 4), np.uint8)
    geom = make_geom(corners.astype(np.float32), colours)
    _strings[key] = geom
    if len(_strings) > CACHE:
        _strings.popitem(last=False)
    return geom


def node(geom):
    holder = GeomNode('label')
    holder.addGeom(geom)
    path = NodePath(holder)
    path.setAttrib(ColorAttrib.makeVertex(), 10)
    path.setTransparency(TransparencyAttrib.MAlpha)
    return path


@generate_properties_for_class()
class Label(Entity):
    """Words in the game's own letters, made like ursina's Text: `text`, `origin`, `scale`, `color`
    and line breaks mean what they mean there. `style` is 'block' or 'flat', chosen by size if
    not given. With `letters=True` each glyph is an entity of its own in `glyphs`, each with its
    resting place in `home`, for `drop_in`, `wave` and the like to move."""

    def __init__(self, text='', style=None, letters=False, origin=(-0.5, 0), parent=camera.ui, **kwargs):
        self._ready = False
        self._text = None
        self._origin = tuple(origin)
        self._colour = Vec4(1, 1, 1, 1)
        self.body = None
        self.glyphs = []
        self.home = []
        self.extent = (0, 0)
        scale = kwargs.get('scale', 1)
        size = scale if isinstance(scale, (int, float)) else scale[1]
        self._style = style or ('block' if size >= BLOCK_FROM else 'flat')
        self.letters = letters
        # words never update themselves, so the engine is told to skip them each frame: with a few
        # hundred on the HUD and the menus, checking them all costs more than drawing them
        kwargs.setdefault('ignore', True)
        super().__init__(parent=parent, **kwargs)
        self._origin = tuple(origin)
        self._ready = True
        self.text = text

    # --- ursina's properties ---

    def text_getter(self):
        return self._text or ''

    def text_setter(self, value):
        value = str(value)
        if value == self._text:
            return
        self._text = value
        if self._ready:
            self.rebuild()

    def origin_getter(self):
        return getattr(self, '_origin', (-0.5, 0))

    def origin_setter(self, value):
        value = (value[0], value[1])
        if value == getattr(self, '_origin', None):
            return
        self._origin = value
        if getattr(self, '_ready', False):
            self.rebuild()

    def style_getter(self):
        return getattr(self, '_style', 'flat')

    def style_setter(self, value):
        if value == getattr(self, '_style', None):
            return
        self._style = value
        if getattr(self, '_ready', False):
            for glyph in self.glyphs:
                glyph.char = None
            self.rebuild()

    def color_getter(self):
        return getattr(self, '_colour', Vec4(1, 1, 1, 1))

    def color_setter(self, value):
        if not isinstance(value, Vec4):
            value = Vec4(value[0], value[1], value[2], value[3] if len(value) > 3 else 1)
        self._colour = value
        self.setColorScale(value)

    def width_getter(self):
        """How wide it is on its parent, as ursina's Text.width."""
        return self.extent[0] * CELL * self.scale_x

    # --- building ---

    def rebuild(self):
        text, origin = self._text or '', self._origin
        if not self.letters:
            if self.body is not None:
                self.body.removeNode()
            self.body = node(string_geom(text, self.style, origin))
            self.body.reparentTo(self)
            _, width, height = layout(text, origin)
            self.extent = (width, height)
            return
        placed, width, height = layout(text, origin)
        self.extent = (width, height)
        shown = [(char, x, y) for char, x, y in placed if char != ' ']
        while len(self.glyphs) < len(shown):
            self.glyphs.append(Entity(parent=self, ignore=True))
        self.home = []
        for glyph, (char, x, y) in zip(self.glyphs, shown):
            w = len(rows(char)[0])
            if getattr(glyph, 'char', None) != char:
                # not the entity's model: ursina would cut it off from the label's colour
                if getattr(glyph, 'body', None) is not None:
                    glyph.body.removeNode()
                glyph.body = node(string_geom(char, self.style, (0, 0)))
                glyph.body.reparentTo(glyph)
                glyph.char = char
            # each glyph sits round its own middle, so it can squash and turn about it
            glyph.position = ((x + w / 2) * CELL, (y + 3.5) * CELL, 0)
            glyph.scale = 1
            glyph.rotation_z = 0
            glyph.enabled = True
            self.home.append(glyph.position)
        for glyph in self.glyphs[len(shown):]:
            glyph.enabled = False

    def points(self):
        """Where its letters are on the screen (in camera.ui), for pixels to fly from."""
        if self.letters:
            return [glyph.getPos(camera.ui) for glyph in self.glyphs if glyph.enabled]
        placed, _, _ = layout(self._text or '', self._origin)
        return [camera.ui.getRelativePoint(self, Vec3((x + 2.5) * CELL, (y + 3.5) * CELL, 0))
                for char, x, y in placed if char != ' ']

    # --- moving the letters (letters=True) ---

    def settle(self):
        for glyph, home in zip(self.glyphs, self.home):
            glyph.position = home
            glyph.scale = 1
            glyph.rotation_z = 0

    def drop_in(self, t, each=0.035, fall=0.16, height=9.0):
        """Letters falling into place one after another, squashing as they land; `t` seconds in."""
        for i, (glyph, home) in enumerate(zip(self.glyphs, self.home)):
            u = min(max((t - i * each) / fall, 0.0), 1.0)
            glyph.enabled = u > 0
            land = sin(pi * min(max((t - i * each - fall) / 0.14, 0.0), 1.0))
            glyph.position = (home[0], home[1] + (1 - u) ** 2 * height * CELL, 0)
            glyph.scale = (1 + 0.3 * land, 1 - 0.25 * land, 1)
            glyph.rotation_z = (1 - u) * (12 if i % 2 else -12)

    def wave(self, t, height=1.2, speed=8.0, spread=0.55):
        """A ripple running along the letters."""
        for i, (glyph, home) in enumerate(zip(self.glyphs, self.home)):
            glyph.position = (home[0], home[1] + sin(t * speed - i * spread) * height * CELL, 0)

    def jiggle(self, t, amount=1.0, speed=30.0):
        """Every letter shaking on its own, for something urgent."""
        for i, (glyph, home) in enumerate(zip(self.glyphs, self.home)):
            glyph.position = (home[0] + sin(t * speed + i * 1.7) * amount * CELL,
                              home[1] + sin(t * speed * 1.3 + i * 2.3) * amount * CELL, 0)
            glyph.rotation_z = sin(t * speed * 0.7 + i) * 6 * amount
