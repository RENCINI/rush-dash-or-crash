"""Cartoon solids: flat cel-shaded faces inside a dark outline, baked into one mesh.

A solid is a list of convex faces, each a (corners, normal) pair. `build` turns any number
of coloured solids into a single mesh, so a whole gun body costs one scene object.
Axes are Ursina's: x right, y up, z forward.
"""
from math import cos, pi, radians, sin

import numpy as np
from ursina import Mesh

OUTLINE = (0.08, 0.07, 0.15)
OUTLINE_WIDTH = 0.008
LIGHT = np.array((-0.3, 0.85, -0.43))
SHADE_STEP = 0.075      # shading snaps to bands instead of blending


def shade(normal):
    lit = np.clip((float(np.dot(normal, LIGHT)) + 0.6) / 1.45, 0, 1)
    return round((0.55 + 0.45 * lit) / SHADE_STEP) * SHADE_STEP


def solid(polygons):
    """Give each polygon an outward normal and a matching winding. The shape must be convex."""
    polygons = [np.array(p, float) for p in polygons]
    middle = np.mean(np.concatenate(polygons), axis=0)
    faces = []
    for corners in polygons:
        normal = np.cross(corners[1] - corners[0], corners[2] - corners[0])
        normal /= np.linalg.norm(normal)
        if np.dot(normal, corners.mean(axis=0) - middle) < 0:
            corners, normal = corners[::-1], -normal
        faces.append((corners, normal))
    return faces


def box(size, at=(0, 0, 0)):
    """size is (width, height, length); `at` is the centre."""
    x, y, z = (s / 2 for s in size)
    c = np.array([(i, j, k) for i in (-x, x) for j in (-y, y) for k in (-z, z)]) + np.array(at, float)
    return solid([c[[0, 1, 3, 2]], c[[4, 5, 7, 6]], c[[0, 1, 5, 4]], c[[2, 3, 7, 6]], c[[0, 2, 6, 4]],
                  c[[1, 3, 7, 5]]])


def barrel(radius, z0, z1, x=0.0, y=0.0, sides=10, end_radius=None):
    """A tube along z from z0 to z1, optionally tapering to `end_radius`."""
    end_radius = radius if end_radius is None else end_radius
    angles = [2 * pi * (i + 0.5) / sides for i in range(sides)]
    back = [(x + sin(a) * radius, y + cos(a) * radius, z0) for a in angles]
    front = [(x + sin(a) * end_radius, y + cos(a) * end_radius, z1) for a in angles]
    sides_ = [(back[i], back[i - 1], front[i - 1], front[i]) for i in range(sides)]
    return solid([back, front] + sides_)


def slab(profile, width, x=0.0):
    """A side-view outline, given as (z, y) points, extruded sideways to `width`."""
    left = [(x - width / 2, py, pz) for pz, py in profile]
    right = [(x + width / 2, py, pz) for pz, py in profile]
    n = len(profile)
    edges = [(left[i], left[i - 1], right[i - 1], right[i]) for i in range(n)]
    return solid([left, right] + edges)


def plate(profile, depth, z=0.0):
    """A front-view outline, given as (x, y) points, extruded back to `depth`."""
    front = [(px, py, z - depth / 2) for px, py in profile]
    back = [(px, py, z + depth / 2) for px, py in profile]
    n = len(profile)
    edges = [(front[i], front[i - 1], back[i - 1], back[i]) for i in range(n)]
    return solid([front, back] + edges)


def heart(depth, z=0.0):
    """A heart from the front, about 2 tall and 2.1 wide round the origin, extruded to `depth`:
    two round lobes over a point. Three solids, each convex, for `build` to outline as one."""
    lobes = [plate(disc(0.56, (side * 0.48, 0.3), 16), depth, z) for side in (-1, 1)]
    return lobes + [plate([(-1.02, 0.26), (1.02, 0.26), (0.0, -1.02)], depth, z)]


def ball(radius, at=(0.0, 0.0, 0.0), squash=(1.0, 1.0, 1.0), rings=5, sides=10, dome=False):
    """A faceted ball, `squash` stretching it along x, y and z. With `dome` only its top half,
    closed flat at the middle."""
    sx, sy, sz = (radius * s for s in squash)
    ax, ay, az = at

    def point(lat, lon):
        return (ax + sx * cos(lat) * sin(lon), ay + sy * sin(lat), az + sz * cos(lat) * cos(lon))

    lons = [2 * pi * (j + 0.5) / sides for j in range(sides)]
    if dome:
        k = rings // 2 + 1
        lats = [pi / 2 * i / k for i in range(k)]
    else:
        lats = [-pi / 2 + pi * i / rings for i in range(1, rings)]
    rows = [[point(lat, lon) for lon in lons] for lat in lats]
    top = (ax, ay + sy, az)
    faces = [[top, rows[-1][j - 1], rows[-1][j]] for j in range(sides)]
    faces += [[a[j - 1], a[j], b[j], b[j - 1]] for a, b in zip(rows, rows[1:]) for j in range(sides)]
    if dome:
        faces.append(rows[0])
    else:
        bottom = (ax, ay - sy, az)
        faces += [[bottom, rows[0][j], rows[0][j - 1]] for j in range(sides)]
    return solid(faces)


