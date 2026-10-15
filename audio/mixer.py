from pathlib import Path

from panda3d.core import Filename
from ursina import application

from audio import synth
from data import tuning as T

SFX_FOLDER = Path(__file__).resolve().parent.parent / 'assets' / 'sfx'


class Sfx:
    """Plays the generated sounds. Each sound has a few voices so repeats can overlap."""

    def __init__(self, mute=False):
        self.mute = mute
        self.volume = T.MASTER_VOLUME
        self.voices = {}
        self.next_voice = {}
        self.wind = None
        self.hum = None
        self.music = []             # the layers, all looping together from the start
        self.music_level = [0.0] * len(synth.MUSIC)
        self.music_target = [0.0] * len(synth.MUSIC)
        if mute:
            return
        loader = application.base.loader
        for name, path in synth.ensure(SFX_FOLDER).items():
            count = synth.SOUNDS[name][1]
            self.voices[name] = [loader.loadSfx(Filename.fromOsSpecific(str(path))) for _ in range(count)]
            self.next_voice[name] = 0
        self.wind = self.start_loop('wind')
        self.hum = self.start_loop('hum')
        # started in the same frame and all the same length, the layers stay in step
        self.music = [self.start_loop(name) for name in synth.MUSIC]

    def start_loop(self, name):
        sound = self.voices[name][0]
        sound.setLoop(True)
        sound.setVolume(0)
        sound.play()
        return sound

    def play(self, name, volume=1.0, pitch=1.0):
        if self.mute:
            synth.SOUNDS[name]      # a sound that doesn't exist fails here as it would out loud
            return
        voices = self.voices[name]
        i = self.next_voice[name]
        self.next_voice[name] = (i + 1) % len(voices)
        sound = voices[i]
        sound.setVolume(volume * self.volume)
        sound.setPlayRate(pitch)
        sound.play()

    def set_wind(self, amount):
        """amount is 0-1: how fast the player is going."""
        if self.wind is None:
            return
        self.wind.setVolume(amount * amount * 0.9 * self.volume)
        self.wind.setPlayRate(0.7 + 0.9 * amount)

    def set_hum(self, amount):
        """amount is 0-1: how strongly the Overdrive electricity is buzzing."""
        if self.hum is not None:
            self.hum.setVolume(amount * 0.5 * self.volume)

    def set_music(self, tier, playing=True, duck=1.0):
        """Which music layers should be up: each comes in at its chain tier (MUSIC_LAYERS).
        Nothing plays unless `playing`; `duck` turns the lot down, under a menu."""
        for i, start in enumerate(T.MUSIC_LAYERS):
            self.music_target[i] = duck if playing and tier >= start else 0.0

    def update_music(self, dt):
        """Fade each layer toward where set_music wants it. A layer comes in quickly, on the
        kill that earned it, and goes out slowly."""
        for i, target in enumerate(self.music_target):
            level = self.music_level[i]
            rate = dt / (0.25 if target > level else T.MUSIC_FADE)
            level = min(target, level + rate) if target > level else max(target, level - rate)
            self.music_level[i] = level
            if i < len(self.music):
                self.music[i].setVolume(level * T.MUSIC_VOLUME * self.volume)
