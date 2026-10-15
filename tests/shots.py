"""Pictures of every map, enemy, weapon and screen, drawn offscreen, to look a visual change over
before and after. Run: py tests/shots.py [group ...]   groups: maps enemies weapons screens
They are written to tests/shots/ (not kept in git). Nothing the player owns is read or written."""
import sys
import traceback
from math import cos, radians, sin
from pathlib import Path
from tempfile import TemporaryDirectory

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from panda3d.core import ClockObject, Filename
from ursina import Vec3, camera, mouse, window

# an offscreen buffer has no pointer to lock or read
type(mouse).locked = property(lambda self: False, lambda self, value: None)
type(mouse).x = property(lambda self: 0.0)
type(mouse).y = property(lambda self: 0.0)
type(mouse).position = property(lambda self: Vec3(0, 0, 0))

import main
from data.levels import LEVELS
from data.settings import Settings
from game import mods

OUT = Path(__file__).resolve().parent / 'shots'
GROUPS = ('maps', 'enemies', 'weapons', 'screens')
LINEUP = {'blender': ('brawler', 'thrower', 'sniper'), 'jungle': ('croc', 'snapper', 'lobber'),
          'cave': ('golem', 'miner', 'monkey')}
VARIANTS = (dict(green=False), dict(green=True), dict(special='gold'), dict(special='glow', green=False))
BRANCHES = (('POPPER', 'flame', 0), ('POPPER', 'taser', 0), ('SCATTER', 'impulse', 1), ('SCATTER', 'ice', 1),
            ('BOOMER', 'tiger', 2), ('BOOMER', 'poison', 2), ('BUZZER', 'dark', 3), ('BUZZER', 'light', 3),
            ('LONGSHOT', 'dragon', 4), ('LONGSHOT', 'semi', 4))

OUT.mkdir(exist_ok=True)
scratch = TemporaryDirectory()
app = main.build(mute=True, settings=Settings(Path(scratch.name) / 'settings.json'), window_type='offscreen')
# the window module sets the UI lens when a real window changes shape; offscreen it never does
camera.ui_lens.set_film_size(camera._ui_size * 0.5 * window.aspect_ratio, camera._ui_size * 0.5)
clock = ClockObject.getGlobalClock()
clock.setMode(ClockObject.MNonRealTime)
clock.setDt(1 / 60)
s = app.session
p, enemies = s.player, s.enemies
s.juice.hitstop_enabled = False
s.director.auto = s.director.hearts = s.director.beacons = False
s.progress.path = Path(scratch.name) / 'progress.json'


def run(frames):
    for _ in range(frames):
        app.step()


def shot(name):
    app.graphicsEngine.renderFrame()
    app.graphicsEngine.renderFrame()
    app.win.saveScreenshot(Filename.fromOsSpecific(str(OUT / f'{name}.png')))
    print('shot', name)


def place(position, yaw, pitch=0.0):
    p.position = Vec3(*position)
    p.rotation_y = yaw
    p.pivot.rotation_x = pitch
    p.vel = Vec3(0, 0, 0)
    p.hp = 100
    p.invulnerable = 1e9


def ahead(distance, side=0.0):
    yaw = radians(p.rotation_y)
    return (p.x + sin(yaw) * distance + cos(yaw) * side, p.z + cos(yaw) * distance - sin(yaw) * side)


def frozen(kind, x, z, **how):
    enemy = enemies.spawn(kind, x, z, **how)
    if enemy is not None:
        enemy.spawning = 0
        enemy.pause = 1e9
    return enemy


def at_spawn(name):
    s.load_map(name)
    enemies.clear()
    s.pickups.clear()
    place(s.map.spawn_position, s.map.spawn_yaw)
    run(20)


def maps():
    for name in LINEUP:
        at_spawn(name)
        shot(f'map_{name}_spawn')
        place(Vec3(*s.map.spawn_position) + Vec3(0, 12, 0), s.map.spawn_yaw, 18)
        run(5)
        shot(f'map_{name}_overview')
        place(s.map.spawn_position, s.map.spawn_yaw + 180)
        run(5)
        shot(f'map_{name}_behind')


