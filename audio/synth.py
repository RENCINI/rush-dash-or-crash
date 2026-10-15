"""Every sound in the game, generated with numpy and cached as WAV files."""
import wave
from pathlib import Path

import numpy as np

RATE = 44100
VERSION = 'v10'      # bump when a recipe changes so cached files are rebuilt


def ramp(duration):
    return np.linspace(0, 1, int(RATE * duration), endpoint=False)


def tone(duration, f0, f1=None, shape='sine', curve=1.0):
    """Oscillator sweeping from f0 to f1."""
    x = ramp(duration)
    freq = f0 + ((f1 if f1 is not None else f0) - f0) * x ** curve
    phase = 2 * np.pi * np.cumsum(freq) / RATE
    if shape == 'square':
        return np.sign(np.sin(phase))
    if shape == 'saw':
        return (phase / np.pi) % 2 - 1
    if shape == 'triangle':
        return 2 * np.abs((phase / np.pi) % 2 - 1) - 1
    return np.sin(phase)


def noise(duration, seed=0):
    return np.random.default_rng(seed).uniform(-1, 1, int(RATE * duration))


def lowpass(x, cutoff):
    width = max(3, int(RATE / cutoff))
    kernel = np.hanning(width)
    return np.convolve(x, kernel / kernel.sum(), mode='same')


def highpass(x, cutoff):
    return x - lowpass(x, cutoff)


def decay(duration, rate, attack=0.002):
    x = ramp(duration)
    return np.exp(-x * rate) * np.minimum(1, x * duration / attack)


def swell(duration, peak=0.3):
    """Rises to `peak` (share of the duration) then fades to silence."""
    x = ramp(duration)
    return np.where(x < peak, x / peak, (1 - x) / (1 - peak)) ** 1.5


def fit(*parts):
    """Sum parts of different lengths."""
    out = np.zeros(max(len(p) for p in parts))
    for p in parts:
        out[:len(p)] += p
    return out


def fm_bell(duration, f, ratio=3.5, index=2.0, rate=6.0):
    """A glassy bell: a sine whose phase is pushed about by another, the push dying away first."""
    x = ramp(duration)
    t = x * duration
    env = np.exp(-x * rate)
    mod = np.sin(2 * np.pi * f * ratio * t) * index * np.exp(-x * rate * 2)
    return np.sin(2 * np.pi * f * t + mod) * env * np.minimum(1, t / 0.002)


def reverb(x, length=0.6, wet=0.2, seed=99, loop=False):
    """A small room: the sound convolved with a burst of decaying noise. `loop` wraps the tail
    round to the start, for a clip that repeats."""
    n = int(RATE * length)
    rng = np.random.default_rng(seed)
    ir = rng.uniform(-1, 1, n) * np.exp(-np.linspace(0, 7, n))
    ir = lowpass(ir, 5000)
    ir /= np.sqrt(np.sum(ir * ir))
    size = len(x) if loop else len(x) + n
    tail = np.fft.irfft(np.fft.rfft(x, size) * np.fft.rfft(ir, size), size)
    dry = x if loop else np.concatenate([x, np.zeros(n)])
    return dry + tail * wet


def midi(note):
    return 440.0 * 2 ** ((note - 69) / 12)


def shot_popper():
    d = 0.13
    return (tone(d, 950, 180, 'square', 0.5) * 0.5 + highpass(noise(d, 1), 3000) * 0.6) * decay(d, 9)


def shot_scatter():
    d = 0.34
    return fit(lowpass(noise(d, 2), 2600) * decay(d, 5) * 1.4, tone(0.2, 150, 45) * decay(0.2, 4))


def shot_rocket():
    """Launch: a hollow thump out of the tube, then the motor catching and tearing away."""
    thump = tone(0.3, 210, 42, curve=0.5) * decay(0.3, 4) * 2.2
    cough = lowpass(noise(0.12, 3), 1600) * decay(0.12, 4) * 1.8
    d = 0.75
    motor = highpass(lowpass(noise(d, 34), 5200), 700) * swell(d, 0.18) * 1.5
    whine = tone(d, 480, 1500, 'saw', 0.6) * swell(d, 0.25) * 0.12
    return np.tanh(fit(thump, cough, motor, whine) * 0.8) * 1.2


def bounce():
    d = 0.08
    return tone(d, 520, 760, 'triangle') * decay(d, 6)


