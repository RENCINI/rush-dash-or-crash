"""What is done to the whole picture of the arena after it is drawn: one full-screen shader
(`camera.shader`). The HUD and the menus are drawn by another camera, so none of this touches them.

- `saturation`: 1 is as drawn. Overdrive pushes it up; losing the chain drains it for a moment.
- `aberration`: red and blue pulled apart toward the edges. Overdrive, and a jolt on kills.
- `edge` (rgb, amount): a glow round the screen in hard bands, a step brighter for each chain tier.
- `radial`: a smear out from the middle, at speed.
- `flash`: the whole picture washed white for a frame or two.
- `pause`: blurred, darkened and greyed behind a menu.
- `crt`: a curved, scanlined screen behind the upgrade terminal.
- `wipe` (0-1): blocks of ink cover the screen, for going from one place to another.

`set(name, value)` is where a value is heading; `pulse(name, peak, seconds)` throws it up to
`peak` and lets it fall back. Values move in real time, so hitstop and menus don't stop them. If
the picture can't be filtered (the tests draw offscreen) this does nothing, but takes the same calls.
"""
from ursina import Entity, Shader, Vec4, camera, time

DEFAULTS = {'saturation': 1.0, 'aberration': 0.0, 'radial': 0.0, 'flash': 0.0, 'pause': 0.0, 'crt': 0.0,
            'wipe': 0.0, 'edge_amount': 0.0}
RATES = {'saturation': 4.0, 'aberration': 10.0, 'radial': 6.0, 'flash': 30.0, 'pause': 8.0, 'crt': 8.0,
         'wipe': 0.0, 'edge_amount': 6.0}     # how quickly each eases to where it is heading; 0 is at once

post_shader = Shader(name='post_shader', language=Shader.GLSL, fragment='''#version 330
uniform sampler2D tex;
uniform float saturation;
uniform float aberration;
uniform float radial;
uniform float flash;
uniform float pause;
uniform float crt;
uniform float wipe;
uniform vec4 edge;
uniform float aspect;
in vec2 uv;
out vec4 out_color;

const vec3 LUMA = vec3(0.299, 0.587, 0.114);
const vec3 INK = vec3(0.08, 0.07, 0.15);

vec3 pick(vec2 p) {
    if (aberration > 0.0) {
        vec2 d = (p - 0.5) * aberration * 2.0;
        return vec3(texture(tex, p + d).r, texture(tex, p).g, texture(tex, p - d).b);
    }
    return texture(tex, p).rgb;
}

float hash(vec2 p) {
    return fract(sin(dot(p, vec2(12.9898, 78.233))) * 43758.5453);
}

void main() {
    vec2 p = uv;
    if (crt > 0.0) {
        vec2 c = p - 0.5;
        p = 0.5 + c * (1.0 + crt * 0.12 * dot(c, c) * 4.0);
    }
    vec3 colour = pick(p);
    if (radial > 0.0) {
        // the smear takes plain samples: the colour split is in the first one already
        vec2 out_way = (p - 0.5) * radial * 0.03;
        vec3 smear = colour;
        for (int i = 1; i < 4; i++) {
            smear += texture(tex, p - out_way * float(i)).rgb;
        }
        colour = smear / 4.0;
    }
    if (pause > 0.0) {
        vec3 soft = vec3(0.0);
        for (int x = -2; x <= 2; x++) {
            for (int y = -2; y <= 2; y++) {
                soft += texture(tex, p + vec2(float(x) / aspect, float(y)) * 0.006 * pause).rgb;
            }
        }
        colour = mix(colour, soft / 25.0, pause);
    }
    float light = dot(colour, LUMA);
    colour = max(mix(vec3(light), colour, saturation), 0.0);
    if (pause > 0.0) {
        colour = mix(colour, vec3(light) * 0.5 + vec3(0.05, 0.04, 0.1), pause * 0.6);
    }
    if (edge.a > 0.0) {
        float inside = 1.0 - max(abs(uv.x - 0.5), abs(uv.y - 0.5) * 1.0) * 2.0;
        float band = inside < 0.018 ? 1.0 : inside < 0.045 ? 0.55 : inside < 0.08 ? 0.22 : 0.0;
        colour = mix(colour, edge.rgb, band * edge.a);
    }
    colour = mix(colour, vec3(1.0), flash);
    if (crt > 0.0) {
        colour *= 1.0 - crt * 0.14 * step(0.5, fract(uv.y * 270.0));
        if (p.x < 0.0 || p.x > 1.0 || p.y < 0.0 || p.y > 1.0) {
            colour = INK;
        }
    }
    if (wipe > 0.0) {
        vec2 grid = vec2(16.0, 9.0);
        vec2 cell = floor(uv * grid);
        float order = (cell.x + (grid.y - 1.0 - cell.y) * 0.7) / (grid.x + grid.y * 0.7);
        order = order * 0.8 + hash(cell) * 0.2;
        float grow = clamp((wipe * 1.35 - order) * 5.0, 0.0, 1.0);
        vec2 inner = abs(fract(uv * grid) - 0.5) * 2.0;
        if (max(inner.x, inner.y) < grow) {
            colour = INK;
        }
    }
    out_color = vec4(colour, 1.0);
}
''')


