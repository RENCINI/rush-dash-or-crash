"""The shader every solid is drawn with: Ursina's unlit one (vertex colour x texture x colour
scale) plus a few things the toon look needs, all doing nothing until asked.

- `flash` (0-1) washes a body to white, but not its ink: a vertex as dark as the outline keeps
  its colour, so a hit enemy flashes white inside a dark rim.
- `status` (rgb, amount) recolours the body in two hard bands, light faces more than dark ones:
  fire, poison, cold, a glowing enemy's cyan.
- `gold` (rgb, amount) turns a body that colour all through, keeping its light and shade.
- `dull` (0-1) greys it out and lifts it: stunned.
- `fog` (rgb, amount) and `fog_range` (near, far) fade far things toward the sky in steps.
- `pattern` (scale, strength) with `pattern_tex` lays a small pixel-art tile over a surface, picked
  by which way the face looks, so meshes need no texture coordinates (fx/textures.py).

Shader inputs set on a node reach everything under it, unless something under it sets its own.
Ursina writes a shader's `default_input` onto every entity, so these are left out of it and set
once on the roots instead (`install`); an enemy or a map sets them on its own root to change them.
"""
from panda3d.core import SamplerState, Texture as PandaTexture
from ursina import Entity, Shader, Vec2, Vec4, camera, scene

INK = 0.1       # vertices this dark are outline, which no tint or flash touches

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
uniform vec4 fog;
uniform vec2 fog_range;
uniform sampler2D pattern_tex;
uniform vec2 pattern;
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
        float light = dot(colour.rgb, LUMA);
        if (gold.a > 0.0) {
            colour.rgb = mix(colour.rgb, gold.rgb * (0.45 + 0.75 * light), gold.a);
        }
        if (status.a > 0.0) {
            float band = light > 0.42 ? 1.0 : 0.62;
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
    node.setShaderInput('fog', Vec4(0, 0, 0, 0))
    node.setShaderInput('fog_range', Vec2(0, 1))
    node.setShaderInput('pattern_tex', blank_pattern())
    node.setShaderInput('pattern', Vec2(0, 0))


def install():
    """Draw everything with the toon shader from now on."""
    Entity.default_shader = toon_shader
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