def explode():
    """A hard crack, a body of low roar, a sub that drops through the floor and debris raining after."""
    crack = highpass(noise(0.07, 5), 1800) * decay(0.07, 4) * 2.2
    roar = lowpass(noise(0.9, 4), 1100) * decay(0.9, 3.5) * 3.0
    sub = tone(1.1, 110, 24, curve=0.5) * decay(1.1, 3) * 2.6
    punch = tone(0.18, 260, 55) * decay(0.18, 4) * 1.8
    debris = crackle(1.3, 35, 0.012) * decay(1.3, 3, attack=0.15) * 1.6
    rumble = lowpass(noise(1.6, 36), 320) * decay(1.6, 3, attack=0.1) * 1.6
    return np.tanh(fit(crack, roar, sub, punch, late(debris, 0.08), rumble) * 0.7) * 1.22


def hit():
    """A round little knock with a click on top; the game pitches it by how hard the hit was."""
    d = 0.06
    knock = tone(d, 1500, 1050, 'triangle', 0.5) * 0.8 + tone(d, 3000, 2100, curve=0.5) * 0.2
    return fit(knock * decay(d, 9), highpass(noise(0.008, 6), 4000) * decay(0.008, 4) * 0.5)


def kill():
    """A kill, Balatro's chip: a card flick, a bubble pop and a glassy bell. The game plays it a
    note higher on the scale for every chain tier, so a long chain climbs like a tune."""
    flick = highpass(noise(0.012, 7), 3500) * decay(0.012, 4) * 0.7
    pop = tone(0.05, 900, 260, curve=0.4) * decay(0.05, 5) * 0.9
    bell = fm_bell(0.45, 880, ratio=3.5, index=2.2) * 0.7 + tone(0.45, 1760) * decay(0.45, 9) * 0.2
    return reverb(fit(flick, pop, late(bell, 0.008)), 0.5, 0.18) * 0.9


def dash():
    d = 0.28
    return highpass(lowpass(noise(d, 8), 3500), 500) * swell(d, 0.2) * 1.6


def jump():
    d = 0.1
    return tone(d, 300, 520, 'triangle') * decay(d, 5)


def land():
    d = 0.12
    return fit(tone(d, 130, 60) * decay(d, 5), lowpass(noise(0.05, 9), 1200) * decay(0.05, 8) * 0.6)


def pad():
    d = 0.36
    x = ramp(d)
    wobble = 1 + 0.06 * np.sin(2 * np.pi * 28 * x)
    freq = (220 + 760 * x ** 0.5) * wobble
    return np.sin(2 * np.pi * np.cumsum(freq) / RATE) * decay(d, 3)


def boost():
    step = 0.055
    notes = [tone(step, f, shape='saw') * decay(step, 3) for f in (392, 523, 659, 784, 1047)]
    return lowpass(np.concatenate(notes), 5000) * 0.6


def slide():
    d = 0.3
    return highpass(lowpass(noise(d, 10), 1800), 300) * swell(d, 0.1) * 1.3


def hurt():
    d = 0.22
    return (tone(d, 420, 140, 'square') * 0.5 + lowpass(noise(d, 11), 1500) * 0.6) * decay(d, 4)


def spawn():
    d = 0.2
    return tone(d, 880, 330, 'triangle') * decay(d, 5) * 0.7


def switch():
    d = 0.06
    return (tone(d, 700, 1100, 'square') * 0.4 + highpass(noise(d, 12), 3000) * 0.3) * decay(d, 8)


def shot_buzzer():
    d = 0.085
    snap = (tone(d, 1500, 320, 'square', 0.5) * 0.4 + highpass(noise(d, 20), 2500) * 0.7) * decay(d, 11)
    return fit(snap, tone(0.05, 230, 90) * decay(0.05, 5) * 0.7)


def late(x, seconds):
    return np.concatenate([np.zeros(int(RATE * seconds)), x])


def shot_longshot():
    """A cannon, not a rifle: whip-crack, a sub drop you feel, a tearing screech and
    the crack slapping back off the arena walls into a long rumble."""
    crack = highpass(noise(0.06, 21), 1800) * decay(0.06, 4) * 2.4
    body = lowpass(noise(0.6, 22), 2200) * decay(0.6, 5) * 2.2
    sub = tone(0.9, 95, 26, curve=0.5) * decay(0.9, 3.5) * 2.4
    punch = tone(0.16, 300, 60) * decay(0.16, 4) * 1.6
    tear = tone(0.35, 5200, 380, 'saw', 0.3) * decay(0.35, 6) * 0.35
    echo = lowpass(noise(0.12, 32), 1500) * decay(0.12, 4)
    slaps = fit(late(echo * 0.9, 0.14), late(echo * 0.55, 0.3), late(echo * 0.3, 0.5))
    rumble = lowpass(noise(1.5, 23), 420) * decay(1.5, 3.5, attack=0.1) * 1.5
    return np.tanh(fit(crack, body, sub, punch, tear, slaps, rumble) * 0.75) * 1.22     # squashed, not clipped