def loft(rings):
    """A convex solid through closed rings of (x, y, z) points, each with as many points as the
    first; the last may be a single point, for a tip."""
    faces = [rings[0]]
    for a, b in zip(rings, rings[1:]):
        n = len(a)
        if len(b) == 1:
            faces += [[a[i - 1], a[i], b[0]] for i in range(n)]
        else:
            faces += [[a[i - 1], a[i], b[i], b[i - 1]] for i in range(n)]
    if len(rings[-1]) > 1:
        faces.append(rings[-1])
    return solid(faces)


def disc(radius, at=(0.0, 0.0), steps=14):
    """A circle's outline as (x, y) points, for `plate`."""
    return [(at[0] + radius * cos(2 * pi * i / steps), at[1] + radius * sin(2 * pi * i / steps)) for i in range(steps)]


def blocks(cells, depth=1.0):
    """Unit cubes on a grid, given as (column, row) cells, fused into one solid. Faces between
    neighbours are left out, so the outline runs round the whole shape; it need not be convex."""
    cells = set(cells)
    faces = []
    for i, j in cells:
        for corners, normal in box((1, 1, depth), (i + 0.5, j + 0.5, 0)):
            if normal[2] or (i + round(normal[0]), j + round(normal[1])) not in cells:
                faces.append((corners, normal))
    return faces


def placed(faces, at=(0, 0, 0), yaw=0, pitch=0):
    """The same solid tilted by `pitch`, turned by `yaw` (degrees, as rotation_x and rotation_y)
    and moved to `at`. Shading is baked in, so fixed scenery is placed here, not on its entity."""
    y, p = radians(yaw), radians(pitch)
    turn = (np.array(((cos(y), 0, sin(y)), (0, 1, 0), (-sin(y), 0, cos(y))))
            @ np.array(((1, 0, 0), (0, cos(p), -sin(p)), (0, sin(p), cos(p)))))
    at = np.array((at[0], at[1], at[2]), float)
    return [(corners @ turn.T + at, normal @ turn.T) for corners, normal in faces]


def swollen(faces, amount):
    """The same solid with every face pushed out by `amount`, corners kept sharp."""
    normals = {}
    for corners, normal in faces:
        for corner in corners:
            normals.setdefault(tuple(np.round(corner, 5)), []).append(normal)
    moved = {}
    for key, touching in normals.items():
        touching = np.unique(np.round(touching, 4), axis=0)
        push = np.linalg.lstsq(touching, np.full(len(touching), amount), rcond=None)[0]
        moved[key] = np.array(key) + push
    return [(np.array([moved[tuple(np.round(c, 5))] for c in corners]), normal) for corners, normal in faces]


def build(parts, outline=OUTLINE_WIDTH):
    """parts is [(solid, colour), ...]. Returns one mesh: shaded faces plus the outline hull."""
    vertices, colours = bake(parts, outline)
    return Mesh(vertices=vertices, colors=colours, mode='triangle', static=True)


def bake(parts, outline=OUTLINE_WIDTH, keep=None):
    """What `build` makes, as lists of triangle corners and their colours. `keep`, if given,
    picks which shaded faces to draw by their normal; the outline hull is always whole."""
    vertices, colours = [], []

    def add(corners, tint, inside_out):
        # Ursina's axes are left-handed, so faces seen from outside are wound clockwise
        order = corners if inside_out else corners[::-1]
        for i in range(1, len(order) - 1):
            vertices.extend((tuple(order[0]), tuple(order[i]), tuple(order[i + 1])))
            colours.extend((tint, tint, tint))

    for faces, colour in parts:
        for corners, normal in faces:
            if keep is None or keep(normal):
                s = shade(normal)
                add(corners, (colour[0] * s, colour[1] * s, colour[2] * s, 1), False)
        if outline:
            # the hull is drawn inside out, so only the rim around the solid shows
            for corners, _ in swollen(faces, outline):
                add(corners, (*OUTLINE, 1), True)
    return vertices, colours


def star(points=7, inner=0.42):
    """Flat cartoon burst for muzzle flashes."""
    ring = []
    for i in range(points * 2):
        a = pi * i / points
        r = 1 if i % 2 == 0 else inner
        ring.append((sin(a) * r, cos(a) * r, 0))
    vertices = []
    for i in range(points * 2):
        vertices += [(0, 0, 0), ring[i], ring[(i + 1) % len(ring)]]
    return Mesh(vertices=vertices, mode='triangle', static=True)


def fan(corners, inside_out=False):
    """Triangles for one convex face, wound the way `build` winds them."""
    order = corners if inside_out else corners[::-1]
    return [point for i in range(1, len(order) - 1) for point in (tuple(order[0]), tuple(order[i]), tuple(order[i + 1]))]