def lineup(name):
    lined = []
    for row, kind in enumerate(LINEUP[name]):
        for col, how in enumerate(VARIANTS):
            x, z = ahead(9 + row * 3.5, -6 + col * 4)
            lined.append(frozen(kind, x, z, **how))
    return [e for e in lined if e is not None]


def enemies_group():
    for name in LINEUP:
        at_spawn(name)
        lined = lineup(name)
        run(30)
        shot(f'enemy_{name}_lineup')
        for enemy in lined:
            enemy.flash = 0.07
        run(1)
        shot(f'enemy_{name}_flash')
        for enemy, status in zip(lined, ('burn', 'poison', 'slow', 'stun', 'freeze', 'fighter', 'healer')):
            if status == 'burn':
                enemy.ignite(1, 30)
            elif status == 'poison':
                enemy.envenom(1, 30)
            elif status == 'slow':
                enemy.chill(0.4, 30)
            elif status == 'freeze':
                enemy.chill(0.4, 30, freeze=True)
            elif status == 'stun':
                enemy.stagger(30)
            else:
                enemies.convert(enemy, status, 30)
        run(20)
        shot(f'enemy_{name}_status')
        enemies.clear()
        x, z = ahead(16)
        boss = enemies.spawn_boss(LEVELS[list(LINEUP).index(name)].boss, x, z)
        if boss is not None:
            boss.spawning = 0
            boss.pause = 1e9
        run(30)
        shot(f'enemy_{name}_boss')
        for enemy in list(enemies.alive):
            enemies.damage(enemy, 1e9)
        run(3)
        shot(f'enemy_{name}_boss_death')
        lined = lineup(name)
        run(10)
        for enemy in lined:
            enemies.damage(enemy, 1e9)
        run(2)
        shot(f'enemy_{name}_deaths')
        run(10)
        shot(f'enemy_{name}_deaths_later')
        enemies.clear()


def fire_weapon(label, index):
    s.arsenal.select(index, quiet=True)
    run(30)
    shot(f'weapon_{label}_idle')
    s.arsenal.cooldown = 0
    s.arsenal.fire()
    app.step()
    shot(f'weapon_{label}_fire')
    run(4)
    shot(f'weapon_{label}_fire_later')
    run(30)


def weapons():
    at_spawn('blender')
    s.arsenal.endless = True
    for x, z in (ahead(14, -2), ahead(14, 2)):
        frozen('brawler', x, z, green=False)
    run(10)
    for index, weapon in enumerate(list(s.arsenal.weapons)):
        fire_weapon(weapon.name.lower(), index)
    for slot, branch, index in BRANCHES:
        s.progress.unlocked = {slot: [branch]}
        s.progress.branches = {slot: branch}
        mods.rebuild()
        s.arsenal.equip()
        fire_weapon(f'{slot.lower()}_{branch}', index)
    s.progress.unlocked, s.progress.branches = {}, {}
    mods.rebuild()
    s.arsenal.equip()
    s.katana.slash()
    run(3)
    shot('weapon_katana_slash')
    run(30)


def screens():
    at_spawn('blender')
    s.director.auto = True
    s.director.start()
    run(240)
    shot('screen_hud')
    for n in range(6):
        x, z = ahead(10, -4 + n * 1.6)
        enemies.damage(frozen('brawler', x, z, green=False), 1e9)
        run(4)
    shot('screen_chain')
    run(60)
    shot('screen_chain_landed')
    s.director.auto = False
    s.open_shop()
    run(150)
    shot('screen_tally_counting')
    for _ in range(600):
        app.step()
        if s.tally.done:
            break
    run(20)
    shot('screen_tally_done')
    s.tally.input('space')
    run(60)
    shot('screen_shop_after_level')
    s.shop.close()
    run(10)
    from ui.menus import Menu
    s.menu = Menu(s)
    s.menu.open()
    run(40)
    shot('screen_menu')
    s.menu.close()
    run(10)
    s.shop.open(after_level=False)
    run(120)
    shot('screen_shop')


if __name__ == '__main__':
    wanted = [g for g in sys.argv[1:] if g in GROUPS] or list(GROUPS)
    for group in wanted:
        try:
            {'maps': maps, 'enemies': enemies_group, 'weapons': weapons, 'screens': screens}[group]()
        except Exception:
            traceback.print_exc()
    print('pictures in', OUT)