def longshot_hit():
    """The round going through something: a wet crunch on top of a deep knock."""
    crunch = lowpass(highpass(noise(0.14, 33), 500), 3500) * decay(0.14, 6) * 1.6
    knock = tone(0.3, 110, 38) * decay(0.3, 4) * 1.8
    return np.tanh(fit(crunch, knock) * 0.8) * 1.15


def pump():
    click = lowpass(noise(0.04, 24), 2200) * decay(0.04, 6) + tone(0.04, 420, 260, 'square') * decay(0.04, 6) * 0.25
    return fit(click, np.concatenate([np.zeros(int(RATE * 0.13)), click * 1.2]))


def bolt():
    click = highpass(noise(0.03, 25), 2500) * decay(0.03, 7) + tone(0.03, 1900, 1300, 'square') * decay(0.03, 7) * 0.2
    return fit(click, np.concatenate([np.zeros(int(RATE * 0.17)), click * 1.2])) * 0.8


def scope_in():
    d = 0.09
    return highpass(lowpass(noise(d, 26), 4000), 1200) * swell(d, 0.3) * 1.2 + tone(d, 500, 950) * swell(d, 0.5) * 0.25


def quickscope():
    """Two bright rising notes with a sparkle on top."""
    first = tone(0.08, 1319, shape='triangle') * decay(0.08, 3)
    second = tone(0.34, 1976, shape='triangle') * decay(0.34, 5) + tone(0.34, 3951) * decay(0.34, 7) * 0.4
    return fit(first, np.concatenate([np.zeros(int(RATE * 0.07)), second])) * 0.8


def crackle(duration, seed, density=0.004):
    """Sparse random clicks: the sound of arcing electricity."""
    rng = np.random.default_rng(seed)
    n = int(RATE * duration)
    spikes = np.where(rng.random(n) < density, rng.uniform(-1, 1, n), 0)
    return highpass(np.convolve(spikes, np.hanning(9), mode='same'), 1800)


def overdrive():
    """A lightning strike: snap, falling zap, a gated buzz and a rising chord under it."""
    d = 0.95
    x = ramp(d)
    snap = highpass(noise(0.1, 27), 1500) * decay(0.1, 5) * 1.8
    zap = tone(0.4, 3400, 220, 'square', 0.35) * decay(0.4, 5) * 0.5
    gate = 0.5 + 0.5 * np.sign(np.sin(2 * np.pi * 41 * x))
    buzz = lowpass(tone(d, 55, 110, 'saw') * gate, 3000) * decay(d, 2.5) * 0.8
    boom = tone(0.55, 125, 36) * decay(0.55, 3) * 1.5
    chord = lowpass(sum(tone(d, f, f * 2, 'saw', 2.0) for f in (220, 277, 330)) / 3, 4500) * swell(d, 0.65) * 0.7
    return np.tanh(fit(snap, zap, buzz, boom, chord, crackle(d, 28, 0.01) * decay(d, 2) * 1.5) * 0.55) * 1.2


def overdrive_end():
    d = 0.5
    fall = lowpass(tone(d, 520, 90, 'saw'), 2500) * decay(d, 3) * 0.7
    return fit(fall, crackle(d, 29, 0.008) * decay(d, 4) * 1.2)


def zap():
    d = 0.11
    arc = tone(d, 2800, 600, 'square', 0.5) * (0.5 + 0.5 * np.sign(np.sin(2 * np.pi * 190 * ramp(d))))
    return (arc * 0.35 + crackle(d, 30, 0.05) * 1.6) * decay(d, 5)


def bar_tick():
    d = 0.075
    return (tone(d, 880, 1320, 'triangle') + tone(d, 1760, 2640) * 0.3) * decay(d, 5) * 0.7


def loop(x, fade=0.3):
    """Crossfade the ends of a clip so it repeats without a click."""
    fade = int(RATE * fade)
    blend = np.linspace(0, 1, fade)
    out = x[:-fade].copy()
    out[:fade] = x[:fade] * blend + x[-fade:] * (1 - blend)
    return out


def hum():
    """Loop that plays for as long as Overdrive lasts: mains buzz with arcing on top."""
    d = 2.3
    x = ramp(d)
    buzz = lowpass(tone(d, 110, shape='saw'), 1600) * (0.65 + 0.35 * np.sin(2 * np.pi * 50 * x))
    whine = tone(d, 1760) * 0.06 * (0.6 + 0.4 * np.sin(2 * np.pi * 3 * x))
    return loop(buzz * 0.4 + whine + crackle(d, 31, 0.006))


def wind():
    return loop(highpass(lowpass(noise(2.3, 13), 1400), 150) * 2.5)