def streak_mesh(sides=6, tail=0.7, rim=0.45):
    """Bullet trail one unit long: a little narrower at z=0, radius 0.5 at z=1, inside a dark rim.
    Scale it to (width, width, length). The rim only grows sideways, so a trail of any
    length keeps the same outline. White, so the entity's colour tints it."""
    def ring(z, radius):
        return [(sin(2 * pi * (i + 0.5) / sides) * radius, cos(2 * pi * (i + 0.5) / sides) * radius, z)
                for i in range(sides)]

    def walls(grow):
        back, front = ring(0, 0.5 * tail * grow), ring(1, 0.5 * grow)
        return [(back[i], back[i - 1], front[i - 1], front[i]) for i in range(sides)], back, front

    vertices, colours = [], []
    sides_, back, front = walls(1)
    for corners, normal in solid([back, front] + sides_):
        triangles = fan(corners)
        s = shade(normal)
        vertices += triangles
        colours += [(s, s, s, 1)] * len(triangles)
    for corners, _ in solid(walls(1 + rim)[0]):
        triangles = fan(corners, inside_out=True)
        vertices += triangles
        colours += [(*OUTLINE, 1)] * len(triangles)
    return Mesh(vertices=vertices, colors=colours, mode='triangle', static=True)


def slug_mesh():
    """A cartoon bullet one unit long and one wide, pointing along z. White, to be tinted."""
    return build([(barrel(0.5, 0, 0.55, sides=8), (0.82, 0.82, 0.82)),
                  (barrel(0.5, 0.55, 1.0, sides=8, end_radius=0.1), (1, 1, 1))], outline=0.14)


def flat_bands(outlines, tints):
    """Flat shape made of closed outlines nested inside each other, filled band by band.
    outlines[0] is fanned from the centre with tints[0]; each later one adds a band."""
    vertices, colours = [], []
    n = len(outlines[0])
    for i in range(n):
        j = (i + 1) % n
        if tints[0] is not None:        # None leaves the middle open
            vertices += [(0, 0, 0), outlines[0][i], outlines[0][j]]
            colours += [tints[0]] * 3
        for inner, outer, tint in zip(outlines, outlines[1:], tints[1:]):
            vertices += [inner[i], outer[i], outer[j], inner[i], outer[j], inner[j]]
            colours += [tint] * 6
    return Mesh(vertices=vertices, colors=colours, mode='triangle', static=True)


def burst_mesh(points=7, inner=0.42, rim=1.25):
    """Outlined star for impacts: white heart, dark rim. Draw it double-sided."""
    shape = []
    for i in range(points * 2):
        a = pi * i / points
        r = 1 if i % 2 == 0 else inner
        shape.append((sin(a) * r, cos(a) * r, 0))
    return flat_bands([shape, [(x * rim, y * rim, 0) for x, y, _ in shape]], [(1, 1, 1, 1), (*OUTLINE, 1)])


def dashed_ring(segments=10, fill=0.62, thickness=0.18, rim=0.05, steps=4):
    """A ring of radius 1 broken into dashes, each a white band inside a dark rim, flat in xy.
    Spun about its middle it reads as turning; tinted, as anyone's colour."""
    vertices, colours = [], []
    radii = (1 - thickness - rim, 1 - thickness, 1, 1 + rim)
    tints = ((*OUTLINE, 1), (1, 1, 1, 1), (*OUTLINE, 1))
    span = 2 * pi / segments
    for k in range(segments):
        a0 = k * span
        angles = [a0 + span * fill * i / steps for i in range(steps + 1)]
        for a, b in zip(angles, angles[1:]):
            for (r0, r1), tint in zip(zip(radii, radii[1:]), tints):
                p = [(sin(a) * r0, cos(a) * r0, 0), (sin(a) * r1, cos(a) * r1, 0),
                     (sin(b) * r1, cos(b) * r1, 0), (sin(b) * r0, cos(b) * r0, 0)]
                vertices += [p[0], p[1], p[2], p[0], p[2], p[3]]
                colours += [tint] * 6
    return Mesh(vertices=vertices, colors=colours, mode='triangle', static=True)


def halo_mesh(steps=24):
    """A glow in hard steps: three discs, each fainter than the one inside it, white to be tinted."""
    def circle(radius):
        return [(sin(2 * pi * i / steps) * radius, cos(2 * pi * i / steps) * radius, 0) for i in range(steps)]
    return flat_bands([circle(0.22), circle(0.36), circle(0.5)], [(1, 1, 1, 0.42), (1, 1, 1, 0.26), (1, 1, 1, 0.12)])


def ring_mesh(steps=28, thickness=0.2, rim=0.05):
    """Outlined shock ring of radius 1: a white band between two dark lines, hollow inside."""
    def circle(radius):
        return [(sin(2 * pi * i / steps) * radius, cos(2 * pi * i / steps) * radius, 0) for i in range(steps)]

    radii = (1 - thickness - rim, 1 - thickness, 1, 1 + rim)
    return flat_bands([circle(r) for r in radii], [None, (*OUTLINE, 1), (1, 1, 1, 1), (*OUTLINE, 1)])
