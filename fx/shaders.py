"""The shader every solid is drawn with: Ursina's unlit one (vertex colour x texture x colour
scale) plus a few things the toon look needs, all doing nothing until asked.

- `flash` (0-1) washes a body to white, but not its ink: a vertex as dark as the outline keeps
  its colour, so a hit enemy flashes white inside a dark rim.
- `status` (rgb, amount) recolours the body in two hard bands, light faces more than dark ones:
  fire, poison, cold, a glowing enemy's cyan.
- `gold` (rgb, amount) turns a body that colour all through, keeping its light and shade.
- `dull` (0-1) greys it out and lifts it: stunned.
- `neon` (0-1) lights up only the parts painted parry green, toward white: a green enemy throbs
  where it is green, and nowhere else.
- `fog` (rgb, amount) and `fog_range` (near, far) fade far things toward the sky in steps.
- `pattern` (scale, strength) with `pattern_tex` lays a small pixel-art tile over a surface, picked
  by which way the face looks, so meshes need no texture coordinates (fx/textures.py).
- `lamps` (x, y, z, radius) and `lamp_tints` (rgb), `lamp_count` of them: pools of coloured light
  in two hard rings round something that glows, on whatever is near it (`Lamps`).

Shader inputs set on a node reach everything under it, unless something under it sets its own.
Ursina writes a shader's `default_input` onto every entity, so these are left out of it and set
once on the roots instead (`install`); an enemy or a map sets them on its own root to change them.
"""
from panda3d.core import LVecBase4f, PTA_LVecBase4f, SamplerState, Texture as PandaTexture
from ursina import Entity, Shader, Vec2, Vec4, application, camera, scene
from ursina.shaders import unlit_shader

INK = 0.1       # vertices this dark are outline, which no tint or flash touches
LAMPS = 16      # the most pools of light one node can have

toon_shader = Shader(name='toon_shader', language=Shader.GLSL, vertex='''#version 140
uniform mat4 p3d_ModelViewProjectionMatrix;
uniform mat4 p3d_ModelViewMatrix;
uniform mat4 p3d_ModelMatrix;
uniform vec2 texture_scale;
uniform vec2 texture_offset;
in vec4 p3d_Vertex;
in vec2 p3d_MultiTexCoord0;
in vec4 p3d_Color;
out vec2 uvs;
out vec4 vertex_color;
out vec3 world_position;
out float depth;

void main() {
    gl_Position = p3d_ModelViewProjectionMatrix * p3d_Vertex;
    uvs = p3d_MultiTexCoord0 * texture_scale + texture_offset;
    vertex_color = p3d_Color;
    world_position = (p3d_ModelMatrix * p3d_Vertex).xyz;
    depth = -(p3d_ModelViewMatrix * p3d_Vertex).z;
}
''', fragment='''#version 140
uniform sampler2D p3d_Texture0;
uniform vec4 p3d_ColorScale;
uniform float flash;
uniform vec4 status;
uniform vec4 gold;
uniform float dull;
uniform float neon;
uniform vec4 fog;
uniform vec2 fog_range;
uniform sampler2D pattern_tex;
uniform vec2 pattern;
uniform vec4 lamps[''' + str(LAMPS) + '''];
uniform vec4 lamp_tints[''' + str(LAMPS) + '''];
uniform float lamp_count;
in vec2 uvs;
in vec4 vertex_color;
in vec3 world_position;
in float depth;
out vec4 fragColor;

const vec3 LUMA = vec3(0.299, 0.587, 0.114);

void main() {
    vec4 colour = texture(p3d_Texture0, uvs) * p3d_ColorScale * vertex_color;
    float own = dot(vertex_color.rgb, LUMA);
    if (pattern.y > 0.0) {
        vec3 n = abs(normalize(cross(dFdx(world_position), dFdy(world_position))));
        vec2 at = n.y > max(n.x, n.z) ? world_position.xz : (n.x > n.z ? world_position.zy : world_position.xy);
        float tile = texture(pattern_tex, at * pattern.x).r;
        colour.rgb *= 1.0 + (tile - 0.5) * 2.0 * pattern.y;
    }
    if (own > ''' + str(INK) + ''') {
        float lit = dot(colour.rgb, LUMA);
        for (int i = 0; i < ''' + str(LAMPS) + '''; i++) {
            if (float(i) >= lamp_count) {
                break;
            }
            float d = distance(world_position, lamps[i].xyz);
            float band = d < lamps[i].w * 0.45 ? 0.36 : (d < lamps[i].w ? 0.17 : 0.0);
            colour.rgb = mix(colour.rgb, lamp_tints[i].rgb * (0.45 + 0.7 * lit), band);
        }
        vec3 v = vertex_color.rgb;
        if (neon > 0.0 && v.g > 0.5 && v.g > v.r * 2.2 && v.g > v.b * 1.8) {
            colour.rgb = mix(colour.rgb, vec3(0.85, 1.0, 0.85), neon);
        }
        float light = dot(colour.rgb, LUMA);
        if (gold.a > 0.0) {
            colour.rgb = mix(colour.rgb, gold.rgb * (0.45 + 0.75 * light), gold.a);
        }
        if (status.a > 0.0) {
            float band = light > 0.42 ? 1.0 : 0.8;
            colour.rgb = mix(colour.rgb, status.rgb * (0.55 + 0.6 * light), status.a * band);
        }
        if (dull > 0.0) {
            colour.rgb = mix(colour.rgb, vec3(0.35 + 0.6 * light), dull);
        }
        colour.rgb = mix(colour.rgb, vec3(1.0), flash);
    }
    if (fog.a > 0.0) {
        float far = clamp((depth - fog_range.x) / max(fog_range.y - fog_range.x, 0.001), 0.0, 1.0);
        colour.rgb = mix(colour.rgb, fog.rgb, floor(far * 4.0) / 4.0 * fog.a);
    }
    fragColor = colour;
}
''', default_input={'texture_scale': Vec2(1, 1), 'texture_offset': Vec2(0, 0)})