def slash():
    d = 0.17
    air = highpass(lowpass(noise(d, 40), 6500), 1400) * swell(d, 0.3) * 1.5
    return air + tone(d, 1100, 380, curve=0.6) * swell(d, 0.3) * 0.25


def parry():
    """Steel on steel: a hard click, a low knock and a bell-like ring that hangs on."""
    d = 0.7
    ring = sum(tone(d, f) * decay(d, rate) * level
               for f, rate, level in ((1240, 5, 0.5), (1873, 6, 0.4), (2637, 8, 0.3), (3411, 10, 0.2)))
    click = highpass(noise(0.03, 41), 2500) * decay(0.03, 5) * 1.3
    knock = tone(0.12, 260, 110) * decay(0.12, 5) * 0.9
    return np.tanh(fit(ring, click, knock) * 0.9)


def reflect():
    d = 0.22
    return (tone(d, 620, 2500, curve=0.5) * 0.6 + tone(d, 1240, 5000, curve=0.5) * 0.2) * swell(d, 0.6)


def punch():
    d = 0.14
    return fit(tone(d, 170, 60) * decay(d, 5) * 1.2, lowpass(noise(0.05, 40), 1800) * decay(0.05, 9) * 0.8)


def throw():
    d = 0.22
    return highpass(lowpass(noise(d, 41), 2600), 600) * swell(d, 0.35) * 1.5


def splat():
    d = 0.2
    return fit(lowpass(noise(d, 42), 1400) * decay(d, 5) * 1.6, tone(0.09, 260, 90, 'triangle') * decay(0.09, 6) * 0.6)


def chip():
    """A coin's ping; the game pitches it up as chips are picked up in a row."""
    d = 0.16
    return (tone(d, 1568, shape='triangle') * 0.7 + tone(d, 3136) * 0.35) * decay(d, 6)


def token():
    """A golden enemy's prize: four notes climbing into a shimmer."""
    notes = [late(tone(0.3, f, shape='triangle') * decay(0.3, 4), i * 0.07) for i, f in enumerate((784, 988, 1175, 1568))]
    shimmer = late(tone(0.5, 3136) * decay(0.5, 5) * 0.4 + crackle(0.5, 50, 0.02) * decay(0.5, 4) * 0.6, 0.21)
    return fit(*notes, shimmer) * 0.7


def round_start():
    """Two low horn notes: here they come."""
    first = lowpass(tone(0.22, 196, shape='saw'), 2400) * swell(0.22, 0.15)
    second = lowpass(tone(0.5, 294, shape='saw'), 2600) * swell(0.5, 0.1)
    return fit(first, late(second, 0.2)) * 0.8


def round_clear():
    """A rising major chord, each note on top of the last."""
    notes = [late(tone(0.7 - i * 0.1, f, shape='triangle') * decay(0.7 - i * 0.1, 3), i * 0.1)
             for i, f in enumerate((523, 659, 784, 1047))]
    return fit(*notes) * 0.55


def flame():
    """One puff of the flamethrower; played many times a second it becomes a roar."""
    d = 0.24
    return highpass(lowpass(noise(d, 51), 2200), 250) * swell(d, 0.25) * 1.7 + tone(d, 90, 60) * swell(d, 0.3) * 0.4


def poison():
    """Gas let out under pressure, with a wet bubble under it."""
    d = 0.9
    hiss = highpass(lowpass(noise(d, 52), 7000), 2500) * decay(d, 3, attack=0.03) * 1.3
    bubble = tone(0.35, 240, 520, curve=2.0) * swell(0.35, 0.6) * 0.5
    return fit(hiss, bubble, late(bubble * 0.6, 0.22))


def convert():
    """An enemy changing sides: a falling note that turns round and rises."""
    down = tone(0.16, 880, 440, 'triangle') * decay(0.16, 3)
    up = tone(0.4, 440, 1320, 'triangle', 0.5) * swell(0.4, 0.5) + tone(0.4, 880, 2640, curve=0.5) * swell(0.4, 0.6) * 0.3
    return fit(down, late(up, 0.14)) * 0.7


def steal():
    """Health pulled out of an enemy: a quick slurp upward."""
    d = 0.16
    return (tone(d, 330, 990, curve=0.6) * 0.7 + lowpass(noise(d, 53), 3000) * 0.3) * swell(d, 0.6)


def buy():
    """A till: a click, then a bright two-note ring."""
    click = highpass(noise(0.03, 54), 2000) * decay(0.03, 6)
    ring = fit(tone(0.4, 1319, shape='triangle') * decay(0.4, 5),
               late(tone(0.4, 1760, shape='triangle') * decay(0.4, 5), 0.07))
    return fit(click, late(ring, 0.03) * 0.6)


