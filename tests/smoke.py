"""Headless check of movement, weapons, enemies, sound files, the menu, the levels and the upgrade
shop. Run: py tests/smoke.py"""
import json
import sys
import wave
from math import atan2, degrees
from pathlib import Path
from tempfile import TemporaryDirectory
from time import perf_counter

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from panda3d.core import ClockObject
from ursina import Vec3, camera, held_keys, mouse, raycast

import main
from audio import synth
from audio.mixer import SFX_FOLDER, Sfx
from data import controls
from data import tuning as T
from data.levels import LEVELS
from data.progress import Progress
from data.settings import Settings
from game import mods
from fx import pixels as fxpixels
from game.foes.cave import HANG
from game.foes.base import MODEL_SCALE
from game.maps.blender import polar, roof_height
from ui import menus, shop

# the player's own settings.json and progress.json are neither read nor written here
scratch = TemporaryDirectory()
settings_file = Path(scratch.name) / 'settings.json'
app = main.build(mute=True, settings=Settings(settings_file), window_type='offscreen')
clock = ClockObject.getGlobalClock()
clock.setMode(ClockObject.MNonRealTime)
clock.setDt(1 / 60)

s = app.session
p, arena, enemies, arsenal = s.player, s.map, s.enemies, s.arsenal
s.juice.hitstop_enabled = False
s.director.auto = False     # no level starts by itself: each check sets up its own enemies
s.director.hearts = False   # nor does the runaway heart get out, but where it is tested
s.director.beacons = False  # and the miniboss beacon is only offered where it is tested
# astronauts are all one size and keep their feet on the deck, except in the checks of sizes and hops
T.ASTRO_SIZE = T.GOLD_SIZE = (1.0, 1.0)
T.HOP_EVERY = (1e9, 1e9)
arsenal.endless = True      # and no weapon runs dry, except in the checks of ammunition
spare_chips, T.SPARE_AMMO_CHIPS = T.SPARE_AMMO_CHIPS, 0     # so a crate nobody needs does not blur the chip counts
results = []


def run(seconds):
    for _ in range(int(seconds * 60)):
        app.step()


def keys(**down):
    for k in ('w', 'a', 's', 'd', 'left control', 'c'):
        held_keys[k] = 0
    for k, v in down.items():
        held_keys[k.replace('_', ' ')] = v


def place(pos, yaw=0, pitch=0):
    p.position = pos
    p.rotation_y = yaw
    p.pivot.rotation_x = pitch
    p.vel = Vec3(0, 0, 0)
    p.grounded = False
    p.sliding = False
    p.air_jumps = T.AIR_JUMPS
    p.dash_charges = T.DASH_CHARGES
    p.hp = T.PLAYER_HP
    p.invulnerable = 0
    # keep the bar and gates out of unrelated checks
    arena.knock_cooldown = 99
    p.boost_cooldown = 99


def clear_enemies():
    enemies.clear()
    s.pickups.clear()
    s.clouds.clear()


def frozen(x, z, kind='brawler', green=False):
    """An astronaut that stands where it is put."""
    enemy = enemies.spawn(kind, x, z, green)
    enemy.spawning = 0
    enemy.pause = 999
    return enemy


def check(name, ok, detail):
    results.append(ok)
    print(f"{'PASS' if ok else 'FAIL'}  {name}: {detail}")


def down_height(point):
    return raycast(Vec3(point.x, 12, point.z), Vec3(0, -1, 0), distance=40).world_point.y      # from under the roof


# ---------------- movement ----------------

keys()
run(0.5)
check('settle', p.grounded and abs(p.y) < 0.01, f'y={p.y:.3f} grounded={p.grounded}')

lo, hi, top = down_height(polar(38.5, 0)), down_height(polar(49.5, 0)), down_height(polar(52, 0))
check('ramp shape', abs(lo - 0.15) < 0.1 and abs(hi - 3.35) < 0.1 and abs(top - 3.5) < 0.01,
      f'low={lo:.2f} high={hi:.2f} balcony={top:.2f}')

worst = 0
for radius, angle in ((20, 10), (40, 0), (45, 90), (48, 181), (44, 20), (55, 0), (55, 100), (55, 45), (30, 270)):
    at = polar(radius, angle)
    worst = max(worst, abs(down_height(at) - arena.ground_height(at.x, at.z, 10)))
check('ground_height matches colliders', worst < 0.12, f'largest_difference={worst:.3f}')

place(polar(20, 200), yaw=90)
keys(w=1)
run(1.5)
check('run', abs(p.flat_speed - T.RUN_SPEED) < 0.3, f'speed={p.flat_speed:.2f} rush={p.rush.value:.0f}')

place(polar(56, 22), yaw=22)
keys(w=1)
run(2)
r = (p.x ** 2 + p.z ** 2) ** 0.5
check('outer wall', r < 60 - T.PLAYER_RADIUS + 0.05, f'radius={r:.2f}')

place(polar(20, 200))
keys()
run(0.3)
p.input('space')
peak = 0
for _ in range(60):
    app.step()
    peak = max(peak, p.y)
check('jump', 1.9 < peak < 2.2, f'peak={peak:.2f}')
run(0.5)
p.input('space')
run(0.25)
p.input('space')
peak2 = 0
for _ in range(90):
    app.step()
    peak2 = max(peak2, p.y)
check('double jump', peak2 > peak + 1 and p.grounded, f'peak={peak2:.2f} grounded={p.grounded}')

place(polar(20, 200), yaw=90)
run(0.3)
p.input('left shift')
app.step()
check('dash', abs(p.flat_speed - T.DASH_SPEED) < 0.5 and p.dash_charges == 1,
      f'speed={p.flat_speed:.1f} charges={p.dash_charges}')
run(0.5)

place(polar(20, 200), yaw=90)
run(0.3)
p.dash_recharge = 0.0
p.input('left shift')
p.input('left shift')
empty = p.dash_charges
run(2 * T.DASH_RECHARGE + 0.1)
check('dash recharge', empty == 0 and p.dash_charges == T.DASH_CHARGES, f'after_use={empty} now={p.dash_charges}')

coasted = []
for held in ({}, {'s': 1}):
    place(polar(26, 200), yaw=290)
    keys()
    run(0.3)
    p.vel = p.forward * 40
    keys(**held)
    run(0.25)
    coasted.append(p.flat_speed)
check('coasting sheds speed, back brakes harder', 15 < coasted[0] < 25 and coasted[1] < T.RUN_SPEED,
      f'no_keys={coasted[0]:.1f} holding_back={coasted[1]:.1f} after 0.25s from 40')
keys()

place(polar(20, 200), yaw=90)
keys(w=1)
run(1)
keys(w=1, left_control=1)
run(0.1)
check('slide', p.sliding and p.flat_speed > T.RUN_SPEED + 3 and p.pivot.y < 1.4,
      f'sliding={p.sliding} speed={p.flat_speed:.1f} eye={p.pivot.y:.2f}')

place(polar(36, 0), yaw=0)
keys(w=1)
run(1.6)
check('ramp walk', abs(p.y - 3.5) < 0.05 and p.grounded, f'y={p.y:.2f} grounded={p.grounded}')

place(polar(53, 45, 0.5))
keys()
top = 0
for _ in range(120):
    app.step()
    top = max(top, p.y)
check('jump pad', top > 5.5, f'peak={top:.2f}')

place(polar(59.35, 45, 2), yaw=45)
keys()
p.vel = polar(8, 45)
app.step()
p.input('space')
app.step()
outward = p.vel.x * polar(1, 45).x + p.vel.z * polar(1, 45).z
check('wall-kick', outward < -5 and p.vel.y > 8 and p.air_jumps == 1,
      f'radial_speed={outward:.1f} vy={p.vel.y:.1f} air_jumps={p.air_jumps}')
check('one kick per wall', not p.can_wall_kick(), f'can_kick_again={p.can_wall_kick()}')

place(polar(39, 45), yaw=45)
keys(w=1)
run(1)
d = ((p.x - polar(44, 45).x) ** 2 + (p.z - polar(44, 45).z) ** 2) ** 0.5
check('pillar', d >= 1.5 + T.PLAYER_RADIUS - 0.05, f'distance_from_pillar_centre={d:.2f}')

place(Vec3(6, 0, 0))
keys()
arena.knock_cooldown = 0
thrown = False
for _ in range(400):
    app.step()
    if p.vel.y > 5:
        thrown = True
        break
check('bar knock', thrown, f'thrown={thrown} speed={p.speed:.1f}')

place(polar(26, 25), yaw=115)
keys(w=1)
run(0.8)
p.boost_cooldown = 0
fastest = 0
for _ in range(120):
    app.step()
    fastest = max(fastest, p.flat_speed)
check('boost gate', fastest > T.RUN_SPEED + T.GATE_BOOST - 1, f'top_speed={fastest:.1f}')

# a bot circling the loop lane with hops, dashes and gates
place(polar(26, 200), yaw=290)
p.boost_cooldown = 0
keys(w=1)
run(0.5)
best = total = fastest = 0
samples = []
for i in range(1800):
    r = (p.x ** 2 + p.z ** 2) ** 0.5
    correction = max(-40, min(40, (r - 26) * 6))
    p.rotation_y = degrees(atan2(p.x, p.z)) + 90 + correction
    if p.dash_charges >= 1 and p.flat_speed < 30:
        p.input('left shift')
    if p.grounded:
        p.input('space')
    app.step()
    best = max(best, p.rush.overdrive_time)
    total += p.rush.overdrive / 60
    fastest = max(fastest, p.speed)
    if i % 180 == 0:
        samples.append(f'{p.flat_speed:.0f}/{p.rush.value:.0f}')
check('overdrive reachable', best > 5, f'longest={best:.1f}s total={total:.1f}s of 30s top_speed={fastest:.1f}')
print('   speed/rush every 3s:', ' '.join(samples))

place(polar(26, 200), yaw=290)
p.boost_cooldown = 0
keys(w=1)
run(0.5)
total = fastest = 0
speeds = []
for i in range(1800):
    r = (p.x ** 2 + p.z ** 2) ** 0.5
    p.rotation_y = degrees(atan2(p.x, p.z)) + 90 + max(-40, min(40, (r - 26) * 6))
    if p.dash_charges >= 1 and p.flat_speed < 30:
        p.input('left shift')
    app.step()
    total += p.rush.overdrive / 60
    fastest = max(fastest, p.speed)
    speeds.append(p.flat_speed)
print(f'   running-only bot: average_speed={sum(speeds) / len(speeds):.1f} top_speed={fastest:.1f} '
      f'overdrive={total:.1f}s of 30s')

# ---------------- sound ----------------

paths = synth.ensure(SFX_FOLDER)
lengths = {}
for name, path in paths.items():
    with wave.open(str(path)) as f:
        lengths[name] = f.getnframes() / f.getframerate()
check('sound files', len(paths) == len(synth.SOUNDS) and all(v > 0.03 for v in lengths.values()),
      f'{len(paths)} files, {min(lengths.values()):.2f}-{max(lengths.values()):.2f}s')
real = Sfx()
real.set_wind(0)
voices = real.voices['hit']
if main.application.base.sfxManagerList[0].isValid():
    check('sound loads', voices[0] is not voices[1] and voices[0].length() > 0.03 and real.wind.length() > 1.5,
          f'hit={voices[0].length():.2f}s wind={real.wind.length():.2f}s separate_voices={voices[0] is not voices[1]}')
else:
    print('SKIP  sound loads: no audio output device is available right now')
real.wind.stop()

# ---------------- enemies and weapons ----------------

place(Vec3(20, 0, 0), yaw=0)
keys()
run(0.3)
enemy = enemies.spawn('brawler', 20, 16, green=False)
start = 16.0
run(4)
gap = ((enemy.x - p.x) ** 2 + (enemy.z - p.z) ** 2) ** 0.5
check('brawler runs in and punches', p.hp < T.PLAYER_HP and gap < start, f'hp={p.hp} gap={gap:.1f}')
clear_enemies()

place(Vec3(20, 0, 0), yaw=0)
run(0.3)
thrower = enemies.spawn('thrower', 20, 6, green=False)
thrower.hit_cooldown = 99       # no throwing yet
run(3)
gap = ((thrower.x - p.x) ** 2 + (thrower.z - p.z) ** 2) ** 0.5
check('thrower keeps its distance', T.THROWER_NEAR - 1 < gap < T.THROWER_FAR + 1 and p.hp == T.PLAYER_HP,
      f'gap={gap:.1f} after starting 6 m away')

thrower.hit_cooldown = 0
thrown = False
for _ in range(240):
    app.step()
    thrown = thrown or bool(enemies.markers)
    if p.hp < T.PLAYER_HP:
        break
check('marker hits a standing player', thrown and p.hp == T.PLAYER_HP - T.MARKER_DAMAGE and not enemies.markers,
      f'thrown={thrown} hp={p.hp} still_flying={len(enemies.markers)}')

clear_enemies()
place(Vec3(-20, 0, 0), yaw=0)
thrower = enemies.spawn('thrower', -2, 12, green=False)
thrower.hit_cooldown = 0
keys(w=1)
thrown = False
for _ in range(160):
    app.step()
    thrown = thrown or bool(enemies.markers)
keys()
check('running dodges a marker', thrown and p.hp == T.PLAYER_HP, f'thrown={thrown} hp={p.hp} speed={p.flat_speed:.1f}')

clear_enemies()
place(Vec3(20, 0, 0))
thrower = frozen(20, 30, 'thrower')
s.particles.age[:] = s.particles.life       # ink from the pens above is still fading
confetti = int((s.particles.age < s.particles.life).sum())
pen = enemies.throw(thrower, Vec3(-10, 3, 20), Vec3(0, 2, 10), thrower.ink)
for _ in range(120):
    app.step()
    if not pen.live:
        break
check('marker splats on the deck', not pen.live and not enemies.markers and p.hp == T.PLAYER_HP
      and int((s.particles.age < s.particles.life).sum()) > confetti, f'landed={not pen.live} at z={pen.pos.z:.1f}')
clear_enemies()


def aim_at(target):
    to = target - (p.position + Vec3(0, T.EYE_HEIGHT, 0))
    p.rotation_y = degrees(atan2(to.x, to.z))
    p.pivot.rotation_x = -degrees(atan2(to.y, (to.x ** 2 + to.z ** 2) ** 0.5))
    app.step()


place(Vec3(20, 0, 0))
run(0.3)
enemy = frozen(20, 10)
aim_at(enemy.centre)
arsenal.select(0)
p.rush.value = 0.0
shots = 0
kills_before = s.kills
while enemy.alive and shots < 20:
    arsenal.fire()
    shots += 1