class PostFx(Entity):
    def __init__(self, enabled=True):
        super().__init__(ignore_paused=True)
        self.values = dict(DEFAULTS)
        self.targets = dict(DEFAULTS)
        self.pulses = {}            # name -> [peak, seconds, seconds left]
        self.edge_colour = (1.0, 1.0, 1.0)
        self.reveal_time = self.reveal_left = 0.0
        self.written = {}
        self.active = False
        self.switch(enabled)

    def switch(self, on):
        """Filter the picture, or stop. Returns whether it is filtered."""
        if on and not self.active:
            try:
                camera.shader = post_shader
                if camera.filter_quad is None:
                    raise RuntimeError('no filter')
                self.active = True
                self.written.clear()
                self.write()
            except Exception:
                self.active = False
                try:
                    camera.shader = None
                except Exception:
                    pass
        elif not on and self.active:
            camera.shader = None
            self.active = False
        return self.active

    def set(self, name, value):
        self.targets[name] = value
        if not RATES.get(name):
            self.values[name] = value

    def pulse(self, name, peak, seconds):
        held = self.pulses.get(name)
        if held is None or peak >= held[0] * held[2] / held[1]:
            self.pulses[name] = [peak, seconds, seconds]

    def reveal(self, seconds=0.6):
        """Cover the screen in blocks of ink at once, and take them away over `seconds`: the new
        place, or the new start, comes up out of the dark."""
        self.reveal_time = self.reveal_left = seconds

    def edge(self, colour, amount):
        self.edge_colour = (colour[0], colour[1], colour[2])
        self.set('edge_amount', amount)

    def now(self, name):
        """The value as it is drawn this frame, pulses and all."""
        value = self.values[name]
        held = self.pulses.get(name)
        if held is not None:
            share = held[2] / held[1]
            value = max(value, held[0] * share) if name != 'saturation' else min(value, 1 - (1 - held[0]) * share)
        return value

    def update(self):
        dt = time.dt_unscaled
        for name, target in self.targets.items():
            rate = RATES.get(name)
            if rate:
                self.values[name] += (target - self.values[name]) * min(1.0, rate * dt)
        for name in list(self.pulses):
            self.pulses[name][2] -= dt
            if self.pulses[name][2] <= 0:
                del self.pulses[name]
        if self.reveal_left > 0:
            self.reveal_left = max(0.0, self.reveal_left - dt)
            self.values['wipe'] = self.reveal_left / self.reveal_time
        if self.active:
            self.write()

    def write(self):
        from ursina import window
        inputs = {name: round(self.now(name), 4) for name in DEFAULTS if name != 'edge_amount'}
        inputs['aspect'] = round(window.aspect_ratio, 4)
        for name, value in inputs.items():
            if self.written.get(name) != value:
                self.written[name] = value
                camera.set_shader_input(name, value)
        edge = (*self.edge_colour, round(self.now('edge_amount'), 4))
        if self.written.get('edge') != edge:
            self.written['edge'] = edge
            camera.set_shader_input('edge', Vec4(*edge))