def reload():
    """A magazine out and another in, then the action let go."""
    out = lowpass(noise(0.05, 71), 1800) * decay(0.05, 5) + tone(0.05, 300, 180, 'square') * decay(0.05, 6) * 0.2
    home = highpass(noise(0.04, 72), 1500) * decay(0.04, 6) + tone(0.04, 900, 500, 'square') * decay(0.04, 7) * 0.25
    return fit(out, late(home * 1.2, 0.28), late(home * 0.8, 0.42)) * 0.9


def empty():
    """The hammer falling on nothing."""
    return (highpass(noise(0.045, 73), 3000) + tone(0.045, 2400, 1800, 'square') * 0.3) * decay(0.045, 8) * 0.7


def unlock():
    """A branch opening: a lock thrown, a sweep up, and four notes that ring out."""
    clunk = lowpass(noise(0.07, 61), 900) * decay(0.07, 5) * 1.5
    sweep = tone(0.35, 220, 1760, curve=0.5) * swell(0.35, 0.7) * 0.4
    notes = [late(tone(0.7, f, shape='triangle') * decay(0.7, 4), 0.32 + i * 0.055)
             for i, f in enumerate((659, 988, 1319, 1976))]
    return fit(clunk, late(sweep, 0.05), *notes) * 0.6


def deny():
    """The shop saying no: two flat buzzes."""
    buzz = lowpass(tone(0.09, 150, 130, 'square'), 2400) * decay(0.09, 2)
    return fit(buzz, late(buzz, 0.12)) * 0.5


def lock():
    """A sniper's laser finding its range: one dry beep."""
    return tone(0.06, 1900, 1900, 'square') * decay(0.06, 3, 0.004) * 0.35


def snipe():
    """The shot: a crack, a thump under it, and the echo rolling off."""
    crack = highpass(noise(0.05, 81), 2200) * decay(0.05, 4) * 1.4
    thump = tone(0.3, 170, 45, curve=0.4) * decay(0.3, 5)
    echo = lowpass(noise(0.9, 82), 900) * decay(0.9, 5) * 0.5
    return fit(crack, thump, late(echo, 0.04)) * 0.9


def snap():
    """Jaws shutting."""
    clack = highpass(noise(0.035, 83), 1800) * decay(0.035, 6)
    return fit(clack, tone(0.08, 320, 110, 'square') * decay(0.08, 5) * 0.4) * 0.8


def growl():
    """A crocodile about to go: a low rattle that rises."""
    rattle = tone(0.4, 60, 105, 'saw') * (0.6 + 0.4 * tone(0.4, 28, 40, 'square'))
    return lowpass(rattle, 900) * swell(0.4, 0.7) * 0.7


def chime():
    """Crystal breaking: three glassy notes at once."""
    notes = [tone(0.5, f, shape='triangle') * decay(0.5, 7 + i * 2) for i, f in enumerate((1568, 2349, 3136))]
    return fit(highpass(noise(0.03, 84), 4000) * decay(0.03, 5) * 0.6, *notes) * 0.35


def dig():
    """Earth thrown up."""
    return lowpass(noise(0.35, 85), 700) * swell(0.35, 0.2) * (0.7 + 0.3 * tone(0.35, 18, 26, 'square')) * 1.1


def stick():
    """A sticky grenade slapping onto something: a wet thunk and a click as it arms."""
    thunk = lowpass(noise(0.12, 86), 500) * decay(0.12, 9) * 1.3
    click = tone(0.03, 2600, 2600, 'square') * decay(0.03, 4) * 0.25
    return fit(thunk, tone(0.1, 180, 90) * decay(0.1, 7) * 0.6, late(click, 0.07))


def beep():
    """A sticky grenade waiting: a short high blip."""
    return tone(0.05, 2400, 2400, 'triangle') * decay(0.05, 3, 0.003) * 0.4


def glug():
    """Health pouring in: a round bubbly gulp that rises."""
    gulp = tone(0.16, 220, 520, curve=0.5) * swell(0.16, 0.25) * 0.8
    bubble = tone(0.07, 700, 1300, 'triangle', curve=0.4) * decay(0.07, 5) * 0.35
    wet = lowpass(noise(0.1, 91), 1800) * decay(0.1, 6) * 0.3
    return np.tanh(fit(gulp, late(bubble, 0.08), wet) * 1.3) * 0.8


def whack():
    """A boxing glove on the bar: a fat thump and a rattle."""
    thump = tone(0.25, 140, 45, curve=0.5) * decay(0.25, 5) * 1.6
    slap = lowpass(noise(0.07, 88), 3000) * decay(0.07, 6) * 1.4
    rattle = crackle(0.3, 89, 0.02) * decay(0.3, 5) * 0.6
    return np.tanh(fit(thump, slap, late(rattle, 0.03)) * 1.2)