expected = -(-T.ASTRO_HP // (T.POPPER_DAMAGE * T.RUSH_DAMAGE_MIN))
live_particles = int((s.particles.age < s.particles.life).sum())
check('popper kills', s.kills == kills_before + 1 and shots == expected and live_particles > 30,
      f'shots={shots} expected={expected:.0f} kills={s.kills - kills_before} particles={live_particles}')

miss_before = live_particles
p.pivot.rotation_x = 30
app.step()
arsenal.fire()
check('miss sparks on floor', int((s.particles.age < s.particles.life).sum()) > miss_before, 'sparks emitted')

place(Vec3(20, 0, 0))
run(0.3)
p.pivot.rotation_x = 0
app.step()
arsenal.select(1)
arsenal.fire()
back = -p.vel.z
check('scatter recoil', abs(back - T.SCATTER_RECOIL) < 1.5, f'backward_speed={back:.1f}')
for _ in range(4):
    arsenal.fire()
check('recoil cap', abs(p.flat_speed - T.SCATTER_MAX_SPEED) < 0.1, f'speed after 5 shots={p.flat_speed:.1f}')

place(Vec3(20, 0, 0))
run(0.3)
p.pivot.rotation_x = 89
app.step()
arsenal.fire()
top = 0
for _ in range(150):
    app.step()
    top = max(top, p.y)
check('scatter jump', top > 10, f'peak={top:.1f}')

place(Vec3(20, 12, 0))
p.pivot.rotation_x = 89
app.step()
p.vel = Vec3(0, -15, 0)
arsenal.fire()
check('scatter lifts out of a fall', p.vel.y > T.SCATTER_RECOIL - 1, f'vy={p.vel.y:.1f}')

clear_enemies()
place(Vec3(20, 0, 0))
run(0.3)
enemy = frozen(20, 4)
aim_at(enemy.centre)
arsenal.fire()
check('scatter point blank', not enemy.alive or enemy.hp < T.ASTRO_HP - 25,
      f'alive={enemy.alive} hp={enemy.hp if enemy.alive else 0:.0f}')

clear_enemies()
place(Vec3(20, 0, 0))
run(0.3)
enemy = frozen(20, 14)
aim_at(enemy.centre + Vec3(0, 0.6, 0))
arsenal.select(2)
arsenal.fire()
run(1.0)
check('rocket blast', enemy.hp < T.ASTRO_HP and not any(r['live'] for r in arsenal.rockets),
      f'hp={enemy.hp:.0f} of {T.ASTRO_HP}')

clear_enemies()
place(Vec3(20, 0, 0))
run(0.5)
p.pivot.rotation_x = -25        # up and away, so nothing is in the rocket's path
app.step()
arsenal.cooldown = 0
arsenal.fire()
back = -(p.vel.x * camera.forward.x + p.vel.y * camera.forward.y + p.vel.z * camera.forward.z)
rocket = next(r for r in arsenal.rockets if r['live'])
launch, heading = Vec3(*rocket['pos']), rocket['vel'].normalized()
for _ in range(12):
    app.step()
flown = rocket['pos'] - launch
drift = (flown - heading * flown.dot(heading)).length()
check('rocket flies straight', rocket['live'] and drift < 0.01 and abs(flown.length() - T.ROCKET_SPEED * 0.2) < 0.5,
      f'flown={flown.length():.1f}m drift={drift:.3f}m')
check('rocket recoil', abs(back - T.ROCKET_RECOIL) < 1.5 and abs(T.ROCKET_RECOIL - 1.2 * 28) < 0.01
      and abs(T.SCATTER_RECOIL - 1.1 * 28) < 0.01, f'thrown_back={back:.1f} scatter={T.SCATTER_RECOIL:.1f}')
run(T.ROCKET_LIFE + 0.2)
check('rocket burns out', not any(r['live'] for r in arsenal.rockets), f'live={sum(r["live"] for r in arsenal.rockets)}')

place(Vec3(20, 0, 0))
run(0.5)
p.pivot.rotation_x = 85         # straight at your own feet
app.step()
arsenal.cooldown = 0
arsenal.fire()
run(0.2)
lost = T.PLAYER_HP - p.hp
check('own rocket hurts', T.ROCKET_SELF_DAMAGE * 0.4 <= lost <= T.ROCKET_SELF_DAMAGE and p.vel.y > 20,
      f'hp_lost={lost:.0f} of up to {T.ROCKET_SELF_DAMAGE} vy={p.vel.y:.0f}')
place(Vec3(20, 0, 0))
run(0.6)
s.explode(p.position + Vec3(0, 0, T.ROCKET_RADIUS + 3), T.ROCKET_RADIUS, T.ROCKET_DAMAGE, arsenal.weapon.colour,
          self_damage=T.ROCKET_SELF_DAMAGE)
far_hp = p.hp
s.explode(p.centre, T.OVERDRIVE_KILL_BLAST_RADIUS, T.OVERDRIVE_KILL_BLAST_DAMAGE, arsenal.weapon.colour, quiet=True)
check('only close rockets hurt you', far_hp == T.PLAYER_HP and p.hp == T.PLAYER_HP,
      f'outside_radius_hp={far_hp:.0f} overdrive_blast_hp={p.hp:.0f}')

place(Vec3(20, 0, 0))
run(0.5)
arsenal.select(0)
arsenal.cooldown = 0
arsenal.fire()
drawn = [t for t in arsenal.tracers if t['live']]
slug_out = bool(drawn) and drawn[0]['slug'].enabled and drawn[0]['trail'].enabled
run(0.5)
starred = any(i['age'] > 0 for i in arsenal.impacts)
check('bullets are drawn', slug_out and starred and not any(t['live'] for t in arsenal.tracers)
      and not any(i['star'].enabled for i in arsenal.impacts),
      f'slug={slug_out} impact_star={starred} still_live={sum(t["live"] for t in arsenal.tracers)}')
check('big guns', abs(arsenal.weapons[2].view.scale_x - 1.2) < 1e-4 and abs(arsenal.weapons[4].view.scale_x - 1.2) < 1e-4,
      f'boomer={arsenal.weapons[2].view.scale_x} longshot={arsenal.weapons[4].view.scale_x}')

clear_enemies()
place(Vec3(20, 0, 0))
run(0.5)
near, far = frozen(20, 8), frozen(20, 13)
aim_at(near.centre)
arsenal.select(0)
arsenal.fire()
one = (near.hp < T.ASTRO_HP, far.hp < T.ASTRO_HP)
p.rush.value, p.rush.overdrive = 100.0, True
arsenal.fire()
check('pierce only in overdrive', one == (True, False) and far.hp < T.ASTRO_HP,
      f'normal_shot_hit={one} overdrive_far_hp={far.hp:.0f}')

check('five weapons', [w.name for w in arsenal.weapons] == ['POPPER', 'SCATTER', 'BOOMER', 'BUZZER', 'LONGSHOT']
      and all(len(w.view.children) >= 2 for w in arsenal.weapons), ' '.join(w.name for w in arsenal.weapons))

clear_enemies()
place(Vec3(20, 0, 0))
run(1.5)
p.pivot.rotation_x = -30
arsenal.select(3)
run(0.3)
shots = 0
for _ in range(60):
    app.step()
    if arsenal.cooldown <= 0:
        arsenal.fire()
        shots += 1
check('buzzer rate', 15 <= shots <= 18 and shots > 1 / T.POPPER_INTERVAL + 5, f'{shots} shots in 1s')

clear_enemies()
place(Vec3(20, 0, 0))
run(0.5)
near, far = frozen(20, 10), frozen(20, 16)
aim_at(near.centre)
arsenal.select(4)
run(0.3)
p.rush.value = 0.0
kills_before = s.kills
wide = camera.fov
held_keys['right mouse'] = 1
run(T.LONGSHOT_SCOPE_TIME + 0.05)
quick = arsenal.quick_ready
arsenal.fire()
check('quickscope', quick and s.kills == kills_before + 2 and camera.fov < wide - 30
      and arsenal.cooldown < T.LONGSHOT_INTERVAL * 0.6 and s.hud.quick_time > 0,
      f'window_open={quick} kills={s.kills - kills_before} fov={wide:.0f}->{camera.fov:.0f} '
      f'cooldown={arsenal.cooldown:.2f}')

run(1.5)
enemy = frozen(20, 10)
p.rush.value = 0.0
quick = arsenal.quick_ready
arsenal.fire()
check('held scope is not a quickscope', not quick and not enemy.alive
      and abs(arsenal.cooldown - T.LONGSHOT_INTERVAL) < 0.05,
      f'window_open={quick} killed={not enemy.alive} cooldown={arsenal.cooldown:.2f}')
held_keys['right mouse'] = 0
run(1.0)     # long enough for the shot's view kick to settle
check('unscope', arsenal.scope == 0 and abs(camera.fov - wide) < 3, f'scope={arsenal.scope:.2f} fov={camera.fov:.0f}')

# ---------------- katana and parry ----------------

katana = s.katana


def still(x, z, green):
    enemy = frozen(x, z)
    enemy.green = green
    return enemy


def slash():
    katana.cooldown = 0
    p.rush.value = 0.0
    katana.input(T.KEY_KATANA)


cut = T.KATANA_DAMAGE * T.RUSH_DAMAGE_MIN
clear_enemies()
place(Vec3(20, 0, 0))
run(1.5)
p.drive = 0
front, behind = still(20, 3, False), still(20, -3, False)
slash()
busy = katana.busy
check('katana slash', abs(front.hp - (T.ASTRO_HP - cut)) < 0.01 and behind.hp == T.ASTRO_HP and p.drive == 0 and busy,
      f'front_hp={front.hp:.1f} behind_hp={behind.hp:.1f} drive={p.drive} gun_stowed={arsenal.stow if busy else 0}')
run(T.KATANA_SLASH_TIME + 0.3)
check('katana puts itself away', not katana.busy and not katana.hand.enabled and katana.stow == 0,
      f'busy={katana.busy} stow={katana.stow:.2f}')

clear_enemies()
place(Vec3(20, 0, 0))
green = still(20, 3, True)
slash()
check('slash parries a green enemy', abs(green.hp - (T.ASTRO_HP - cut * T.KATANA_PARRY_DAMAGE)) < 0.01
      and green.stun > 0 and green.vz > 0 and p.drive == 1,
      f'hp={green.hp:.1f} stun={green.stun:.2f} thrown_back={green.vz:.1f} drive={p.drive}')

def puncher():
    """A green brawler in front of the player whose punch lands on its next update."""
    brawler = still(20, 1.2, True)
    brawler.pause = 0
    brawler.wind = 1 / 120
    return brawler


clear_enemies()
place(Vec3(20, 0, 0))
run(0.6)
biter = puncher()
run(0.1)
unparried = T.PLAYER_HP - p.hp
clear_enemies()
place(Vec3(20, 0, 0))
run(0.6)
biter = puncher()
katana.struck.clear()
katana.age = 0.0        # blade already moving when the punch lands
katana.hand.enabled = True
biter.update(1 / 60, p, arena, enemies.alive)
check('green punch: parried or punished', unparried == T.BRAWLER_DAMAGE * T.GREEN_DAMAGE_MULTIPLIER
      and p.hp == T.PLAYER_HP and biter.stun > 0 and p.drive == 2,
      f'damage_without_parry={unparried:.0f} hp_with_parry={p.hp:.0f} stun={biter.stun:.2f} drive={p.drive}')


class Shot:
    """Stand-in for the projectiles another system will provide."""

    def __init__(self, pos, vel, owner):
        self.pos, self.vel, self.owner = Vec3(*pos), Vec3(*vel), owner
        self.green, self.friendly, self.target, self.damage = True, False, p, 10

    def fly(self, dt):      # a tracker: always turns toward its target
        if self.target is not None:
            self.vel = (self.target.centre - self.pos).normalized() * self.vel.length()
        self.pos += self.vel * dt


clear_enemies()
place(Vec3(20, 0, 0))
run(0.6)
sender = still(20, 30, False)
eye = p.position + Vec3(0, T.EYE_HEIGHT, 0)
incoming, from_behind = Shot(eye + Vec3(0, 0, 2.5), (0, 0, -20), sender), Shot(eye + Vec3(0, 0, -2.5), (0, 0, 20), sender)
s.projectiles = [incoming, from_behind]
p.drive = 0
slash()
sender.x += 8       # the sender moves after the parry
for _ in range(120):
    incoming.fly(1 / 60)
gap = (incoming.pos - sender.centre).length()
check('parried tracker returns to sender', incoming.target is sender and incoming.friendly
      and abs(incoming.vel.length() - 20 * T.KATANA_REFLECT_SPEED) < 0.1 and gap < 1.5
      and from_behind.target is p and p.drive == 1,
      f'target_is_sender={incoming.target is sender} speed={incoming.vel.length():.0f} gap={gap:.1f} '
      f'behind_untouched={from_behind.target is p}')
s.projectiles = enemies.markers

# the real thing: a green pen, slashed out of the air, goes back and floors the astronaut who threw it
clear_enemies()
place(Vec3(20, 0, 0))
run(0.6)
sender = frozen(20, 30, 'thrower', green=True)
p.drive = 0
kills = s.kills
pen = enemies.throw(sender, eye + Vec3(0, 0, 2.5), Vec3(0, 0, -20), sender.ink)
slash()
sent_back = pen.friendly and pen.target is sender
sender.x += 8
run(1.5)
check('parried marker floors its thrower', sent_back and not sender.alive and not pen.live and s.kills == kills + 1
      and p.hp == T.PLAYER_HP and p.drive == 1,
      f'sent_back={sent_back} thrower_alive={sender.alive} hp={p.hp} drive={p.drive}')

clear_enemies()
place(Vec3(20, 0, 0))
run(0.6)
sender = frozen(20, 30, 'thrower', green=True)
pen = enemies.throw(sender, eye + Vec3(0, -0.6, 1.2), Vec3(0, 0, -20), sender.ink)
run(0.2)
check('green marker that lands hits harder', p.hp == T.PLAYER_HP - T.MARKER_DAMAGE * T.GREEN_DAMAGE_MULTIPLIER
      and not pen.friendly, f'hp={p.hp}')

p.drive = T.DRIVE_MAX
s.on_parry(Vec3(20, 1, 3))
check('drive caps', p.drive == T.DRIVE_MAX and len(s.hud.bar.drive_pips) == T.DRIVE_MAX, f'drive={p.drive} of {T.DRIVE_MAX}')
p.drive = 0

# ---------------- speed bar ----------------

clear_enemies()
bar = s.hud.bar
for _ in range(120):
    place(polar(30, 200))
    p.vel = Vec3(0, 0, 45)
    app.step()
lit = sum(b.enabled for b in bar.bolts)
check('speed bar overdrive', bar.shown > 0.97 and bar.overdrive and bar.multiplier.text == 'x2.00',
      f'fill={bar.shown:.2f} multiplier={bar.multiplier.text} speed={bar.number.text} bolts={lit}')
keys()
place(polar(30, 200))
run(4)
check('speed bar drains', abs(bar.shown - p.rush.fraction) < 0.02 and bar.shown < 0.2 and not bar.overdrive
      and not any(b.enabled for b in bar.bolts),
      f'fill={bar.shown:.2f} rush={p.rush.fraction:.2f} speed={p.speed:.1f} bolts={sum(b.enabled for b in bar.bolts)}')

# ---------------- menu ----------------

# an offscreen buffer has no cursor, so stand in for the three things the menu asks of the mouse
pointer = [0.0, 0.0]
type(mouse).locked = property(lambda m: getattr(m, '_locked', False), lambda m, value: setattr(m, '_locked', value))
type(mouse).x = property(lambda m: pointer[0])
type(mouse).y = property(lambda m: pointer[1])


def click(x, y):
    pointer[:] = x, y
    app.input('left mouse down')
    app.step()
    app.input('left mouse up')


clear_enemies()
keys()
place(polar(30, 200))
run(0.2)
menu = s.menu = menus.Menu(s)
menu.open()
kills, spot = s.kills, Vec3(p.position)
held_keys['w'] = 1
run(0.5)
held_keys['w'] = 0
app.input('escape', True)
check('menu freezes the match', main.application.paused and menu.is_open and not mouse.locked
      and not s.hud.enabled and (p.position - spot).length() < 0.001,
      f'paused={main.application.paused} moved={(p.position - spot).length():.3f} still_open_after_esc={menu.is_open}')

click(menus.FIELD_X, menus.ROW_NAME)
for _ in range(len(s.settings.name)):
    app.input('backspace', True)
for character in 'zip <7>!':
    app.text_input(character)
app.input('backspace', True)
typing = menu.typing
app.input('enter', True)
check('menu name', typing and menu.is_open and s.settings.name == 'ZIP 7' and s.hud.tag.text == 'ZIP 7',
      f'name={s.settings.name!r} hud={s.hud.tag.text!r} open_after_enter={menu.is_open}')

click(menus.SWATCH_X + 5 * menus.SWATCH_STEP, menus.ROW_PAINT)
painted = [w.paint_hue for w in arsenal.weapons]
whole = all(len(w.view.children) >= 2 for w in arsenal.weapons)
click(menus.SWATCH_X, menus.ROW_PAINT)
stock = [w.paint_hue == w.hue for w in arsenal.weapons]
click(menus.SWATCH_X + 8 * menus.SWATCH_STEP, menus.ROW_PAINT)
check('menu colour', painted == [185] * 5 and whole and all(stock) and s.settings.hue == 325
      and arsenal.weapon.view.enabled, f'cyan={painted} classic_restores={all(stock)} now={s.settings.hue}')

pointer[:] = menus.TRACK_X + 0.25 * menus.TRACK_LENGTH, menus.ROW_VOLUME
app.input('left mouse down')
grabbed = s.sfx.volume
pointer[0] = menus.TRACK_X + 0.8 * menus.TRACK_LENGTH
app.step()
app.input('left mouse up')
pointer[0] = 5
app.step()
check('menu volume', grabbed == 0.25 and s.sfx.volume == 0.8 and menu.volume_text.text == '80%',
      f'click={grabbed} drag={s.sfx.volume} label={menu.volume_text.text} after_release={s.settings.volume}')

def rebind(action, key, raw=True):
    """Click an action's slot on the controls page, then press its new key."""
    click(*menu.slots[action][:2])
    app.input(key, raw)
    held_keys[key.replace(' down', '')] = 0     # and let it go


click(menus.CONTROLS_X, menus.ROW_PLAY)
shown = menu.page == 'controls' and menu.controls.enabled and not menu.main.enabled
bound = s.settings.keys
rebind('forward', 'i')
rebind('jump', 'f')                         # taken by the katana, so the two swap
rebind('weapon_1', 'scroll up', raw=False)  # taken by previous weapon
rebind('dash', 'right mouse down', raw=False)
check('rebinding', shown and (bound['forward'], T.KEY_FORWARD) == ('i', 'i')
      and (bound['jump'], bound['katana']) == ('f', 'space')
      and (T.KEYS_WEAPON[0], T.KEY_PREVIOUS_WEAPON) == ('scroll up', '1')
      and (T.KEY_DASH, T.KEY_SCOPE) == ('right mouse', 'left shift') and menu.slots['jump'][3].text == 'F',
      f"forward={bound['forward']} jump={bound['jump']} katana={bound['katana']} weapon_1={bound['weapon_1']} "
      f"previous={bound['weapon_previous']} dash={bound['dash']} scope={bound['scope']}")

rebind('fire', 'scroll down', raw=False)    # the wheel can't be held
wheel = bound['fire']
rebind('slide', T.KEY_SPAWN_MANY)           # kept for the debug key
click(*menu.slots['right'][:2])
waited = menu.waiting
app.input('escape', True)
check('rebinding refusals', (wheel, bound['slide'], bound['right']) == ('left mouse', 'left control', 'd')
      and waited == 'right' and menu.waiting is None and menu.page == 'controls' and menu.is_open,
      f"fire={wheel} slide={bound['slide']} right={bound['right']} esc_cancels={menu.waiting is None}")

click(menus.AIM_X + 0.8 * menus.AIM_LENGTH, menus.ROW_AIM)
saved = Settings(settings_file)
check('sensitivity', s.settings.sensitivity == 81 and T.MOUSE_SENSITIVITY == 81 and menu.aim_text.text == '81'
      and saved.sensitivity == 81 and saved.keys == bound,
      f'setting={s.settings.sensitivity} tuning={T.MOUSE_SENSITIVITY} saved={saved.sensitivity} '
      f'keys_saved={saved.keys == bound}')

app.input('escape', True)
back = menu.page == 'main' and menu.is_open
click(menus.PLAY_X, menus.ROW_PLAY)
saved = Settings(settings_file)
check('play starts the match', not main.application.paused and not menu.is_open and mouse.locked and s.hud.enabled
      and (saved.name, saved.hue, saved.volume) == ('ZIP 7', 325, 0.8),
      f'paused={main.application.paused} locked={mouse.locked} saved={(saved.name, saved.hue, saved.volume)}')

run(0.3)
held_keys['w'] = 1
run(0.3)
held_keys['w'] = 0
old_key = (p.position - spot).length()
held_keys['i'] = 1
run(0.3)
held_keys['i'] = 0
new_key = (p.position - spot).length()
keys()
run(0.5)
app.input('f', True)
app.step()
jumped = p.vel.y > 5
charges = p.dash_charges
app.input('right mouse down')
app.input('right mouse up')
s.katana.cooldown = 0
app.input('space', True)
arsenal.select(2)
app.input('scroll up')
first = arsenal.current
app.input('1', True)
check('rebound keys in the match', back and old_key < 0.01 and new_key > 1 and jumped
      and p.dash_charges == charges - 1 and s.katana.cooldown > 0 and (first, arsenal.current) == (0, 4)
      and s.hud.help.text.startswith('I A S D move   F jump'),
      f'w_moved={old_key:.2f} i_moved={new_key:.2f} f_jumps={jumped} right_click_dashes={p.dash_charges == charges - 1} '
      f'space_slashes={s.katana.cooldown > 0} wheel_then_1={(first, arsenal.current)}')

run(1.5)
place(polar(30, 200))
spot = Vec3(p.position)
app.input('escape', True)
click(menus.CONTROLS_X, menus.ROW_PLAY)
click(menus.DEFAULTS_X, menus.ROW_DONE)
restored = (s.settings.keys == controls.DEFAULT_KEYS and Settings(settings_file).keys == controls.DEFAULT_KEYS
            and (T.KEY_FORWARD, T.KEY_JUMP, T.KEYS_WEAPON[0], T.MOUSE_SENSITIVITY) == ('w', 'space', '1', 40))
click(menus.DONE_X, menus.ROW_DONE)
check('controls defaults', restored and menu.page == 'main' and menu.is_open,
      f'restored={restored} forward={T.KEY_FORWARD} sensitivity={T.MOUSE_SENSITIVITY} page={menu.page}')
app.input('escape', True)

app.input('escape', True)
reopened = menu.is_open and main.application.paused and menu.play_text.text == 'RESUME'
app.input('escape', True)
held_keys['w'] = 1
run(0.5)
held_keys['w'] = 0
check('escape pauses and resumes', reopened and not menu.is_open and (p.position - spot).length() > 1
      and s.kills == kills, f'reopened={reopened} open={menu.is_open} moved={(p.position - spot).length():.1f}')

# ---------------- levels and rounds ----------------

director, progress, pickups = s.director, s.progress, s.pickups


def wipe():
    """Kill everything in the arena the way a weapon would."""
    for enemy in list(enemies.alive):
        enemies.damage(enemy, 99999)


clear_enemies()
keys()
place(polar(30, 200))
p.invulnerable = 1e6
progress.cleared = progress.chips = progress.tokens = 0
director.start()
plans, most, states = [], [], []
for number in range(5):
    queue = list(director.queue)
    plans.append((len(queue), sum(kind == 'thrower' for kind, _, _ in queue),
                  sum(special == 'glow' for _, _, special in queue), sum(special == 'gold' for _, _, special in queue)))
    states.append((director.state, director.round, len(enemies.alive)))
    run(T.ROUND_INTRO + 0.05)
    crowd = 0
    for _ in range(3000):
        director.spawn_timer = 0        # no waiting between spawns
        app.step()
        crowd = max(crowd, len(enemies.alive))
        if director.state != 'fight':
            break
        if len(enemies.alive) >= director.alive_cap or not director.queue:
            wipe()
    most.append(crowd)
    if number < 4:
        run(T.ROUND_BREATHER + 0.05)
check('five rounds, throwers from the third', plans == [(10, 0, 2, 0), (14, 0, 3, 0), (18, 4, 3, 1), (24, 8, 4, 1),
                                                         (30, 12, 5, 2)]
      and states == [('intro', n, 0) for n in range(5)] and most == [5, 7, 8, 10, 12],
      f'(enemies, throwers, glowing, golden)={plans} most_alive={most}')

won = director.state
run(T.LEVEL_WON_PAUSE + 0.2)
tally = s.tally
tallied = (tally.is_open, s.shop.is_open, main.application.paused)
counted = []
for _ in range(900):            # it runs on real time, which the test's clock also steps
    app.step()
    counted.append(tally.step)
    if tally.done:
        break
stats = tally.stats
expected = round((stats['base'] + stats['style']) * (1 + T.TALLY_CHAIN_STEP * stats['best']))
lines = [label.text for label in tally.values]
tally.input('left mouse down')
check('a level ends on its tally: each line counts up in turn, the best chain multiplies them, then the shop',
      tallied == (True, False, True) and tally.done and counted == sorted(counted) and tally.score == expected
      and tally.final.text == f'{expected:,}' and stats['kills'] > 50 and all(lines) and not tally.is_open
      and s.shop.is_open, f'opened (tally, shop, paused)={tallied} lines={lines} (kills, points, style, best)='
      f"{(stats['kills'], stats['base'], stats['style'], stats['best'])} score={tally.score} expected={expected}")
saved = Progress(progress.path)
check('level clear opens the shop', won == 'won' and s.shop.is_open and main.application.paused and not mouse.locked
      and progress.cleared == 1 and director.state == 'idle',
      f'state={won} shop={s.shop.is_open} paused={main.application.paused} levels_cleared={progress.cleared}')
check('chips and keys are kept', progress.chips == 83 and progress.tokens == 4 and not pickups.live
      and (saved.chips, saved.cleared, saved.tokens) == (83, 1, 4),
      f'chips={progress.chips} keys={progress.tokens} on_disk={saved.chips} chips, {saved.tokens} keys, '
      f'{saved.cleared} level')

# ---------------- the shop ----------------

tab = shop.TAB_Y - shop.WEAPONS.index('BOOMER') * shop.TAB_STEP
click(shop.TAB_X, tab)
tiger, poison = mods.find('BOOMER', 'tiger'), mods.find('BOOMER', 'poison')
offered = s.shop.buttons['branch 0']['visible'] and s.shop.buttons['branch 1']['visible']
progress.tokens = 0
click(shop.CARD_X[0], shop.CARD_Y)
keyless = (progress.chips, dict(progress.unlocked), s.shop.note.text)
progress.tokens = 4
click(shop.CARD_X[0], shop.CARD_Y)
check('a branch costs a key and chips', offered and keyless == (83, {}, 'NO KEY: GOLDEN ENEMIES DROP THEM')
      and (progress.chips, progress.tokens) == (83 - T.BRANCH_COST, 3) and progress.unlocked == {'BOOMER': ['tiger']}
      and progress.branches == {'BOOMER': 'tiger'} and arsenal.weapons[2].name == 'TIGER'
      and s.hud.slots[2].text == '3  TIGER' and arsenal.weapons[2].view.enabled == (arsenal.current == 2),
      f'without_a_key={keyless} chips={progress.chips} keys={progress.tokens} unlocked={progress.unlocked} '
      f'slot_3={arsenal.weapons[2].name}')

before = mods.stat('BOOMER', 'damage')
click(*shop.node_at(tiger.nodes[0]))                # damage, level 1
raised = mods.stat('BOOMER', 'damage')
click(*shop.node_at(tiger.nodes[2]))                # rocket speed hangs from blast, which has no level yet
click(*shop.node_at(tiger.nodes[7]))                # the link needs the first node of both paths
locked = (progress.chips, s.shop.note.text)
click(*shop.node_at(tiger.nodes[1]))                # blast
click(*shop.node_at(tiger.nodes[0]))
saved = Progress(progress.path)
check('buying nodes of the tree', (before, raised) == (130, 142) and locked == (33, 'THE NODES BEFORE IT COME FIRST')
      and progress.chips == 8 and progress.nodes == {'BOOMER/tiger': {'claws': 2, 'roar': 1}}
      and mods.stat('BOOMER', 'radius') == 11.5
      and (saved.chips, saved.tokens, saved.unlocked, saved.branches, saved.nodes)
      == (8, 3, progress.unlocked, progress.branches, progress.nodes),
      f'damage={before}->{raised} after_locked_clicks={locked} chips={progress.chips} nodes={progress.nodes}')

click(*shop.node_at(tiger.nodes[0]))                # 22 chips, with 8 in hand
check('too few chips buys nothing', progress.chips == 8 and progress.nodes['BOOMER/tiger']['claws'] == 2
      and 'MORE CHIPS' in s.shop.note.text, f'chips={progress.chips} note={s.shop.note.text!r}')

click(shop.PLAIN_X, shop.CARD_Y)
plain = (arsenal.weapons[2].name, mods.stat('BOOMER', 'damage'), dict(progress.branches))
click(shop.CARD_X[1], shop.CARD_Y)                  # the other branch: a key in hand, but 8 chips
short = (progress.unlocked['BOOMER'], progress.tokens)
click(shop.CARD_X[0], shop.CARD_Y)
check('a branch can be put away and taken up again', plain == ('BOOMER', T.ROCKET_DAMAGE, {})
      and short == (['tiger'], 3) and arsenal.weapons[2].name == 'TIGER' and mods.stat('BOOMER', 'damage') == 154
      and (progress.chips, progress.tokens) == (8, 3),
      f'plain={plain} other_branch={short} back={arsenal.weapons[2].name} damage={mods.stat("BOOMER", "damage")}')

# a tree is the same shape for every branch: a root, two paths that end in a perk, and a link
shapes = {(weapon, of.id): [(n.at, len(n.costs), len(n.requires)) for n in of.nodes]
          for weapon, branches in shop.TREES.items() for of in branches}
perks = {name: [n.id for i, n in enumerate(of.nodes) if i in shop.PERKS] for (_, name), of in
         (((w, b.id), b) for w, bs in shop.TREES.items() for b in bs)}
check('every branch has a tree with two perks', len(shapes) == 10 and len({str(v) for v in shapes.values()}) == 1
      and all(len(v) == 8 for v in shapes.values()) and all(len(v) == 2 for v in perks.values()),
      f'branches={len(shapes)} perks={perks}')

old = Path(scratch.name) / 'old.json'
old.write_text(json.dumps({'chips': 50, 'cleared': 2, 'branches': {'LONGSHOT': 'semi'},
                           'nodes': {'LONGSHOT': {'damage': 5, 'interval': 1}},
                           'modifiers': {'BOOMER': {'damage': 2}}}), encoding='utf-8')
moved = Progress(old)
check('an old save keeps its branch and is paid back its upgrades', moved.chips == 50 + 100 + 10
      and moved.unlocked == {'LONGSHOT': ['semi']} and moved.branches == {'LONGSHOT': 'semi'} and moved.nodes == {}
      and moved.cleared == 2 and not hasattr(moved, 'modifiers'),
      f'chips={moved.chips} unlocked={moved.unlocked} nodes={moved.nodes}')
click(shop.GO_X, shop.ROW_GO)
check('next level leaves the shop', not s.shop.is_open and not main.application.paused and mouse.locked
      and s.hud.enabled and director.level == 2, f'shop={s.shop.is_open} paused={main.application.paused} '
      f'level={director.level}')

progress.cleared = len(LEVELS)      # the first level again, on the second lap round them all
director.start()
harder = (director.total, director.alive_cap, round(director.hp_scale, 2))
director.round = 2
place(polar(30, 200))
progress.chips += 5                 # picked up since the last save
kept = (progress.chips, progress.tokens, progress.cleared, dict(progress.unlocked), dict(progress.nodes))
p.take_damage(9999)
saved = Progress(progress.path)
check('later levels are harder; dying restarts the level and keeps the save', harder == (12, 7, 1.15)
      and director.round == 0 and director.state == 'intro' and p.hp == T.PLAYER_HP
      and (progress.chips, progress.tokens, progress.cleared, progress.unlocked, progress.nodes) == kept
      and (saved.chips, saved.tokens, saved.cleared, saved.unlocked, saved.nodes) == kept
      and arsenal.weapons[2].name == 'TIGER' and director.level == len(LEVELS) + 1 and director.total == 12
      and s.hud.subtitle.text == f'LEVEL {len(LEVELS) + 1}   ROUND 1',
      f'(enemies, alive, hp)={harder}; after death (chips, keys, levels, unlocked, nodes)={kept} '
      f'slot_3={arsenal.weapons[2].name} level={director.level} hud={s.hud.subtitle.text!r}')

# the game is beaten: the menu offers endless, or any one level over again
menu.open()
offered = menu.stage.enabled
click(menus.STAGE_X, menus.ROW_UPGRADES)
click(menus.STAGE_X, menus.ROW_UPGRADES)
picked = (progress.replay, menu.labels['stage'].text, Progress(progress.path).replay, director.changed)
director.auto = True
click(menus.PLAY_X, menus.ROW_PLAY)
director.auto = False
playing = (s.map.name, director.level, director.lap, director.round, director.total, director.changed)
director.round = len(director.rounds) - 1
director.begin_round()
run(T.ROUND_INTRO + 0.05)
for _ in range(3000):
    director.spawn_timer = 0
    app.step()
    if director.state != 'fight':
        break
    wipe()
again = (director.state, progress.cleared, director.level)
run(T.LEVEL_WON_PAUSE + 0.2)
s.tally.input('space')          # straight to the end of the count...
s.tally.input('space')          # ...and on to the shop
click(shop.GO_X, shop.ROW_GO)
menu.open()
for _ in LEVELS[1:]:                # round to endless again
    click(menus.STAGE_X, menus.ROW_UPGRADES)
endless = (progress.replay, menu.labels['stage'].text, director.level, director.lap)
check('once beaten, a level can be picked to play again, or endless', offered
      and picked == (1, 'MODE: LEVEL 2', 1, True) and playing == ('jungle', 2, 0, 0, 12, False)
      and again == ('won', len(LEVELS), 2) and endless == (None, 'MODE: ENDLESS', len(LEVELS) + 1, 1),
      f'offered={offered} picked={picked} playing (map, level, lap, round, enemies, stale)={playing} '
      f'cleared it (state, levels, level)={again} endless={endless}')

click(menus.ERASE_X, menus.ROW_UPGRADES)
asked = (menu.labels['erase'].text, progress.cleared, progress.chips > 0)
run(menus.SURE_TIME + 0.2)          # the menu's clock runs on real time, which the test's steps are not
menu.sure = 0.0
menu.disarm()
click(menus.ERASE_X, menus.ROW_UPGRADES)
click(menus.ERASE_X, menus.ROW_UPGRADES)
saved = Progress(progress.path)
left = (progress.chips, progress.tokens, progress.cleared, progress.unlocked, progress.branches, progress.nodes)
gone = (menu.stage.enabled, menu.labels['erase'].text, director.changed)
app.input('escape', True)
check('the save can be deleted from the menu, at the second click', asked == ('SURE? CLICK AGAIN', len(LEVELS), True)
      and left == (0, 0, 0, {}, {}, {}) and gone == (False, 'SAVE DELETED', True)
      and (saved.chips, saved.tokens, saved.cleared, saved.replay, saved.unlocked, saved.nodes) == (0, 0, 0, None, {}, {})
      and arsenal.weapons[2].name == 'BOOMER' and mods.stat('BOOMER', 'damage') == T.ROCKET_DAMAGE
      and director.level == 1 and not menu.is_open,
      f'first click={asked}; after the second (chips, keys, levels, unlocked, carried, nodes)={left} '
      f'slot_3={arsenal.weapons[2].name} level={director.level}')
director.changed = False
director.state = 'idle'
clear_enemies()
s.load_map('blender')
arena = s.map

# ---------------- glowing and golden enemies ----------------

clear_enemies()
place(Vec3(20, 0, 0))
run(0.3)
chips = progress.chips
glowing = enemies.spawn('brawler', 20, 3, green=False, special='glow')
halo = glowing.halo.enabled
enemies.damage(glowing, 9999)
dropped = len(pickups.live)
run(1.5)
check('a glowing enemy drops chips', halo and dropped == T.GLOW_CHIPS and progress.chips == chips + T.GLOW_CHIPS
      and not pickups.live and s.hud.chips.text == f'CHIPS {progress.chips}',
      f'halo={halo} dropped={dropped} chips={chips}->{progress.chips}')

chips = progress.chips
keys_held = progress.tokens
golden = enemies.spawn('thrower', 20, 3, green=True, special='gold')
suit = (golden.gold, golden.green, golden.hp)
enemies.damage(golden, 9999)
run(1.5)
check('a golden enemy drops chips and a key', suit == (True, False, T.ASTRO_HP * T.GOLD_HP)
      and progress.chips == chips + T.GOLD_CHIPS and progress.tokens == keys_held + 1 and s.hud.note.enabled
      and s.hud.note.text.startswith('BRANCH KEY'),
      f'(gold, green, hp)={suit} chips={chips}->{progress.chips} keys={keys_held}->{progress.tokens} '
      f'notice={s.hud.note.text!r}')
chips, keys_held, owned = progress.chips, progress.tokens, progress.unlocked
progress.unlocked = {weapon: [of.id for of in branches] for weapon, branches in shop.TREES.items()}
s.collect_token()
check('a key is chips once every branch is open', (progress.chips, progress.tokens) == (chips + T.SPARE_TOKEN_CHIPS,
                                                                                         keys_held),
      f'chips={chips}->{progress.chips} keys={progress.tokens}')
progress.unlocked = owned

# ---------------- weapon branches ----------------


def equip(perks=(), **branches):
    """Carry exactly these branches, with nothing bought in their trees but the perks named."""
    progress.branches = {weapon.upper(): branch for weapon, branch in branches.items()}
    progress.unlocked = {weapon: [branch] for weapon, branch in progress.branches.items()}
    progress.nodes = {f'{weapon}/{branch}': {perk: 1 for perk in perks} for weapon, branch in progress.branches.items()}
    mods.rebuild()
    s.refresh_weapons()


def tough(x, z, kind='brawler'):
    """A standing astronaut that no single shot can kill, so the damage can be read off it."""
    enemy = frozen(x, z, kind)
    enemy.hp = enemy.max_hp = 10000
    return enemy


def shoot(slot, target=None, rush=0.0):
    if target is not None:
        aim_at(target.centre)
    arsenal.select(slot)
    arsenal.cooldown = 0
    p.rush.value, p.rush.overdrive = rush, rush >= 100
    arsenal.fire()


def lost(enemy):
    return round(10000 - enemy.hp, 2)


equip(popper='flame', longshot='dragon', boomer='tiger', buzzer='dark')
check('branches in hand', [w.name for w in arsenal.weapons] == ['FLAMETHROWER', 'SCATTER', 'TIGER', 'DARKNESS', 'DRAGON']
      and [w.slot for w in arsenal.weapons] == ['POPPER', 'SCATTER', 'BOOMER', 'BUZZER', 'LONGSHOT']
      and all(len(w.view.children) >= 3 for w in arsenal.weapons if w.name != 'SCATTER'),
      ' '.join(w.name for w in arsenal.weapons))

clear_enemies()
place(Vec3(20, 0, 0))
run(0.5)
near, far, behind = tough(20, 6), tough(20, 20), tough(20, -6)
shoot(0, near)
sprayed = (lost(near), lost(far), lost(behind))
run(3.6)
check('flamethrower burns on', sprayed == (5.0, 0.0, 0.0) and lost(near) == 17.0 and near.burn_time <= 0
      and (lost(far), lost(behind)) == (0.0, 0.0),
      f'one puff (near, out of reach, behind)={sprayed} near after 3.6s={lost(near)}')

equip(popper='taser', longshot='semi', boomer='poison', buzzer='light')
clear_enemies()
place(Vec3(20, 0, 0))
run(0.5)
line, apart = [tough(20, z) for z in (8, 12, 16, 20)], tough(20, 40)
shoot(0, line[0])
check('taser arcs down the line', [lost(e) for e in line] == [8.0, 5.6, 5.6, 5.6] and lost(apart) == 0
      and all(e.stun > 0 for e in line) and apart.stun <= 0,
      f'damage={[lost(e) for e in line]} too_far={lost(apart)}')

equip(longshot='dragon')
clear_enemies()
place(Vec3(20, 0, 0))
run(0.5)
target = tough(20, 10)
shoot(4, target)
calm, slow = lost(target), arsenal.cooldown
clear_enemies()         # that shot threw it across the deck
place(Vec3(20, 0, 0))
run(1.0)
target = tough(20, 10)
shoot(4, target, rush=100.0)
check('dragon breathes fire in overdrive', calm == 150 and abs(slow - 1.8) < 0.05 and 900 < lost(target) <= 1020
      and abs(arsenal.cooldown - 1.8 * 0.6) < 0.05,
      f'damage={calm} cooldown={slow:.2f}; in overdrive damage={lost(target)} cooldown={arsenal.cooldown:.2f}')

equip(longshot='semi')
clear_enemies()
place(Vec3(20, 0, 0))
run(1.5)
target = tough(20, 10)
aim_at(target.centre)
arsenal.select(4)
p.rush.value = 0.0
arsenal.cooldown = 0
shots = 0
for _ in range(60):
    if arsenal.cooldown <= 0:
        aim_at(target.centre)       # the last shot kicked the view
        p.rush.value = 0.0
        arsenal.fire()
        shots += 1
    app.step()
hip = (shots, lost(target))
# with the scope held, every click as it comes up is a quickscope, and the next is ready almost at once
target.hp = 10000
held_keys[T.KEY_SCOPE] = 1
arsenal.cooldown = 0
quick = 0
for _ in range(60):
    if arsenal.cooldown <= 0 and arsenal.quick_ready:
        aim_at(target.centre)
        p.rush.value = 0.0
        arsenal.fire()
        quick += 1
    app.step()
held_keys[T.KEY_SCOPE] = 0
run(0.3)
check('semi-auto: slow from the hip, fast with quickscopes', hip[0] == 2 and 0 < hip[1] <= 2 * 90 and quick >= 4
      and lost(target) / quick > hip[1] / hip[0] * 1.9 and mods.stat('LONGSHOT', 'interval') == 0.8,
      f'{hip[0]} shots in 1s from the hip for {hip[1]}; {quick} quickscopes in 1s for {lost(target)}')

equip(boomer='tiger')
clear_enemies()
place(Vec3(20, 0, 0))
run(1.5)
p.pivot.rotation_x = -25
app.step()
shoot(2)
back = -(p.vel.x * camera.forward.x + p.vel.y * camera.forward.y + p.vel.z * camera.forward.z)
big = next(r for r in arsenal.rockets if r['live'])['entity'].scale_x
run(T.ROCKET_LIFE + 0.2)
place(Vec3(20, 0, 0))
run(0.6)
p.pivot.rotation_x = 85
app.step()
shoot(2)
run(0.25)
hurt = T.PLAYER_HP - p.hp
place(Vec3(20, 0, 0))
edge = tough(20, 7.5)
arsenal.weapons[2].burst(Vec3(20, 1, 0))
check('tiger: big rocket, big blast, hurts you', abs(back - T.ROCKET_RECOIL) < 1.5 and abs(big - 2.2) < 0.01
      and 30 * 0.4 <= hurt <= 30 and lost(edge) > 0 and T.ROCKET_RADIUS < 6.5,
      f'recoil={back:.1f} (scatter {T.SCATTER_RECOIL:.0f}) rocket_size={big:.1f} self_damage={hurt:.0f} '
      f'enemy_7m_away_lost={lost(edge)}')

equip(boomer='poison')
clear_enemies()
place(Vec3(20, 0, 0))
run(0.6)
inside, outside = tough(20, 8), tough(20, 16)
arsenal.weapons[2].burst(Vec3(20, 1, 0))       # the player is standing in it
run(2.0)
early = lost(inside)
run(6.0)
settled = lost(inside)
run(1.0)
check('poison cloud', 18 <= early <= 45 and settled > early and lost(inside) == settled and lost(outside) == 0
      and p.hp == T.PLAYER_HP and not s.clouds.clouds,
      f'enemy in the cloud lost {early} in 2s, {settled} in all; outside={lost(outside)} player_hp={p.hp:.0f}')

chance = mods.roll
mods.roll = lambda odds: True       # every bullet steals and converts
equip(buzzer='dark')
clear_enemies()
place(Vec3(20, 0, 0))
run(0.6)
p.hp = 50
turned, victim = tough(20, 8), tough(24, 8)
shoot(3, turned)
role = (turned.ally, turned in enemies.allies, turned in enemies.alive, turned.alive)
stolen = p.hp - 50
run(2.0)
punched = lost(victim)
turned.ally_time = 0.05
run(0.2)
check('darkness steals health and makes a fighter', stolen == 10 and role == ('fighter', True, False, False)
      and punched >= T.ALLY_DAMAGE and not enemies.allies and not turned.entity.enabled,
      f'hp_stolen={stolen:.0f} (ally, in_allies, in_enemies, alive)={role} it_dealt={punched}')

equip(buzzer='light')
clear_enemies()
place(Vec3(20, 0, 0))
run(0.6)
p.hp = 50
healer = tough(20, 8)
shoot(3, healer)
run(2.0)
check('light makes a healer', healer.ally == 'healer' and 55 < p.hp < 60 and len(enemies.allies) == 1,
      f'ally={healer.ally} hp=50->{p.hp:.1f} in 2s')
mods.roll = chance

# ---------------- perks ----------------

chance = mods.roll
mods.roll = lambda odds: False


def pair(gap=2.5):
    """Two tough astronauts side by side in front of the player."""
    clear_enemies()
    place(Vec3(20, 0, 0))
    run(0.3)
    return tough(20, 10), tough(20 + gap, 10)


equip(('combust', 'wildfire'), popper='flame')
near, far = pair()
near.ignite(8, 3)
run(T.STATUS_TICK + 0.1)
spread = far.burn_time > 0
far.burn_time = 0
before = lost(far)
near.hp = 1
enemies.damage(near, 5)
check('flamethrower perks: fire spreads, the burning blow up', spread and lost(far) - before >= T.COMBUST_DAMAGE * 0.4
      and not near.alive, f'spread={spread} blast_took={lost(far) - before:.1f}')

equip(('fork', 'overload'), popper='taser')
clear_enemies()
place(Vec3(20, 0, 0))
run(0.3)
crowd = [tough(20 + dx, 10 + dz) for dx, dz in ((0, 0), (-3, 2), (3, 2), (-5, 5), (5, 5), (-2, 7), (2, 7), (0, 9))]
shoot(0, crowd[0])
forked = sum(1 for e in crowd if lost(e) > 0)
stunned = crowd[0]
stunned.hp = 10000
stunned.stagger(1.0)
enemies.damage(stunned, 100)
check('taser perks: arcs fork, the stunned take more', forked >= 6 and abs(lost(stunned) - 100 * T.OVERLOAD_BONUS) < 0.01,
      f'struck={forked} of {len(crowd)} with 3 arcs; 100 to a stunned enemy took {lost(stunned)}')

equip(('ember', 'always_lit'), longshot='dragon')
near, far = pair(1.8)      # close enough whichever way an unscoped shot strays
shoot(4, near)
check('dragon perks: burns, and bursts outside overdrive', near.burn_time > 0 and lost(far) > 0,
      f'burning={near.burn_time > 0} beside_it_lost={lost(far)}')

equip(('chain', 'adrenaline'), longshot='semi')
near, far = pair(8)
dealt = []
for _ in range(2):
    near.hp = 10000
    aim_at(near.centre)
    arsenal.select(4)
    arsenal.cooldown = 0
    arsenal.scope_age = T.LONGSHOT_SCOPE_TIME
    p.rush.value = 0.0
    arsenal.fire()
    dealt.append(lost(near))
weak = frozen(20, 6)
weak.hp = 1
aim_at(weak.centre)
arsenal.cooldown = 0
arsenal.scope_age = T.LONGSHOT_SCOPE_TIME
p.rush.value = 0.0
arsenal.fire()
check('semi-auto perks: quickscopes chain, kills fill the rush', abs(dealt[1] / dealt[0] - (1 + T.CHAIN_STEP)) < 0.01
      and not weak.alive and p.rush.value >= 100 * T.ADRENALINE_RUSH - 0.01,
      f'quickscope damage={dealt} rush_after_kill={p.rush.value:.0f}')
run(0.5)

equip(boomer='tiger')
near, far = pair()
arsenal.weapons[2].burst(Vec3(20, 1, 12))
single = lost(near)
equip(('cluster', 'blast_suit'), boomer='tiger')
near, far = pair()
p.hp = T.PLAYER_HP
arsenal.weapons[2].burst(Vec3(20, 1, 12))
clustered = lost(near)
place(Vec3(20, 0, 0))
arsenal.weapons[2].burst(Vec3(20, 0.5, 0.5))
check('tiger perks: a cluster of blasts, none of which hurt you', clustered > single > 0 and p.hp == T.PLAYER_HP,
      f'enemy lost {single} to one blast, {clustered} to the cluster; hp={p.hp}')
run(0.5)

equip(('corrode', 'plague'), boomer='poison')
near, far = pair()
near.envenom(1, 5)
enemies.damage(near, 100)
corroded = lost(near)
near.hp = 1
enemies.damage(near, 5)
check('poison perks: poisoned enemies take more and leave a cloud', abs(corroded - 100 * T.CORRODE_BONUS) < 0.01
      and len(s.clouds.clouds) == 1 and s.clouds.clouds[0]['radius'] == T.PLAGUE_RADIUS,
      f'100 to a poisoned enemy took {corroded}; clouds={len(s.clouds.clouds)}')

equip(('feast', 'legion'), buzzer='dark')
near, far = pair()
weak = frozen(20, 6)
weak.hp = 1
p.hp = 50
shoot(3, weak)
fed = p.hp
enemies.convert(near, 'fighter', 0.05)
tag = near.tag.enabled
before = lost(far)
run(0.2)
check('darkness perks: kills feed you, a fighter goes out with a bang', fed == 50 + T.FEAST_HEAL and tag
      and lost(far) - before >= T.LEGION_DAMAGE * 0.4 and s.hud.note.text == 'YOUR FIGHTER IS GONE'
      and s.hud.heal_time > 0, f'hp=50->{fed} blast_took={lost(far) - before:.1f} notice={s.hud.note.text!r}')

equip(('aegis', 'blessing'), buzzer='light')
near, far = pair()
near.z = 5      # inside its healing reach
enemies.convert(near, 'healer', 0.3, heal=0.0)
p.hp = 60
p.invulnerable = 0
p.take_damage(20)
guarded = 60 - p.hp
run(0.5)
check('light perks: a healer shields you and blesses you as it leaves', abs(guarded - 20 * T.AEGIS_SHARE) < 0.01
      and abs(p.hp - (60 - guarded + T.BLESSING_HEAL)) < 0.01 and not enemies.allies,
      f'20 damage took {guarded:.0f}; hp after it left={p.hp:.0f}')
mods.roll = chance

# ---------------- the double barrel ----------------

equip()
clear_enemies()
place(Vec3(20, 0, 0))
run(1.5)
arsenal.endless = False
arsenal.restock()
scatter = arsenal.weapons[1]
arsenal.select(1)
arsenal.cooldown = 0
arsenal.fire()
first = (round(arsenal.cooldown, 2), scatter.rounds, arsenal.reloading)
arsenal.cooldown = 0
arsenal.fire()
second = (round(arsenal.cooldown, 2), scatter.rounds, arsenal.reloading)
arsenal.fire()                      # nothing in it: nothing happens
run(T.AMMO['SCATTER'][2] + 0.1)
check('scatter: two barrels at once, then a reload', first == (T.SCATTER_INTERVAL, 1, False)
      and second == (T.AMMO['SCATTER'][2], 0, True) and (scatter.rounds, scatter.reserve) == (2, 38)
      and not arsenal.reloading and T.SCATTER_INTERVAL < 0.2,
      f'(wait, rounds, reloading) after the first={first} after the second={second}; '
      f'then {scatter.rounds} in the gun and {scatter.reserve} carried')

# ---------------- ammunition ----------------

buzzer = arsenal.weapons[3]
arsenal.select(3)
run(0.3)
buzzer.rounds = 3
mouse.locked = True
arsenal.input(T.KEY_RELOAD)
app.step()
asked = (arsenal.reloading, s.hud.reload_text.text)
run(T.AMMO['BUZZER'][2] + 0.1)
topped = (buzzer.rounds, buzzer.reserve)
buzzer.rounds, buzzer.reserve = 1, 0
held_keys[T.KEY_FIRE] = 1
run(0.5)
dry = (buzzer.rounds, arsenal.reloading, s.hud.reload_text.text[:7])
held_keys[T.KEY_FIRE] = 0
popper = arsenal.weapons[0]
arsenal.select(0)
popper.rounds = 1
arsenal.cooldown = 0
arsenal.fire()
run(T.AMMO['POPPER'][2] + 0.1)
check('magazines, reloading and running dry', asked == (True, 'RELOADING') and topped == (40, 320 - 37)
      and dry == (0, False, 'NO AMMO') and (popper.rounds, popper.reserve) == (12, None),
      f'reload key={asked} then (gun, carried)={topped}; out of ammunition={dry}; popper={popper.rounds} and never runs out')

clear_enemies()
place(Vec3(20, 0, 0))
run(0.3)
for weapon in arsenal.weapons:
    weapon.restock()
buzzer.reserve = 100
chips = progress.chips
T.SPARE_AMMO_CHIPS = spare_chips
golden = enemies.spawn('brawler', 20, 3, green=False, special='gold')
enemies.damage(golden, 9999)
crates = sum(item['kind'] == 'ammo' for item in pickups.live)
run(1.5)
filled = buzzer.reserve
buzzer.reserve = 100
s.collect_ammo()                    # the key came in the same pile, so the notice is read from a crate alone
noted = s.hud.note.text
buzzer.restock()
s.collect_ammo()
buzzer.reserve = 0
director.start()
director.state = 'idle'
clear_enemies()
check('golden enemies drop ammunition', crates == T.AMMO_CRATES and filled == 320 and noted == 'AMMO FOR THE BUZZER'
      and progress.chips == chips + T.GOLD_CHIPS + T.SPARE_AMMO_CHIPS and buzzer.reserve == 320,
      f'crates={crates} buzzer carried 100->{filled}; a spare crate paid {progress.chips - chips - T.GOLD_CHIPS} chips; '
      f'a new level restocks to {buzzer.reserve}')
progress.tokens -= 1
arsenal.endless = True
T.SPARE_AMMO_CHIPS = 0

# ---------------- the scatter's branches ----------------

equip(scatter='impulse')
near, far = pair(2.0)
aim_at(near.centre + Vec3(0, 0.3, 0))
arsenal.select(1)
arsenal.cooldown = 0
arsenal.fire()
grenade = next(r for r in arsenal.rockets if r['live'])
rise = grenade['vel'].y
run(0.2)
sinking = grenade['vel'].y < rise
run(1.0)
thrown = (near.vx ** 2 + near.vz ** 2) ** 0.5 + abs(near.vy)
place(Vec3(20, 0, 0))
run(0.4)
arsenal.weapons[1].burst(Vec3(20, 0, 0.6))
check('impulse: a grenade that arcs, hurls enemies and lifts you unhurt', arsenal.weapons[1].name == 'IMPULSE' and sinking
      and lost(near) > 0 and lost(far) > 0 and p.vel.y > 8 and p.hp == T.PLAYER_HP and arsenal.weapons[1].mag == 4,
      f'grenade_falls={sinking} enemies lost {lost(near)} and {lost(far)}; you leave the deck at {p.vel.y:.1f} m/s, hp={p.hp}')
run(1.0)

# the sticky grenade: the scope key fires one that sticks where it lands, and sets it off
impulse = arsenal.weapons[1]
mouse.locked = True
near, far = pair(2.0)
aim_at(Vec3(20, 0, 7))              # the floor three metres short of the nearer astronaut
arsenal.cooldown = 0
arsenal.input(T.KEY_SCOPE)
run(0.7)
out = arsenal.remotes()
stuck = len(out) == 1 and out[0]['stuck']
spot = Vec3(out[0]['pos']) if stuck else Vec3(0, 0, 0)
run(2.0)
stayed = stuck and out[0]['live'] and (out[0]['pos'] - spot).length() < 0.01 and spot.y < 0.5
untouched = lost(near)
rounds = impulse.rounds
arsenal.input(T.KEY_SCOPE)
run(0.1)
check('impulse: the scope key sticks a grenade where it lands, and sets it off', stayed and untouched == 0
      and lost(near) > 0 and not arsenal.remotes() and impulse.rounds == rounds,
      f'stuck={stuck} at {spot} stayed={stayed}; before setting it off the astronaut lost {untouched}, after {lost(near)}')

near, far = pair(2.0)
aim_at(near.centre)
arsenal.cooldown = 0
arsenal.input(T.KEY_SCOPE)
run(0.4)
out = arsenal.remotes()
riding = len(out) == 1 and out[0]['host'] is near
near.x += 3
run(0.1)
follows = riding and abs(out[0]['pos'].x - (near.x + out[0]['offset'].x)) < 0.01
arsenal.cooldown = 0
arsenal.input(T.KEY_SCOPE)          # with one out, the key sets it off: it never fires a second
run(0.1)
check('impulse: a sticky grenade rides on the enemy it hits, one at a time', follows and not arsenal.remotes()
      and lost(near) > 0, f'riding={riding} follows={follows} out after the second press={len(arsenal.remotes())}')

clear_enemies()
place(Vec3(20, 0, 0))
run(0.5)
impulse.burst(Vec3(23, 0.1, 0))     # on the floor three metres off
lifted = (round(p.vel.y, 1), round((p.vel.x ** 2 + p.vel.z ** 2) ** 0.5, 1))
place(Vec3(20, 0, 0))
run(0.5)
impulse.burst(Vec3(20 + 0.9 * impulse.stat('radius'), 0.1, 0))     # near the edge of the blast
edge = round(p.vel.y, 1)
check('impulse: its blast throws you up hard, nearly as hard at its edge', lifted[0] > 18 and edge > 9,
      f'three metres off (up, along)={lifted}; at the edge, up {edge}')

throws = {}
for branch in (None, 'tiger', 'poison'):
    equip(**({'boomer': branch} if branch else {}))
    weapon = arsenal.weapons[2]
    place(Vec3(20, 0, 0))
    run(0.5)
    p.invulnerable = 99
    weapon.burst(p.centre + Vec3(2, 0, 0))
    expected = weapon.throw * (1 - 2 / (weapon.stat('radius') * 1.3))
    throws[weapon.name] = (round(p.vel.length(), 1), round(expected, 1))
    clear_enemies()
check('the launchers throw you 12, 14 and 11', (T.ROCKET_PLAYER_KNOCK, T.TIGER_PLAYER_KNOCK, T.POISON_PLAYER_KNOCK)
      == (12, 14, 11) and all(abs(got - want) < 0.6 for got, want in throws.values()),
      f'(speed, expected) after a blast 2 m off: {throws}')

pictures = {}
for branch in (None, 'tiger', 'poison'):
    equip(**({'boomer': branch} if branch else {}))
    weapon = arsenal.weapons[2]
    place(Vec3(20, 0, 0))
    run(0.3)
    s.pixels.clear()
    for item in s.blasts.items:
        item['ring'].enabled = False
    weapon.burst(Vec3(20, 1, 14))
    alive = s.pixels.age < s.pixels.life
    drawing = alive & (s.pixels.hold > 0)
    looks = {fxpixels.LOOKS[k] for k in s.pixels.look[alive]}
    run(fxpixels.FORM_TIME * 1.3)
    placed = bool(drawing.any()) and float(abs(s.pixels.pos[drawing] - s.pixels.home[drawing]).max()) < 0.01
    turned = s.pixels.home[drawing].copy()
    run(0.25)
    turned = bool(drawing.any()) and float(abs(s.pixels.home[drawing] - turned).max()) > 0.05
    pictures[weapon.name] = (any(item['ring'].enabled for item in s.blasts.items), int(alive.sum()),
                             int(drawing.sum()), looks, placed and turned)
    clear_enemies()
deep = {look: (len(fxpixels.relief(look)), len(fxpixels.cells(fxpixels.PICTURES[look])),
               len({layer for _, _, layer, _ in fxpixels.relief(look)})) for look in ('tiger', 'poison')}
check('rockets burst into pixels: a tiger for the Tiger, a skull for Poison, both in relief, swinging round',
      pictures['BOOMER'][:3] == (False, 214, 0) and pictures['BOOMER'][3] == {'rocket'}
      and pictures['TIGER'][2] == deep['tiger'][0] and pictures['TIGER'][3] == {'tiger'}
      and pictures['POISON'][2] == deep['poison'][0] and pictures['POISON'][3] == {'poison'}
      and all(n >= 2 * flat and layers >= 4 for n, flat, layers in deep.values())
      and not pictures['TIGER'][0] and not pictures['POISON'][0] and pictures['TIGER'][4] and pictures['POISON'][4],
      f'(toon ring, pixels, in the picture, palettes, picture formed and turning)={pictures}; '
      f'(relief pixels, cells, layers)={deep}')

bursts = {}
for branch, fire in (('impulse', lambda w: w.burst(Vec3(20, 1, 14))), ('dragon', lambda w: w.landed([(Vec3(20, 1, 14), False)]))):
    equip(**({'scatter': branch} if branch == 'impulse' else {'longshot': branch}))
    weapon = arsenal.weapons[1 if branch == 'impulse' else 4]
    place(Vec3(20, 0, 0))
    run(0.3)
    held_rush = p.rush.update
    p.rush.update = lambda speed, dt: None
    p.rush.value, p.rush.overdrive = 100.0, True    # the Dragon only bursts in Overdrive
    weapon.struck = []
    s.pixels.clear()
    for item in s.blasts.items:
        item['ring'].enabled = False
    fire(weapon)
    alive = s.pixels.age < s.pixels.life
    bursts[weapon.name] = (any(item['ring'].enabled for item in s.blasts.items), int(alive.sum()),
                           {fxpixels.LOOKS[k] for k in s.pixels.look[alive]})
    p.rush.update = held_rush
    p.rush.value, p.rush.overdrive = 0.0, False
    clear_enemies()
check('the Impulse and the Dragon burst into pixels too', bursts == {'IMPULSE': (False, 214, {'impulse'}),
                                                                   'DRAGON': (False, 214, {'dragon'})}, f'{bursts}')
equip(scatter='impulse')

equip(('deep_freeze', 'shatter'), scatter='ice')
near, far = pair(2.0)
shoot(1, near)
chilled = (round(near.slow, 2), near.slow_time > 2, near.stun > 0)
shoot(1, near)
frozen_solid = near.stun > 0
runner = enemies.spawn('brawler', 20, 30, green=False)
runner.spawning = runner.pause = 0
runner.chill(0.45, 5)
run(1.0)
pace = (runner.vx ** 2 + runner.vz ** 2) ** 0.5
far.slow_time = 0
before = lost(far)
near.hp = 1
enemies.damage(near, 5)
check('ice: slows what it hits, freezes it on the second hit, and the dead shatter', chilled == (0.45, True, False)
      and frozen_solid and abs(pace - T.BRAWLER_SPEED * 0.55) < 0.6 and far.slow_time > 0 and lost(far) > before,
      f'(slow, lasting, frozen) after one shot={chilled}; frozen after two={frozen_solid}; a slowed brawler runs at '
      f'{pace:.1f} m/s; beside a shattered one: slowed={far.slow_time > 0} lost={lost(far) - before:.1f}')

# ---------------- doors, streaks, sights and the player's body ----------------

equip()
clear_enemies()
place(polar(30, 200))
run(0.3)
came = [enemies.spawn() for _ in range(12)]
spots = [((e.x ** 2 + e.z ** 2) ** 0.5, min(abs((degrees(atan2(e.x, e.z)) - door['angle'] + 180) % 360 - 180)
                                              for door in arena.doors)) for e in came]
nearest = min(((e.x - p.x) ** 2 + (e.z - p.z) ** 2) ** 0.5 for e in came)
opened = sum(door['hold'] > 0 for door in arena.doors)
run(0.3)
ajar = max(door['open'] for door in arena.doors)
check('astronauts come in through the doors', len(arena.doors) == 8 and all(56 < r < 59 and off < 2 for r, off in spots)
      and nearest > T.SPAWN_MIN_DISTANCE and opened >= 2 and ajar > 0.8,
      f'{len(arena.doors)} doors; 12 spawned {min(r for r, _ in spots):.1f}-{max(r for r, _ in spots):.1f}m out, within '
      f'{max(off for _, off in spots):.1f} deg of a door, nearest {nearest:.0f}m from the player; doors open={opened}')

clear_enemies()
place(Vec3(20, 0, 0))
run(0.3)
arsenal.select(0)
arsenal.cooldown = 0
arsenal.fire()
app.step()
streak = next(t for t in arsenal.tracers if t['live'])
drawn = (streak['trail'].scale_z, (Vec3(*streak['trail'].position) - streak['start']).length())
run(0.5)
check('a bullet is a short streak, not a line from the gun', 0 < drawn[0] < 2.0 and drawn[1] >= 1.0
      and not any(t['live'] for t in arsenal.tracers), f'streak {drawn[0]:.1f}m long, starting {drawn[1]:.1f}m from the muzzle')

sights = {}
for branch in (None, 'dragon', 'semi'):
    equip(**({'longshot': branch} if branch else {}))
    arsenal.select(4)
    held_keys[T.KEY_SCOPE] = 1
    run(0.6)
    sights[branch or 'plain'] = (s.hud.sight, round(camera.fov))
    held_keys[T.KEY_SCOPE] = 0
    run(0.3)
check('each rifle has its own sight', sights == {'plain': ('cross', 38), 'dragon': ('dragon', 28), 'semi': ('holo', 50)},
      f'(sight picture, field of view)={sights}')

equip()
place(Vec3(20, 0, 0))
run(0.5)
standing = [round(leg.rotation_x) for leg in p.legs.legs]
keys(w=1)
swung = 0
for _ in range(40):
    app.step()
    swung = max(swung, abs(p.legs.legs[0].rotation_x - p.legs.legs[1].rotation_x))
keys()
gloves = all(len(w.view.children) >= 2 for w in arsenal.weapons)
check('the player has legs that run and hands on every weapon', standing == [-9, -9] and swung > 30 and gloves
      and s.katana.grip is not None, f'legs standing={standing} furthest apart running={swung:.0f} deg hands={gloves}')

old = Path(scratch.name) / 'old_settings.json'
old.write_text(json.dumps({'keys': {'respawn': 'r', 'jump': 'space', 'katana': 'q'}}), encoding='utf-8')
moved = Settings(old).keys
check('an old settings file gives up R for reload', (moved['reload'], moved['respawn'], moved['katana']) == ('r', 'backspace', 'q'),
      f"reload={moved['reload']} respawn={moved['respawn']} katana={moved['katana']}")

# ---------------- sizes, hops and the roof ----------------

clear_enemies()
place(Vec3(20, 0, 0))
run(0.5)
small = enemies.spawn('brawler', 20, 10, green=False, size=0.75)
big = enemies.spawn('brawler', 24, 10, green=False, size=1.45)
for enemy in (small, big):
    enemy.spawning = 0
    enemy.pause = 999
run(0.1)
graze = [e.size for _, e in enemies.ray_hits(Vec3(21.1, 1, 0), Vec3(0, 0, 1), 30)
         + enemies.ray_hits(Vec3(25.1, 1, 0), Vec3(0, 0, 1), 30)]
check('astronauts come in sizes', graze == [1.45] and big.hp > 2.5 * small.hp and small.pace > 1.1 > 0.9 > big.pace
      and abs(big.entity.scale_y / small.entity.scale_y - 1.45 / 0.75) < 0.05 and big.centre.y > small.centre.y,
      f'a shot 1.1m off centre hits sizes {graze}; hp small={small.hp:.0f} big={big.hp:.0f}')

clear_enemies()
place(Vec3(20, 0, 0))
run(0.3)
leaper = enemies.spawn('brawler', 20, 9, green=False)
leaper.spawning = leaper.pause = 0
leaper.hop_timer = 0
peak, leapt = 0.0, False
for _ in range(80):
    app.step()
    peak = max(peak, leaper.y)
    leapt = leapt or leaper.leaping
check('a brawler leaps in and punches as it lands', leapt and 0.8 < peak < 1.5 and p.hp == T.PLAYER_HP - T.BRAWLER_DAMAGE
      and leaper.grounded, f'leapt={leapt} peak={peak:.2f}m hp={p.hp}')

clear_enemies()
place(polar(55, 0, T.PLAYER_HEIGHT + 2))
run(1.0)
p.invulnerable = 1e6
climber = enemies.spawn('brawler', polar(28, 12).x, polar(28, 12).z, green=False)
climber.spawning = climber.pause = 0
fastest = 0.0
for _ in range(420):
    app.step()
    fastest = max(fastest, climber.vy)
    if climber.y > 3.4:
        break
check('no astronaut jumps to a catwalk: it runs up the gangway', p.y > 3.4 and climber.y > 3.4 and fastest <= 0.01,
      f'player_y={p.y:.1f} brawler_y={climber.y:.1f} fastest_rise={fastest:.1f}')
p.invulnerable = 0

clear_enemies()
place(Vec3(20, 0, 0))
run(0.3)
p.vel = Vec3(0, 60, 0)
p.grounded = False
top = 0.0
for _ in range(90):
    app.step()
    top = max(top, p.y)
ceiling = roof_height(20)
place(Vec3(20, 0, 0))
run(0.5)
p.pivot.rotation_x = -89
app.step()
shoot(2)
run(0.7)
flying = sum(r['live'] for r in arsenal.rockets)
check('the roof is solid', ceiling - T.PLAYER_HEIGHT - 1.1 < top <= ceiling - T.PLAYER_HEIGHT + 0.1 and flying == 0,
      f'thrown up at 60 m/s the player stops at {top:.1f}m under a roof at {ceiling:.1f}m; rockets still flying={flying}')
run(1.0)

equip()
clear_enemies()
p.hp = T.PLAYER_HP
check('plain weapons again', [w.name for w in arsenal.weapons] == ['POPPER', 'SCATTER', 'BOOMER', 'BUZZER', 'LONGSHOT']
      and mods.stat('POPPER', 'damage') == T.POPPER_DAMAGE and arsenal.weapon.view.enabled,
      ' '.join(w.name for w in arsenal.weapons))

# ---------------- the levels and their maps ----------------

equip()
clear_enemies()
progress.cleared = 1
director.start()
arena = s.map
jungle = (arena.name, director.plan.name, s.hud.subtitle.text, {kind for kind, _, _ in director.queue})
director.round = 1
director.begin_round()
marksmen = sum(kind == 'sniper' for kind, _, _ in director.queue)
progress.cleared = len(LEVELS) + 2
director.start()
arena = s.map
lapped = (arena.name, director.lap, director.level, round(director.hp_scale, 3))
director.state = 'idle'
clear_enemies()
check('three levels, each its own map, and round again harder', [(lv.name, lv.map) for lv in LEVELS]
      == [('THE SHIP', 'blender'), ('THE JUNGLE', 'jungle'), ('THE CRYSTAL CAVE', 'cave')]
      and jungle == ('jungle', 'THE JUNGLE', 'LEVEL 2   THE JUNGLE', {'croc', 'snapper'}) and marksmen == 1
      and lapped == ('cave', 1, 6, round(1.1 * 1.15, 3)) and len(s.map.anchors) == 14,
      f'level 2={jungle} snipers in its round 2={marksmen}; level 6 (map, lap, level, hp)={lapped}')

worst = {}
for name, spots in (('jungle', ((55, 0, 4.5), (42.5, 120, 2.25), (20, 50, 0), (55, 80, 0), (56, 240, 4.5))),
                    ('cave', ((55, 90, 3.0), (44, 270, 1.5), (30, 10, 0), (55, 0, 0), (57, 280, 3.0)))):
    s.load_map(name)
    arena = s.map
    run(0.1)
    off = 0
    for radius, angle, height in spots:
        at = polar(radius, angle)
        off = max(off, abs(down_height(at) - arena.ground_height(at.x, at.z, 10)), abs(down_height(at) - height))
    worst[name] = round(off, 3)
check('the new maps: ground_height matches their colliders', all(v < 0.12 for v in worst.values())
      and p.position == arena.spawn_position or (p.position - arena.spawn_position).length() < 3,
      f'largest difference={worst}')

s.load_map('blender')
arena = s.map
place(polar(20, 200))
run(0.2)
dressed = {}
for kind, species in enemies.KINDS.items():
    plain = enemies.spawn(kind, 10, 10, green=False)
    green = enemies.spawn(kind, 12, 10, green=True)
    gold = enemies.spawn(kind, 14, 10, special='gold')
    dressed[kind] = (plain.green, green.green == species.PARRY, gold.gold == species.DROPS,
                     gold.halo.enabled == species.DROPS, all(e.alive for e in (plain, green, gold)))
run(0.3)
clear_enemies()
check('every enemy comes plain, parryable and golden', len(dressed) == 11
      and all(v == (False, True, True, True, True) for v in dressed.values())
      and not enemies.KINDS['sniper'].PARRY and not enemies.KINDS['mini'].DROPS,
      f'kinds={sorted(dressed)}')

# ---------------- snipers ----------------


def marksman(kind='sniper'):
    """A sniper on the catwalk at angle 0, ready to aim."""
    e = enemies.spawn(kind)
    e.spawning = e.pause = e.rest = 0
    e.perch = polar(56, 0, 3.5)
    e.x, e.y, e.z = e.perch.x, e.perch.y, e.perch.z
    return e


clear_enemies()
open_floor = polar(20, 0)
place(polar(20, 200))
run(0.3)
sniper = enemies.spawn('sniper')
perched = (sniper.aerial, any((sniper.perch - spot).length() < 0.01 for spot in arena.perches),
           (Vec3(sniper.x, 0, sniper.z) - Vec3(p.x, 0, p.z)).length() > T.SPAWN_MIN_DISTANCE)
sniper.shove(20, 20, 20)
braced = sniper.aerial and sniper.y == sniper.perch.y
clear_enemies()
place(open_floor)
run(0.3)
sniper = marksman()
run(1.0)
cold = tuple(round(c, 2) for c in tuple(sniper.laser.color)[:3])
clear = sniper.aim_point(p)[1] and sniper.laser.enabled
warned = (s.hud.alarm.enabled, s.hud.alarm.text)
sniper.aim = T.SNIPER_AIM - 1.0
run(0.5)
hot = tuple(round(c, 2) for c in tuple(sniper.laser.color)[:3])
counting = s.hud.alarm.text
before = p.hp
run(0.7)
check('a sniper aims for 8 s with a laser that turns red, and hits for 50', perched == (True, True, True) and braced
      and clear and cold[2] > cold[0] + 0.3 and hot[0] > hot[2] + 0.3
      and warned[0] and 'SNIPER' in warned[1] and counting != warned[1]
      and (before, p.hp) == (T.PLAYER_HP, T.PLAYER_HP - T.SNIPER_DAMAGE) and sniper.rest > 0 and sniper.aim == 0,
      f'on a perch, far off, braced={perched + (braced,)} laser blue={cold} red={hot} hud={warned[1]!r}->{counting!r} '
      f'hp {before}->{p.hp}')

place(open_floor)
sniper.rest = 0
sniper.aim = T.SNIPER_AIM - 0.1
run(0.05)
p.dash_timer = T.DASH_TIME          # a dash, just now
run(0.2)
dodged = p.hp
tank = polar(44, 45)
behind = tank + (tank - sniper.perch).normalized() * 4
place(Vec3(behind.x, 0, behind.z))
run(0.3)
sniper.rest = 0
sniper.aim = T.SNIPER_AIM - 0.1
run(0.3)
covered = (p.hp, sniper.aim_point(p)[1])
place(open_floor)
run(0.3)
sniper.rest = 0
sniper.aim = T.SNIPER_AIM - 0.2
enemies.damage(sniper, 9999)
run(0.5)
check('the shot is dodged by a dash, stopped by cover and called off by a kill', dodged == T.PLAYER_HP
      and covered == (T.PLAYER_HP, False) and p.hp == T.PLAYER_HP and not sniper.laser.enabled,
      f'hp after a dash={dodged}, behind a tank={covered[0]} (in sight={covered[1]}), after killing it={p.hp}')

clear_enemies()
place(open_floor)
run(0.3)
elite = marksman('elite')
elite.aim = T.SNIPER_AIM - 0.1
died = []
heard = p.on_event
p.on_event = lambda name, value: (died.append(name), heard(name, value))
run(0.3)
p.on_event = heard
check('the advanced sniper kills with one shot', elite.DAMAGE == T.PLAYER_HP and 'death' in died
      and p.hp == T.PLAYER_HP and progress.cleared == len(LEVELS) + 2,
      f'events={died} levels kept={progress.cleared}')
progress.cleared = 0

# ---------------- crocodiles ----------------

clear_enemies()
s.load_map('jungle')
arena = s.map
home = polar(26, 20)


def loose(kind, x, z, **how):
    """An enemy standing beside the player's spot, free to act at once."""
    e = enemies.spawn(kind, home.x + x, home.z + z, how.pop('green', False), **how)
    e.spawning = e.pause = 0
    return e


place(home)
run(0.3)
croc = loose('croc', 10, 0)
croc.dash_timer = 0
app.step()
crouched = croc.mode
run(T.CROC_CROUCH + 0.05)
dashing = croc.mode
fastest = 0
for _ in range(40):
    app.step()
    fastest = max(fastest, (croc.vx ** 2 + croc.vz ** 2) ** 0.5)
bitten = p.hp
place(home)
croc.x, croc.z = home.x + 10, home.z
croc.mode, croc.dash_timer, croc.hit_cooldown = 'run', 0, 99
croc.vx = croc.vz = 0
app.step()
run(T.CROC_CROUCH + 0.05)
place(home + Vec3(0, 0, 5))         # a step to the side as it sets off
run(0.8)
check('a dark green crocodile crouches, then dashes; a sidestep beats it', (crouched, dashing) == ('crouch', 'dash')
      and fastest > 25 and bitten == T.PLAYER_HP - T.CROC_DASH_DAMAGE and p.hp == T.PLAYER_HP,
      f'modes={crouched}->{dashing} top speed={fastest:.0f} m/s hp after standing still={bitten}, after stepping aside={p.hp}')

clear_enemies()
place(home)
run(0.3)
snapper = loose('snapper', 15, 0)
leaps, was = 0, True
for _ in range(300):
    app.step()
    leaps += was and not snapper.grounded
    was = snapper.grounded
    if p.hp < T.PLAYER_HP:
        break
check('a light green crocodile is small and comes in leaps, biting where it lands', leaps >= 2
      and snapper.size == T.SNAPPER_SCALE and snapper.max_hp < T.ASTRO_HP * 0.6
      and p.hp == T.PLAYER_HP - T.SNAPPER_BITE, f'leaps={leaps} size={snapper.size} hp={snapper.max_hp:.0f} bite took {T.PLAYER_HP - p.hp}')

clear_enemies()
place(home)
run(0.3)
lobber = loose('lobber', 18, 0)
lobber.hit_cooldown, lobber.leap_timer = 0, 99
for _ in range(60):
    app.step()
    if enemies.markers:
        break
thrown = [m.kind.split('_')[0] for m in enemies.markers]     # a green one's are pale, a golden one's gold
run(2.0)
blown = p.hp
place(home)                         # the blast threw the player: back to the same spot, standing
run(0.3)
lobber.hit_cooldown = 0
for _ in range(60):
    app.step()
    if enemies.markers:
        break
place(home + Vec3(-25, 0, 20))      # gone from where it was aimed
run(1.6)
minis = [e for e in enemies.alive if e.kind == 'mini']
stood = len(minis)
for mini in minis:
    mini.fuse = 0.05
run(0.3)
timed = not any(e.kind == 'mini' for e in enemies.alive)
lobber.hit_cooldown = 99
lobber.leap_timer = 0
far, start = 0, Vec3(lobber.x, 0, lobber.z)
for _ in range(90):
    app.step()
    far = max(far, lobber.y)
moved = (Vec3(lobber.x, 0, lobber.z) - start).length()
clear_enemies()
place(home)
run(0.3)
mini = loose('mini', 6, 0)
bystander = frozen(home.x + 2.5, home.z + 1, 'croc')
hurt_before = bystander.hp
run(2.5)
check('a red crocodile leaps about and throws minis that bite and blow up, or get up and come on', thrown == ['mini']
      and blown == T.PLAYER_HP - T.MINI_BITE - T.MINI_BLAST and stood == 1 and timed and far > 2 and moved > 5
      and not mini.alive and T.PLAYER_HP - T.MINI_BLAST_DAMAGE <= p.hp < T.PLAYER_HP and bystander.hp < hurt_before,
      f'thrown={thrown} a hit took {T.PLAYER_HP - blown}; a miss left {stood} on its feet, gone when its time was up={timed}; '
      f'the lobber leapt {far:.1f}m high and {moved:.0f}m; a mini reaching the player took {T.PLAYER_HP - p.hp:.0f} '
      f'and {hurt_before - bystander.hp:.0f} from a crocodile beside them')

clear_enemies()
place(home)
run(0.3)
golden = enemies.spawn('croc', home.x + 4, home.z, special='gold')
parried = loose('croc', 2, 0, green=True)
parried.hit_cooldown = parried.dash_timer = 99
before = len(s.pickups.live)
enemies.damage(golden, 9999)
check('a golden crocodile drops a key like any golden enemy', golden.gold and golden.special == 'gold' and parried.green
      and len(s.pickups.live) > before, f'drops={len(s.pickups.live) - before}')

# ---------------- the crystal cave ----------------

clear_enemies()
s.load_map('cave')
arena = s.map
home = polar(26, 20)
place(home)
run(0.3)
monkey = enemies.spawn('monkey')
monkey.spawning = monkey.pause = 0
first = monkey.anchor
hung = (monkey.aerial, first in arena.anchors, round(first.y - monkey.y, 2))
shards, swung = set(), False
for _ in range(420):
    app.step()
    place(home)
    shards |= {m.kind for m in enemies.markers}
    swung = swung or (monkey.anchor is not first and monkey.mode == 'hang')
monkey.shove(0, 4, 0)
dropped = (monkey.aerial, monkey.anchor)
run(1.0)
floor = monkey.grounded and monkey.y < 0.5
run(T.MONKEY_CLIMB + T.MONKEY_SWING_TIME + 0.4)
check('a crystal monkey hangs, swings to other crystals, flings shards and climbs back when knocked down',
      hung[:2] == (True, True)
      and HANG * MODEL_SCALE * T.MONKEY_SCALE * T.ASTRO_SIZE[0] - 0.05 < hung[2]
      < HANG * MODEL_SCALE * T.MONKEY_SCALE * T.ASTRO_SIZE[1] + 0.05 and 'shard' in shards and swung and dropped == (False, None)
      and floor and monkey.aerial and monkey.mode == 'hang' and monkey.anchor in arena.anchors,
      f'hanging={hung} thrown={shards} moved to another crystal={swung}; knocked down to the floor={floor}, '
      f'back up={monkey.aerial}')

clear_enemies()
place(home)
run(0.3)
monkey = enemies.spawn('monkey')
monkey.spawning = monkey.pause = 0
monkey.hit_cooldown = 99
vine = monkey.vine
reach = HANG * monkey.size * MODEL_SCALE
on_tip = vine is not None and vine.holder is monkey and abs((vine.end - Vec3(monkey.x, monkey.y, monkey.z)).length()
                                                             - reach) < 0.01
vine.kick(5, 0)
worst = tilt = 0.0
last = Vec3(monkey.x, monkey.y, monkey.z)
for _ in range(300):
    app.step()
    place(home)
    now = Vec3(monkey.x, monkey.y, monkey.z)
    if monkey.mode == 'hang':
        worst = max(worst, (now - last).length())
        if monkey.vine is vine:
            tilt = max(tilt, abs(vine.ax) + abs(vine.az))
    last = now
moved_on = monkey.mode == 'hang' and monkey.vine is not vine and monkey.vine.holder is monkey and vine.holder is None
check('monkeys hang from vines that swing with them, and never jump about', len(arena.vines) == len(arena.anchors) == 14
      and on_tip and tilt > 0.1 and worst < 0.25 and moved_on,
      f'on the tip={on_tip} the vine leant {tilt:.2f} rad; most moved in a frame while hanging={worst:.2f} m; '
      f'went on to another vine={moved_on}')

clear_enemies()
place(home)
run(0.3)
golem = loose('golem', 18, 0)
quick, flew = 0, 0
for _ in range(600):
    app.step()
    quick = max(quick, (golem.vx ** 2 + golem.vz ** 2) ** 0.5)
    flew = max(flew, golem.y)
    if p.hp < T.PLAYER_HP:
        break
check('a crystal golem rolls fast and leaps at the player', golem.size == T.GOLEM_SCALE and 14 < quick < 19
      and flew > 0.3 and p.hp == T.PLAYER_HP - T.GOLEM_DAMAGE,
      f'size={golem.size} top speed={quick:.1f} m/s leapt {flew:.1f}m took {T.PLAYER_HP - p.hp}')

rates = []
for step in (1 / 60, 1 / 30):
    clear_enemies()
    place(home)
    clock.setDt(step)
    golem = loose('golem', 30, 0)
    golem.hit_cooldown = 99         # rolling, never leaping
    for _ in range(round(0.5 / step)):
        app.step()
        place(home)
    before = golem.roll
    for _ in range(round(1.0 / step)):
        app.step()
        place(home)
    rates.append(round(golem.roll - before))
clock.setDt(1 / 60)
check('a golem turns over at a pace the eye can follow, at any frame rate',
      all(150 < rate <= T.GOLEM_ROLL_MAX + 1 for rate in rates) and abs(rates[0] - rates[1]) < 40,
      f'degrees turned in a second at 60 and 30 fps={rates}')

clear_enemies()
place(home)
run(0.3)
miner = enemies.spawn('miner')
miner.pause = 0
below = (miner.hidden, miner.entity.enabled, enemies.damage(miner, 20), miner.hp == miner.max_hp,
         len(enemies.in_radius(miner.centre, 5)))
waited = 0
while miner.hidden and waited < 900:
    app.step()
    place(home)
    waited += 1
came_up = ((Vec3(miner.x, 0, miner.z) - Vec3(p.x, 0, p.z)).length(), miner.entity.enabled, miner.hole.enabled)
hit = enemies.damage(miner, 5) is False and miner.hp < miner.max_hp
attacks = set()
down_again = False
for _ in range(int((T.MINER_SURFACE[1] + T.MINER_DIG + 1.5) * 60)):
    app.step()
    place(home)
    attacks |= {m.kind.split('_')[0] for m in enemies.markers}     # pale or gold, a pick is a pick
    down_again = down_again or miner.hidden
check('a miner tunnels unseen, comes up out of a hole near the player, throws, and digs down again',
      below == (True, False, False, True, 0) and waited < 900 and came_up[0] < T.MINER_RANGE[1] + 2 and came_up[1]
      and came_up[2] and hit and attacks and attacks <= {'pick', 'rock', 'shard'} and down_again,
      f'underground (hidden, seen, hurt, unharmed, in a blast)={below}; up after {waited / 60:.1f}s, '
      f'{came_up[0]:.0f}m away; hittable={hit} thrown={attacks} dug down again={down_again}')

clear_enemies()
progress.cleared = 0
s.load_map('blender')
arena = s.map
place(polar(26, 200))
run(0.3)

# ---------------- health: rally, the bar, the runaway heart, minibosses ----------------

from ui import health as bar_module     # noqa: E402

clear_enemies()
place(polar(26, 200))
run(0.3)
held_rush = p.rush.update
p.rush.update = lambda speed, dt: None      # the meter stays where the check puts it
p.rush.value, p.rush.overdrive = 0.0, False
p.rally = 0.0
p.take_damage(30)
hit = (round(p.hp), round(p.rally))
run(T.RALLY_HOLD - 0.3)
held = round(p.rally, 1)
target = tough(20, 10)
s.on_hit(target, 20, target.centre, False)
cold = p.hp
p.rush.value, p.rush.overdrive = 100.0, True
s.on_hit(target, 20, target.centre, False)
hot = p.hp
s.on_hit(target, 1000, target.centre, False)
capped = (round(p.hp), round(p.rally))
p.rush.value, p.rush.overdrive = 0.0, False
p.invulnerable = 0
p.take_damage(20)
run(T.RALLY_HOLD + 1.0)
drained = round(p.rally, 1)
check('rally: a hit can be won back for a while, but only by hitting in Overdrive', hit == (70, 30) and held == 30
      and cold == 70 and abs(hot - (70 + 20 * T.RALLY_SHARE)) < 0.01 and capped == (100, 0)
      and 20 - T.RALLY_DRAIN * 1.3 < drained < 20 - T.RALLY_DRAIN * 0.7,
      f'after a 30 hit (hp, rally)={hit}, held={held}; outside Overdrive hp={cold}, in it {hot:.1f}, then {capped}; '
      f'a 20 hit {T.RALLY_HOLD + 1:.0f}s later={drained}')

bar = s.hud.health
p.hp, p.rally = 100.0, 0.0
run(0.5)
p.take_damage(40)
run(0.05)
ghosting = round(bar.ghost_at, 2)
run(1.5)
settled = (round(bar.fill.scale_x / bar_module.WIDTH, 2), round(bar.ghost_at, 2),
           round((bar.rally.x - bar_module.X) / bar_module.WIDTH, 2), round(bar.rally.scale_x / bar_module.WIDTH, 2))
glow = []
p.hp, p.rally = 20.0, 0.0
for _ in range(90):
    app.step()
    glow.append(bar.vignette.color[3])
p.hp = 60.0
run(0.2)
check('the health bar eases, its ghost lingers, the rally sits on top, and it beats when low',
      ghosting == 1.0 and settled == (0.6, 0.6, 0.6, 0.4) and max(glow) > 0.2 and bar.vignette.color[3] == 0,
      f'ghost just after a hit={ghosting}; a second later (fill, ghost, rally from, rally width)={settled}; '
      f'low-health glow up to {max(glow):.2f}, gone above 30={bar.vignette.color[3] == 0}')
p.rush.update = held_rush

# the runaway heart
clear_enemies()
progress.cleared = 0
director.hearts = True
director.start()
heart = s.heart
spot = Vec3(p.position)
run(T.ROUND_INTRO + 0.1)
for _ in range(600):
    director.spawn_timer = 0
    app.step()
    p.position, p.hp = spot, T.PLAYER_HP
    if director.total - director.left < director.total * T.HEART_AFTER and enemies.alive:
        enemies.damage(enemies.alive[0], 99999)
    if heart.loose:
        break
released = (heart.loose, director.total - director.left >= director.total * T.HEART_AFTER - 1)
director.hearts = False
director.state = 'idle'
clear_enemies()
heart.x, heart.z = spot.x + 4, spot.z + 4     # close by, to see it run
# first the health bar shows it getting out: the heart in the arena waits, its clock stopped
escaping, biggest = [], 0.0
for _ in range(int(T.HEART_ESCAPE * 60) - 6):
    app.step()
    p.position, p.vel = spot, Vec3(0, 0, 0)
    escaping.append((heart.visible, heart.time_left == T.HEART_TIME, bar.chase.enabled))
    biggest = max(biggest, bar.heart.scale_x)
for _ in range(12):
    app.step()
    p.position, p.vel = spot, Vec3(0, 0, 0)
escaped = (all(e == (False, True, False) for e in escaping), round(biggest, 2), heart.visible, bar.scene is None,
           bar.hollow.enabled, bar.chase.enabled, heart.time_left < T.HEART_TIME)
gaps = []
for _ in range(120):
    app.step()
    p.position, p.vel = spot, Vec3(0, 0, 0)
    gaps.append((Vec3(heart.x, 0, heart.z) - Vec3(p.x, 0, p.z)).length())
p.hp = 50.0
p.rally = 0.0
seen = []
p.position = heart.centre - Vec3(0, T.PLAYER_HEIGHT / 2, 0)
for _ in range(300):
    app.step()
    p.vel = Vec3(0, 0, 0)
    if not seen or p.hp != seen[-1]:
        seen.append(p.hp)
poured = (heart.loose, bar.loose, seen[0], seen[-1], len(seen) - 1, bar.heart.enabled,
          (round(bar.heart.x, 3), round(bar.heart.y, 3)))
heart.release()
run(T.HEART_ESCAPE + 0.1)
p.position = spot
p.hp = 60.0
heart.time_left = 0.05
for _ in range(240):
    app.step()
    p.position, p.vel = spot, Vec3(0, 0, 0)
punched = p.hp
heart.release()
run(T.HEART_ESCAPE + 0.1)
p.hp = 5.0
heart.time_left = 0.05
for _ in range(240):
    app.step()
    p.position, p.vel = spot, Vec3(0, 0, 0)
check('the runaway heart leaves the bar, shows itself and gets out, runs, pours 30 back when caught and '
      'punches 10 when not',
      released == (True, True) and escaped == (True, escaped[1], True, True, True, True, True) and escaped[1] > 0.08
      and gaps[-1] > gaps[0] + 3
      and poured == (False, False, 50.0, 80.0, T.HEART_GLUGS, True, tuple(round(v, 3) for v in bar_module.SEAT))
      and punched == 50 and p.hp == 1 and not heart.loose,
      f'out={released}; escaping (all hidden, clock stopped, no chase line; biggest on screen; then shown, scene '
      f'over, seat empty, chase line, clock running)={escaped}; ran from {gaps[0]:.0f} to {gaps[-1]:.0f} m; caught '
      f'(loose, seat empty, hp before, after, glugs, seated, at)={poured}; missed at 60 hp={punched}, at 5 hp={p.hp}')

# the miniboss and its beacon
director.beacons = True
p.invulnerable = 1e6


def to_beacon():
    clear_enemies()
    director.start()
    director.round = T.BEACON_AFTER - 1
    director.queue.clear()
    director.state = 'fight'
    app.step()


to_beacon()
offered = (director.state, s.beacon.live, round(director.timer, 1))
run(T.BEACON_TIME + 0.2)
ignored = (director.round, director.state, s.beacon.live)
to_beacon()
place(Vec3(s.beacon.x, 0, s.beacon.z) + Vec3(0, 0, -12) if (s.beacon.z > -40) else Vec3(s.beacon.x, 0, s.beacon.z + 12))
p.invulnerable = 1e6
aim_at(s.beacon.position + Vec3(0, 3, 0))
arsenal.select(0)
arsenal.cooldown = 0
arsenal.fire()
shot = director.state
run(T.BOSS_INTRO + 0.1)
boss = director.boss
size_hp = T.ASTRO_HP * director.hp_scale * T.BOSS_SIZE ** 1.5
built = (boss.kind, boss.size, round(boss.max_hp / size_hp, 2), boss.pace, boss.might)
p.invulnerable = 0
p.hp = T.PLAYER_HP
boss.strike(p, 10, 0, 1, 0)
struck = round(T.PLAYER_HP - p.hp, 1)
thrown = enemies.throw(boss, boss.centre, Vec3(0, 0, 1), (1, 1, 1, 1))
thrown_damage = round(thrown.damage, 1) if thrown else None
refused = enemies.convert(boss, 'fighter', 5)
director.hearts = True
run(1.0)
no_heart = not heart.loose
director.hearts = False
p.invulnerable = 1e6
p.hp = 30
director.boss_time = 30 - 1 / 60
enemies.damage(boss, 99999)
run(0.1)
healed = p.hp
check('after round 3 a beacon offers the miniboss, a giant that heals you more the quicker it dies',
      offered == ('clear', True, T.BEACON_TIME) and ignored == (T.BEACON_AFTER, 'intro', False) and shot == 'boss_intro'
      and built == ('thrower', T.BOSS_SIZE, 6.0, 1.5, 1.2) and struck == 12 and thrown_damage == round(T.MARKER_DAMAGE * 1.2, 1)
      and refused is False and no_heart and healed == 95 and director.state == 'clear'
      and [director.boss_heal(t) for t in (10, 30, 60)] == [100, 65, 30],
      f'offered={offered} ignored -> (round, state, beacon)={ignored}; shot -> {shot}; giant (kind, size, health '
      f'x, pace, might)={built}; a 10 blow does {struck}, a throw {thrown_damage}; converted={refused}; '
      f'heart stayed in={no_heart}; killed at 30 s from 30 hp -> {healed}')

giants = {}
for level in LEVELS:
    clear_enemies()
    giant = enemies.spawn_boss(level.boss, 20, 10)
    giants[level.name] = (giant.kind, round(giant.max_hp / (T.ASTRO_HP * giant.HP * T.BOSS_SIZE ** 1.5), 2),
                          giant.pace, giant.might, giant.boss.name)
clear_enemies()
check('each level has its miniboss', [g[0] for g in giants.values()] == ['thrower', 'lobber', 'miner']
      and [g[1:4] for g in giants.values()] == [(6.0, 1.5, 1.2), (8.0, 1.2, 1.2), (5.2, 1.3, 1.3)],
      f'{giants}')
director.beacons = False
director.state = 'idle'
s.beacon.clear()
s.hud.boss_bar.hide()
p.invulnerable = 0
clear_enemies()
progress.cleared = 0
s.load_map('blender')
arena = s.map
place(polar(26, 200))
run(0.3)

# ---------------- perk blasts and lettering ----------------

def burst_looks(go):
    """The palettes of the pixels `go` sets off."""
    s.pixels.clear()
    go()
    alive = s.pixels.age < s.pixels.life
    return {fxpixels.LOOKS[k] for k in s.pixels.look[alive]}


equip(('combust',), popper='flame')
near, far = pair()
near.ignite(8, 3)
near.hp = 1
combust = burst_looks(lambda: enemies.damage(near, 5))
equip(('shatter',), scatter='ice')
near, far = pair()
near.chill(0.45, 2.5)
near.hp = 1
shatter = burst_looks(lambda: enemies.damage(near, 5))
equip(('legion',), buzzer='dark')
near, far = pair()
enemies.convert(near, 'fighter', 0.05)
legion = burst_looks(lambda: run(0.2))
check('the perks burst into pixels: Combust in fire, Shatter in frost, Legion in violet',
      'dragon' in combust and 'frost' in shatter and 'legion' in legion, f'{combust} {shatter} {legion}')
equip()
clear_enemies()

import ast  # noqa: E402

from ui import font  # noqa: E402

# every character in every string the game has must be in the alphabet, and nothing shown so
# far (the HUD, the menus, the shop, numbers and names put together while playing) was missing
written = set()
for path in list(Path('.').glob('*.py')) + [f for folder in ('ui', 'game', 'data', 'fx') for f in Path(folder).rglob('*.py')]:
    for node in ast.walk(ast.parse(path.read_text(encoding='utf-8'))):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            written |= set(node.value)
unknown = {c for c in written if c not in '\n\t\r' and c.upper() not in font.GLYPHS}
lettered = font.Label('AB\nC', origin=(0.5, 0.5), scale=2)
placed, wide, tall = font.layout('AB\nC', (0.5, 0.5))
again = font.string_geom('AB\nC', 'block', (0.5, 0.5)) is font.string_geom('AB\nC', 'block', (0.5, 0.5))
spaced = font.Label('HI THERE', letters=True)
small = font.Label('tiny', scale=0.8)
built = (lettered.text, lettered.style, lettered.extent, [(c, x, y) for c, x, y in placed],
         sum(g.enabled for g in spaced.glyphs), spaced.style, small.style, small.text)
for label in (lettered, spaced, small):
    label.enabled = False
check('the lettering: one pixel alphabet for everything the game prints, set in blocks or flat',
      not unknown and not font.MISSING
      and built == ('AB\nC', 'block', (11, 17), [('A', -11, -7), ('B', -5, -7), ('C', -5, -17)], 7, 'flat', 'flat', 'tiny')
      and again, f'not in the alphabet: {sorted(unknown)} missed while playing: {sorted(font.MISSING)}; '
      f'(text, style, size, placed, letters, small styles, text)={built}; cached={again}')

# ---------------- the visual pass ----------------

from ursina import Entity, scene
from fx import shaders, toon
from fx.postfx import DEFAULTS as POST_DEFAULTS

probe = Entity(model='cube')
inherited = all(scene.getShaderInput(name).getValueType() != 0 for name in ('flash', 'status', 'gold', 'dull', 'fog', 'pattern'))
outline_luma = 0.299 * toon.OUTLINE[0] + 0.587 * toon.OUTLINE[1] + 0.114 * toon.OUTLINE[2]
own_inputs = set(shaders.toon_shader.default_input)
probe.enabled = False
check('one toon shader draws everything, its effects set once at the root so every limb follows',
      probe.shader is shaders.toon_shader and inherited and outline_luma < shaders.INK
      and not own_inputs & {'flash', 'status', 'gold', 'dull', 'fog', 'fog_range', 'pattern', 'pattern_tex'},
      f'default={probe.shader.name} roots set={inherited} outline luma={outline_luma:.3f} < ink {shaders.INK}; '
      f'per-entity inputs={sorted(own_inputs)}')

post = s.postfx
s.was_overdrive = p.rush.overdrive      # nothing the game does about Overdrive steps in
post.set('saturation', 1.35)
post.pulse('aberration', 0.006, 0.1)
post.edge((1, 0.5, 0.2), 0.6)
run(0.05)
eased = post.values['saturation']
pulsing = post.now('aberration') > 0
run(1)
settled = abs(post.values['saturation'] - post.targets['saturation']) < 0.02 and 'aberration' not in post.pulses
post.set('saturation', 1.0)
post.edge((1, 1, 1), 0)
run(1)
check('the full-screen effects ease and pulse, and do nothing harmful where the picture cannot be filtered',
      1.0 < eased < 1.35 and pulsing and settled and set(POST_DEFAULTS) >= {'saturation', 'aberration', 'wipe'},
      f'filtered={post.active} saturation after 0.05 s={eased:.2f}, settled={settled}, pulse seen={pulsing}')

clear_enemies()
place(polar(26, 200), yaw=290)
kept_unlocked, kept_branches = dict(s.progress.unlocked), dict(s.progress.branches)
s.progress.unlocked, s.progress.branches = {'BOOMER': ['poison', 'tiger']}, {'BOOMER': 'poison'}
mods.rebuild()
arsenal.equip()
arsenal.select(2, quiet=True)
arsenal.cooldown = 0
arsenal.fire()
flying = sum(r['live'] for r in arsenal.rockets)
s.progress.branches = {'BOOMER': 'tiger'}
mods.rebuild()
arsenal.equip()
crashed = None
try:
    run(1)
except Exception as error:      # the rocket asked the new branch for the old one's numbers
    crashed = repr(error)
s.progress.unlocked, s.progress.branches = kept_unlocked, kept_branches
mods.rebuild()
arsenal.equip()
arsenal.select(0, quiet=True)
check('a rocket in the air when its branch is swapped in the shop goes quietly',
      flying == 1 and crashed is None and not any(r['live'] for r in arsenal.rockets),
      f'in the air before the swap={flying}, error={crashed}')

clear_enemies()
place(polar(26, 200), yaw=290)
s.reset_chain()
chain = s.chain
tiers, pitches, music = [], [], []
real_play = s.sfx.play
s.sfx.play = lambda name, volume=1.0, pitch=1.0: (pitches.append(round(pitch, 2)) if name == 'kill' else None,
                                                   real_play(name, volume, pitch))
for n in range(5):
    victim = frozen(20, 3 + n * 2)
    enemies.damage(victim, 1e6)
    tiers.append(chain.tier)
    s.ticker.update()
    music.append([round(target, 2) for target in s.sfx.music_target])
s.sfx.play = real_play
badge = (s.hud.score.badge.enabled, s.hud.score.multiplier.text)
flying = sum(f['live'] for f in s.hud.score.flyers)
run(2)
landed = s.hud.score.score.text
p.invulnerable = 0
p.take_damage(5)
after_hit = chain.tier
run(T.CHAIN_WINDOW + 0.2)
check('kills climb the chain: each pops a note higher, the badge slams, music joins, the points fly to the score',
      tiers == [1, 2, 3, 4, 5] and pitches == sorted(pitches) and len(set(pitches)) == 5
      and badge == (True, 'X5') and flying == 5 and landed == f'{chain.score:,}' and chain.score > 0
      and music[0][:2] == [1.0, 0.0] and music[-1][:3] == [1.0, 1.0, 1.0] and music[-1][3] == 0.0,
      f'tiers={tiers} kill pitches={pitches} badge={badge} flying={flying} score={landed} of {chain.score} '
      f'music targets after 1 and 5 kills={music[0]}, {music[-1]}')
check('a hit knocks the chain down two tiers; letting it lapse loses it and the badge goes',
      after_hit == 3 and chain.tier == 0 and not s.hud.score.badge.enabled,
      f'after a hit at x5: x{after_hit}; after {T.CHAIN_WINDOW} s: x{chain.tier}, badge={s.hud.score.badge.enabled}')

clear_enemies()
place(polar(26, 200), yaw=290)
target = frozen(20, 3)
target.hp = 1e6
enemies.damage(target, 1)
run(1 / 60)
flashed = target.look.shown.get('flash')
run(0.3)
settled = target.look.shown.get('flash')
tints = {}
for name, how in (('burn', lambda e: e.ignite(1, 1)), ('poison', lambda e: e.envenom(1, 1)),
                  ('cold', lambda e: e.chill(0.3, 1)), ('stun', lambda e: e.stagger(1))):
    how(target)
    run(0.1)
    tints[name] = (round(target.look.shown['status'][3], 2) > 0 or target.look.shown['dull'][0] > 0,
                   target.stars is not None and target.stars.enabled)
    run(1.6)
cleared = target.look.shown['status'] == (0.0, 0.0, 0.0, 0.0) and target.look.shown['dull'] == (0.0,)
pixels_before = int((s.pixels.age < s.pixels.life).sum())
enemies.damage(target, 1e9)
dying = (target in enemies.corpses, target.entity.enabled, target.look.shown.get('flash'))
pixels_after = int((s.pixels.age < s.pixels.life).sum())
run(0.1)
gone = target not in enemies.corpses and not target.entity.enabled
green_mini = enemies.shot_mesh('mini_green').colors[0][:3] != enemies.shot_mesh('mini').colors[0][:3]
check('a hit flashes the body white inside its ink; fire, poison, cold and a stun each show; a kill pops white and bursts',
      flashed == (1.0,) and settled == (0.0,) and all(shown for shown, _ in tints.values()) and tints['stun'][1]
      and cleared and dying == (True, True, (1.0,)) and pixels_after - pixels_before >= 30 and gone and green_mini,
      f'flash {flashed}->{settled} statuses (shown, stars)={tints} cleared={cleared} dying={dying} '
      f'pixels +{pixels_after - pixels_before} gone after={gone} pale green mini={green_mini}')

effects_file = Path(scratch.name) / 'effects.json'
saved_effects = Settings(effects_file)
saved_effects.effects = False
saved_effects.save()
check('the effects can be turned off on the menu, and it is remembered', Settings(effects_file).effects is False,
      f'after a save and load: effects={Settings(effects_file).effects}')

# ---------------- performance ----------------

clear_enemies()
place(polar(26, 200), yaw=290)
p.boost_cooldown = 0
arena.knock_cooldown = 0
keys(w=1)
enemies.mix = None          # the ship's crew, whatever level was played last
enemies.input(T.KEY_SPAWN_MANY)
run(1)
start = perf_counter()
for i in range(300):
    if i % 9 == 0:
        arsenal.fire()
    app.step()
ms = (perf_counter() - start) / 300 * 1000
check('40 enemies frame time', len(enemies.alive) >= 25 and ms < 12,
      f'{ms:.2f} ms/frame of game logic with {len(enemies.alive)} enemies (16.7 ms is 60 fps)')

print(f'\n{sum(results)}/{len(results)} passed')
sys.exit(0 if all(results) else 1)