_blank = None


def blank_pattern():
    """A tile that changes nothing, for every node that has no pattern of its own."""
    global _blank
    if _blank is None:
        _blank = PandaTexture('blank_pattern')
        _blank.setup2dTexture(1, 1, PandaTexture.T_unsigned_byte, PandaTexture.F_rgba8)
        _blank.setRamImage(bytes((128, 128, 128, 255)))
        _blank.setMagfilter(SamplerState.FT_nearest)
        _blank.setMinfilter(SamplerState.FT_nearest)
    return _blank


def neutral(node):
    """Set every toon input on `node` to doing nothing."""
    node.setShaderInput('flash', 0.0)
    node.setShaderInput('status', Vec4(0, 0, 0, 0))
    node.setShaderInput('gold', Vec4(0, 0, 0, 0))
    node.setShaderInput('dull', 0.0)
    node.setShaderInput('neon', 0.0)
    node.setShaderInput('fog', Vec4(0, 0, 0, 0))
    node.setShaderInput('fog_range', Vec2(0, 1))
    node.setShaderInput('pattern_tex', blank_pattern())
    node.setShaderInput('pattern', Vec2(0, 0))
    node.setShaderInput('lamps', PTA_LVecBase4f.empty_array(LAMPS))
    node.setShaderInput('lamp_tints', PTA_LVecBase4f.empty_array(LAMPS))
    node.setShaderInput('lamp_count', 0.0)


def pattern(node, texture, scale, strength):
    """Lay a tile from fx/textures.py over everything under `node`: one tile every 1/scale metres."""
    node.setShaderInput('pattern_tex', texture._texture)
    node.setShaderInput('pattern', Vec2(scale, strength))


class Lamps:
    """The pools of light under one node: up to LAMPS of them, each (position, rgb, radius). Any
    one can be recoloured every frame without anything being set again."""

    def __init__(self, node, lamps):
        self.where = PTA_LVecBase4f.empty_array(LAMPS)
        self.tints = PTA_LVecBase4f.empty_array(LAMPS)
        for i, (position, tint, radius) in enumerate(lamps[:LAMPS]):
            self.where[i] = LVecBase4f(position[0], position[1], position[2], radius)
            self.tints[i] = LVecBase4f(tint[0], tint[1], tint[2], 1)
        node.setShaderInput('lamps', self.where)
        node.setShaderInput('lamp_tints', self.tints)
        node.setShaderInput('lamp_count', float(min(len(lamps), LAMPS)))

    def tint(self, i, rgb):
        self.tints[i] = LVecBase4f(rgb[0], rgb[1], rgb[2], 1)


def compiles(shader):
    """Whether this graphics card accepts `shader`. Where that can't be asked (no window), yes."""
    try:
        gsg = base.win.getGsg()
        shader._shader.prepare_now(gsg.getPreparedObjects(), gsg)
        return not shader._shader.getErrorFlag()
    except Exception:
        return True


def report():
    """What the card is, written to gpu.txt beside the game, for when something draws wrong."""
    try:
        from fx.postfx import post_shader
        gsg = base.win.getGsg()
        lines = (f'renderer: {gsg.getDriverRenderer()}', f'vendor: {gsg.getDriverVendor()}',
                 f'opengl: {gsg.getDriverVersion()}',
                 f'glsl: {gsg.getDriverShaderVersionMajor()}.{gsg.getDriverShaderVersionMinor()}',
                 f'toon shader ok: {compiles(toon_shader)}', f'filter shader ok: {compiles(post_shader)}')
        (application.asset_folder / 'gpu.txt').write_text('\n'.join(lines) + '\n')
    except Exception:
        pass


def install():
    """Draw everything with the toon shader from now on, or with Ursina's plain unlit one where the
    card refuses it (some laptop chips): flat colours, but nothing missing."""
    Entity.default_shader = toon_shader if compiles(toon_shader) else unlit_shader
    report()
    neutral(scene)
    neutral(camera.ui_render)


class Look:
    """The toon inputs on one node, written only when they change (a write costs more than a compare)."""

    def __init__(self, node):
        self.node = node
        self.shown = {}

    def set(self, name, *value):
        """`value` is 1, 2 or 4 numbers."""
        if self.shown.get(name) != value:
            self.shown[name] = value
            n = len(value)
            self.node.setShaderInput(name, value[0] if n == 1 else Vec2(*value) if n == 2 else Vec4(*value))

    def forget(self):
        """Something else wrote the inputs: write them all again next time."""
        self.shown.clear()