def heartbeat():
    """Lub-dub."""
    lub = tone(0.12, 70, 45) * decay(0.12, 6) * 1.4
    dub = tone(0.1, 85, 55) * decay(0.1, 7) * 1.0
    return lowpass(fit(lub, late(dub, 0.16)), 400) * 1.3


def giggle():
    """The heart getting away with it: a run of quick squeaks, falling."""
    return fit(*[late(tone(0.07, f, f * 1.15, 'triangle') * swell(0.07, 0.3), i * 0.08)
                 for i, f in enumerate((1400, 1250, 1500, 1150, 1300))]) * 0.4


def catch():
    """Got it: a bright pluck and a sparkle going up."""
    pluck = tone(0.3, 1047, shape='triangle') * decay(0.3, 6)
    up = fit(*[late(tone(0.18, f) * decay(0.18, 6) * 0.5, i * 0.05) for i, f in enumerate((1319, 1568, 2093, 2637))])
    return fit(pluck, up) * 0.6


def beacon():
    """The beacon: a low throbbing call that rises."""
    hum = tone(1.2, 55, 110, 'saw', curve=0.7) * (0.6 + 0.4 * tone(1.2, 6, 9, 'square'))
    return lowpass(hum, 900) * swell(1.2, 0.5) * 0.7


def roar():
    """A giant: a growl that swells and breaks."""
    body = lowpass(noise(1.1, 90), 700) * (0.6 + 0.4 * tone(1.1, 30, 22, 'square'))
    voice = tone(1.1, 120, 70, 'saw', curve=0.6) * 0.5
    return np.tanh(lowpass(fit(body, voice), 1200) * swell(1.1, 0.3) * 2.0)


# --- the Balatro part: chain, tally, music ---

def tier():
    """The chain climbing a tier: a bell arpeggio up an octave with a shimmer on top. Played a
    note higher for every tier, like the kill."""
    notes = [late(fm_bell(0.5, f, ratio=2.0, index=1.2, rate=5) * 0.5, i * 0.045)
             for i, f in enumerate((880, 1109, 1319, 1760))]
    shimmer = late(crackle(0.4, 101, 0.015) * decay(0.4, 5) * 0.4, 0.12)
    return reverb(fit(*notes, shimmer), 0.7, 0.25) * 0.75


def deflate():
    """The chain lost: a balloon letting go, wobbling down, and a soft womp."""
    d = 0.75
    x = ramp(d)
    wobble = 1 + (0.03 + 0.12 * x) * np.sin(2 * np.pi * 9 * x * d)
    freq = (620 - 500 * x ** 0.7) * wobble
    squeal = lowpass(((np.cumsum(freq) / RATE) % 1) * 2 - 1, 2200) * swell(d, 0.08) * 0.5
    womp = late(tone(0.4, 220, 70, curve=0.6) * decay(0.4, 4) * 0.9, 0.3)
    return reverb(fit(squeal, womp), 0.5, 0.15) * 0.8


def tick():
    """One step of a counting score: a dry woodblock. The tally pitches it up as it speeds up."""
    d = 0.04
    return fit(tone(d, 1800, 1500) * 0.8 * decay(d, 9), highpass(noise(0.006, 102), 3000) * decay(0.006, 4) * 0.4) * 0.6


def slam():
    """The tally landing: a thump, a crash and a bright major stab, all squashed together."""
    thump = tone(0.5, 150, 40, curve=0.5) * decay(0.5, 4) * 2.0
    crash = highpass(noise(1.0, 103), 2500) * decay(1.0, 4) * 0.8
    stab = sum(tone(0.7, f, shape='saw') for f in (440, 554, 659, 880)) / 4
    stab = lowpass(stab, 3500) * decay(0.7, 4) * 1.2
    return reverb(np.tanh(fit(thump, crash, stab) * 1.1), 0.9, 0.25) * 0.65


def mult():
    """Balatro's mult: a brassy chord that blares up into a pop."""
    d = 0.32
    brass = sum(tone(d, f, f * 1.12, 'saw', 0.4) for f in (330, 415, 494)) / 3
    brass = lowpass(brass, 2800) * swell(d, 0.25) * 1.2
    pop = late(tone(0.05, 1200, 400) * decay(0.05, 5) * 0.6, 0.08)
    return reverb(np.tanh(fit(brass, pop) * 1.4), 0.5, 0.2) * 0.8


# The music: four loops of one length at one tempo, started together and faded in by the chain
# (MUSIC_LAYERS in data/tuning.py). A woozy A-minor groove: Am7, Fmaj7, Dm7, E7, two bars each.
BPM = 116
BEAT = 60 / BPM
BARS = 8
LOOP = BEAT * 4 * BARS
CHORDS = ((57, 60, 64, 67), (53, 57, 60, 64), (50, 53, 57, 60), (52, 56, 59, 62))    # two bars each
ROOTS = (45, 41, 38, 40)
MELODY = (      # (beat, beats long, note)
    (0, 1.5, 76), (1.5, 0.5, 74), (2, 1, 72), (3, 1, 69), (4, 0.5, 72), (4.5, 0.5, 74), (5, 1, 76), (6, 2, 79),
    (8, 1.5, 81), (9.5, 0.5, 79), (10, 1, 76), (11, 1, 72), (12, 0.5, 76), (12.5, 0.5, 79), (13, 1, 76), (14, 2, 72),
    (16, 1.5, 74), (17.5, 0.5, 72), (18, 1, 69), (19, 1, 65), (20, 0.5, 69), (20.5, 0.5, 72), (21, 1, 74), (22, 2, 77),
    (24, 1.5, 76), (25.5, 0.5, 74), (26, 1, 71), (27, 1, 68), (28, 0.5, 71), (28.5, 0.5, 74), (29, 1, 76),
    (30, 0.5, 68), (30.5, 0.5, 71), (31, 1, 76),
)


def bed():
    return np.zeros(int(RATE * LOOP))


def put(buffer, beat, sound):
    """Add `sound` into a loop at `beat`, wrapping whatever runs off the end round to the start."""
    start = int(RATE * BEAT * beat) % len(buffer)
    end = min(len(buffer), start + len(sound))
    buffer[start:end] += sound[:end - start]
    rest = sound[end - start:]
    while len(rest):
        take = min(len(rest), len(buffer))
        buffer[:take] += rest[:take]
        rest = rest[take:]


def finish(x, level):
    x = reverb(x, 1.2, 0.22, seed=104, loop=True)
    return x / np.max(np.abs(x)) * level


def chord_of(beat):
    return int(beat // 8) % 4


def saw_at(freq):
    """A sawtooth following a frequency that may change sample by sample."""
    return ((np.cumsum(freq) / RATE) % 1) * 2 - 1


def music_bed():
    """Always on: a wobbly organ pad and a bouncing bass."""
    out = bed()
    span = BEAT * 8
    for i, chord in enumerate(CHORDS):
        x = ramp(span)
        wow = 1 + 0.004 * np.sin(2 * np.pi * 0.7 * x * span)      # the tape wobble
        voices = [saw_at(np.full(len(x), midi(note) * detune) * wow) for note in chord for detune in (0.997, 1.003)]
        pad = lowpass(sum(voices) / len(voices), 1100)
        pad *= np.minimum(1, x * span / 0.25) * np.minimum(1, (1 - x) * span / 0.3)
        pad *= 0.75 + 0.25 * np.sin(2 * np.pi * 4 * x * span)      # tremolo
        put(out, i * 8, pad * 0.5)
    for bar in range(BARS):
        root = ROOTS[chord_of(bar * 4)]
        for at, step, length in ((0, 0, 0.7), (1.5, 12, 0.35), (2, 7, 0.6), (3, 12, 0.35), (3.5, 0, 0.3)):
            d = BEAT * length
            f = midi(root + step - 12)
            note = (tone(d, f, shape='triangle') * 0.7 + tone(d, f * 2) * 0.2) * decay(d, 3, 0.008)
            put(out, bar * 4 + at, note)
    return finish(out, 0.5)


def music_drums():
    """From chain x2: kick, snare and swung hats."""
    out = bed()
    kick = tone(0.25, 130, 42, curve=0.4) * decay(0.25, 7) * 1.5
    snare = fit(lowpass(highpass(noise(0.18, 105), 1200), 7000) * decay(0.18, 12),
                tone(0.1, 210, 160, 'triangle') * decay(0.1, 8) * 0.6)
    hat = highpass(noise(0.04, 106), 6500) * decay(0.04, 10) * 0.5
    for bar in range(BARS):
        b = bar * 4
        for at in ((0, 2.5) if bar % 2 else (0, 1.75, 2.5)):
            put(out, b + at, kick)
        for at in (1, 3):
            put(out, b + at, snare)
        for eighth in range(8):
            swing = 0.17 if eighth % 2 else 0.0
            put(out, b + eighth * 0.5 + swing, hat * (1.0 if eighth % 2 == 0 else 0.6))
        if bar % 2:
            put(out, b + 3.75, snare * 0.35)        # a ghost note into the next bar
    return finish(out, 0.45)


def music_arp():
    """From chain x4: plucked chord tones running up and down in sixteenths."""
    out = bed()
    shape = (0, 1, 2, 3, 4, 3, 2, 1)
    d = BEAT * 0.4
    for step in range(BARS * 16):
        beat = step / 4
        chord = CHORDS[chord_of(beat)]
        tones = list(chord) + [chord[0] + 12]
        f = midi(tones[shape[step % 8]] + 12)
        pluck = lowpass(tone(d, f, shape='square'), 2400 + 1600 * (step % 4 == 0)) * decay(d, 9, 0.003)
        put(out, beat, pluck * (1.0 if step % 4 == 0 else 0.7))
    return finish(out, 0.32)


def music_lead():
    """From chain x7: the tune, on a singing square lead doubled by a bell."""
    out = bed()
    for beat, length, note in MELODY:
        d = BEAT * length
        x = ramp(d)
        vibrato = 1 + 0.006 * np.sin(2 * np.pi * 5.5 * x * d) * np.minimum(1, x * d / 0.15)
        square = np.sign(np.sin(2 * np.pi * np.cumsum(midi(note) * vibrato) / RATE))
        lead = lowpass(square * 0.6 + tone(d, midi(note), shape='triangle'), 3000)
        lead *= np.minimum(1, x * d / 0.02) * np.minimum(1, (1 - x) * d / 0.06)
        put(out, beat, lead * 0.5)
        put(out, beat, fm_bell(min(d, 0.6), midi(note) * 2, ratio=2.0, index=0.8) * 0.25)
    return finish(out, 0.35)


# name -> (recipe, how many copies may overlap)
SOUNDS = {
    'shot_popper': (shot_popper, 4), 'shot_scatter': (shot_scatter, 2), 'shot_rocket': (shot_rocket, 2),
    'bounce': (bounce, 3), 'explode': (explode, 3), 'hit': (hit, 4), 'kill': (kill, 4),
    'dash': (dash, 2), 'jump': (jump, 2), 'land': (land, 2), 'pad': (pad, 2), 'boost': (boost, 2),
    'slide': (slide, 1), 'hurt': (hurt, 2), 'spawn': (spawn, 2), 'switch': (switch, 1),
    'overdrive': (overdrive, 1), 'overdrive_end': (overdrive_end, 1), 'wind': (wind, 1),
    'shot_buzzer': (shot_buzzer, 4), 'shot_longshot': (shot_longshot, 2), 'longshot_hit': (longshot_hit, 2), 'pump': (pump, 1), 'bolt': (bolt, 1),
    'scope_in': (scope_in, 1), 'quickscope': (quickscope, 2), 'zap': (zap, 3), 'bar_tick': (bar_tick, 2),
    'hum': (hum, 1), 'slash': (slash, 2), 'parry': (parry, 2), 'reflect': (reflect, 2),
    'punch': (punch, 2), 'throw': (throw, 3), 'splat': (splat, 3),
    'chip': (chip, 4), 'token': (token, 1), 'round_start': (round_start, 1), 'round_clear': (round_clear, 1),
    'flame': (flame, 4), 'poison': (poison, 2), 'convert': (convert, 2), 'steal': (steal, 2), 'buy': (buy, 2),
    'unlock': (unlock, 1), 'deny': (deny, 1), 'reload': (reload, 2), 'empty': (empty, 1),
    'lock': (lock, 3), 'snipe': (snipe, 2), 'snap': (snap, 3), 'growl': (growl, 2), 'chime': (chime, 3),
    'dig': (dig, 2), 'stick': (stick, 2), 'beep': (beep, 3),
    'glug': (glug, 2), 'whack': (whack, 1), 'heartbeat': (heartbeat, 1), 'giggle': (giggle, 1),
    'catch': (catch, 1), 'beacon': (beacon, 1), 'roar': (roar, 1),
    'tier': (tier, 2), 'deflate': (deflate, 1), 'tick': (tick, 4), 'slam': (slam, 1), 'mult': (mult, 2),
    'music_bed': (music_bed, 1), 'music_drums': (music_drums, 1), 'music_arp': (music_arp, 1),
    'music_lead': (music_lead, 1),
}
MUSIC = ('music_bed', 'music_drums', 'music_arp', 'music_lead')     # in the order they come in


def ensure(folder):
    """Write any missing WAV files and return {name: path}."""
    folder = Path(folder) / VERSION
    folder.mkdir(parents=True, exist_ok=True)
    paths = {}
    for name, (recipe, _) in SOUNDS.items():
        path = folder / f'{name}.wav'
        if not path.exists():
            samples = np.clip(recipe() * 0.8, -1, 1)
            with wave.open(str(path), 'wb') as f:
                f.setnchannels(1)
                f.setsampwidth(2)
                f.setframerate(RATE)
                f.writeframes((samples * 32767).astype('<i2').tobytes())
        paths[name] = path
    return paths
