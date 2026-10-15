"""The upgrade shop, open between levels: a ship's terminal, all blue light. A tab for each weapon;
on it the weapon's two branches, each opened with a key and chips and then carried or put away,
and the skill tree of the branch picked, bought node by node with chips.

Everything that is bought answers: sparks, a ring, light running down the tree, the counter
rolling. The match is frozen underneath, so all of it runs on real time."""
from math import atan2, degrees, exp, pi, sin

from PIL import Image
from ursina import Circle, Entity, Texture, Vec3, camera, clamp, color, mouse, time

from data import tuning as T
from data.trees import BASE, PERKS, TREES
from game import mods
from ui.font import Label
from ui.hud import GOLD, glow_texture, ring_texture

WEAPONS = tuple(BASE)       # one tab each, in slot order
FRAME = (1.62, 0.88)
ROW_TITLE, ROW_RULE = 0.39, 0.345
TAB_X, TAB_Y, TAB_STEP, TAB_WIDTH, TAB_HEIGHT = -0.645, 0.275, 0.082, 0.27, 0.066
CARD_X, CARD_Y, CARD_WIDTH, CARD_HEIGHT = (-0.225, 0.265), 0.24, 0.47, 0.16
PLAIN_X, PLAIN_WIDTH = 0.655, 0.25
TREE_X, TREE_Y, TREE_STEP_X, TREE_STEP_Y = -0.4, -0.09, 0.2, 0.125
NODE_SIZE, PERK_SIZE = 0.062, 0.08
DETAIL_X, DETAIL_Y, DETAIL_WIDTH, DETAIL_HEIGHT = 0.565, -0.09, 0.43, 0.42
GO_X, ROW_GO, GO_WIDTH, GO_HEIGHT = 0.63, -0.385, 0.3, 0.07
NOTE_X = -0.47
NOTE_TIME = 2.5
OPEN_TIME = 0.3
RINGS, PULSES = 3, 8

# the terminal's light: deep navy glass, cyan lines, white where it is hottest; gold is money
NAVY = color.hsv(222, 0.8, 0.1)
GLASS = color.hsv(218, 0.75, 0.17)
STEEL = color.hsv(214, 0.6, 0.34)       # lines and words that are switched off
BLUE = color.hsv(210, 0.85, 0.95)
CYAN = color.hsv(188, 0.8, 1)
ICE = color.hsv(195, 0.2, 1)
RED = color.hsv(352, 0.75, 1)


def node_at(node):
    """Where a node sits on the board."""
    return TREE_X + node.at[0] * TREE_STEP_X, TREE_Y + node.at[1] * TREE_STEP_Y


def faded(tint, alpha):
    return color.Color(tint[0], tint[1], tint[2], alpha)


def mixed(a, b, t):
    return color.Color(a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t, a[2] + (b[2] - a[2]) * t, 1)


def lines_texture(size=64, every=16, both=True):
    """Thin lines one pixel wide: a grid, or with `both` off the scanlines of a screen."""
    image = Image.new('RGBA', (size, size), (255, 255, 255, 0))
    pixels = image.load()
    for y in range(size):
        for x in range(size):
            if y % every == 0 or (both and x % every == 0):
                pixels[x, y] = (255, 255, 255, 255)
    return Texture(image, filtering='bilinear')


class Shop(Entity):
    def __init__(self, game):
        super().__init__(parent=camera.ui, z=-6, ignore_paused=True)
        self.game = game
        self.is_open = False
        self.after_level = False    # opened by clearing a level, not from the title screen
        self.weapon = WEAPONS[0]
        self.pick = {}              # weapon -> the branch whose tree is on the board
        self.armed = None
        self.hover = None
        self.clock = 0.0
        self.opened = 0.0           # seconds since it opened
        self.boot = 0.0             # seconds since the tree on the board changed
        self.note_time = 0.0
        self.punch = 0.0            # the whole board jumps when something is bought
        self.flash_time = 0.0
        self.shown_chips = 0.0      # the counter rolls to the real number
        self.focus = None           # index of the node the detail panel is about
        self.buttons = {}           # name -> {'x', 'y', 'width', 'height', 'visible', 'shake', 'parts', ...}

        # nothing on the board acts by itself, so the engine is told to skip it all each frame
        self.screen = Entity(parent=self, enabled=False, ignore=True)
        self.quad(0, 0, 4, 2, faded(NAVY, 0.94), z=1, parent=self.screen)
        self.grid = self.quad(0, 0, 1.8, 1.0, faded(BLUE, 0.07), z=0.9, parent=self.screen, texture=lines_texture(),
                              texture_scale=(36, 20))
        board = self.board = Entity(parent=self.screen, ignore=True)
        self.quad(0, 0, FRAME[0], FRAME[1], faded(GLASS, 0.82), z=0.5)
        self.scan = self.quad(0, 0, FRAME[0], FRAME[1], faded(CYAN, 0.05), z=0.4, texture=lines_texture(every=4, both=False),
                              texture_scale=(1, 30))
        self.sweep = self.quad(0, 0, FRAME[0], 0.05, faded(CYAN, 0.06), z=0.35, texture=glow_texture())
        w, h = FRAME[0] / 2, FRAME[1] / 2
        for x, y, width, height in ((0, h, FRAME[0], 0.003), (0, -h, FRAME[0], 0.003), (-w, 0, 0.003, FRAME[1]),
                                    (w, 0, 0.003, FRAME[1]), (0, ROW_RULE, FRAME[0] - 0.06, 0.002)):
            self.quad(x, y, width, height, faded(BLUE, 0.6), z=0.3)
        for sx in (-1, 1):          # brackets clamped on the corners
            for sy in (-1, 1):
                self.quad(sx * (w - 0.04), sy * h, 0.09, 0.008, CYAN, z=0.25)
                self.quad(sx * w, sy * (h - 0.04), 0.008, 0.09, CYAN, z=0.25)

        self.title = Label(parent=board, text='', origin=(-0.5, 0), position=(-0.77, ROW_TITLE, -0.02), scale=2.1, color=CYAN)
        Label(parent=board, text='UPGRADE TERMINAL  //  ENGINE DECK', origin=(-0.5, 0), position=(-0.5, ROW_TITLE - 0.006, -0.02),
             scale=0.75, color=STEEL)
        self.chips = Label(parent=board, text='', origin=(0.5, 0), position=(0.77, ROW_TITLE, -0.02), scale=1.5, color=GOLD)
        self.keys = Label(parent=board, text='', origin=(0.5, 0), position=(0.45, ROW_TITLE, -0.02), scale=1.5, color=GOLD)
        self.header = Label(parent=board, text='', origin=(-0.5, 0), position=(NOTE_X, 0.125, -0.02), scale=0.8, color=STEEL)
        self.empty = Label(parent=board, text='NO BRANCHES FOR THIS ONE YET.', origin=(-0.5, 0),
                          position=(NOTE_X, 0.2, -0.02), scale=1.0, color=STEEL)
        self.note = Label(parent=board, text='', origin=(-0.5, 0), position=(NOTE_X, ROW_GO, -0.02), scale=0.95, color=ICE)

        for i, weapon in enumerate(WEAPONS):
            tab = self.add_button(f'tab {weapon}', TAB_X, TAB_Y - i * TAB_STEP, TAB_WIDTH, TAB_HEIGHT)
            tab['text'] = self.words(tab, weapon, -TAB_WIDTH / 2 + 0.03, 0, 1.0)
            tab['mark'] = self.quad(-TAB_WIDTH / 2 + 0.006, 0, 0.008, TAB_HEIGHT, CYAN, z=-0.01, parent=tab['holder'])
        # a branch: its name, what it does, and on the bottom edge whether it is locked, owned or carried
        self.cards = []
        for i, x in enumerate(CARD_X):
            card = self.add_button(f'branch {i}', x, CARD_Y, CARD_WIDTH, CARD_HEIGHT)
            left = -CARD_WIDTH / 2 + 0.02
            card['name'] = self.words(card, '', left, 0.048, 1.5)
            card['blurb'] = self.words(card, '', left, 0.0, 0.62)
            card['state'] = self.words(card, '', left, -0.055, 0.8)
            card['mark'] = self.quad(0, -CARD_HEIGHT / 2 + 0.004, CARD_WIDTH, 0.008, CYAN, z=-0.01, parent=card['holder'])
            self.cards.append(card)
        plain = self.add_button('plain', PLAIN_X, CARD_Y, PLAIN_WIDTH, CARD_HEIGHT)
        plain['name'] = self.words(plain, '', -PLAIN_WIDTH / 2 + 0.02, 0.048, 1.2)
        plain['blurb'] = self.words(plain, 'THE WEAPON AS IT\nCAME, NO BRANCH.', -PLAIN_WIDTH / 2 + 0.02, 0.0, 0.62)
        plain['state'] = self.words(plain, '', -PLAIN_WIDTH / 2 + 0.02, -0.055, 0.8)
        plain['mark'] = self.quad(0, -CARD_HEIGHT / 2 + 0.004, PLAIN_WIDTH, 0.008, CYAN, z=-0.01, parent=plain['holder'])

        # the tree: every branch has the same shape, so the board is laid out once from any of them
        shape = next(iter(TREES.values()))[0].nodes
        self.links = []             # {'entity', 'from', 'to'}: indices into the branch's nodes
        self.tree = []
        for i, node in enumerate(shape):
            x, y = node_at(node)
            for needed in node.requires:
                j = next(k for k, other in enumerate(shape) if other.id == needed)
                ax, ay = node_at(shape[j])
                length = ((x - ax) ** 2 + (y - ay) ** 2) ** 0.5
                line = self.quad((x + ax) / 2, (y + ay) / 2, length, 0.004, STEEL, z=0.1,
                                 rotation_z=-degrees(atan2(y - ay, x - ax)))
                self.links.append({'entity': line, 'from': j, 'to': i})
        for i, node in enumerate(shape):
            x, y = node_at(node)
            perk = i in PERKS
            size = PERK_SIZE if perk else NODE_SIZE
            button = self.add_button(f'node {i}', x, y, size + 0.02, size + 0.02, bare=True)
            holder = button['holder']
            sides = 4 if perk else 6
            button.update(
                size=size, pop=0.0, state='shut',
                halo=Entity(parent=holder, model='quad', texture=glow_texture(), scale=size * 3.2, z=0.05, color=CYAN,
                            ignore=True),
                rim=Entity(parent=holder, model=Circle(sides), scale=size + 0.014, z=0.02, color=STEEL, ignore=True),
                core=Entity(parent=holder, model=Circle(sides), scale=size, z=0.01, color=NAVY, ignore=True),
                level=Label(parent=holder, text='', origin=(0, 0), position=(0, 0, -0.02), scale=0.7, color=ICE),
                label=Label(parent=holder, text='', origin=(0, 0), position=(0, -size / 2 - 0.022, -0.02), scale=0.58,
                           color=ICE))
            self.tree.append(button)

        # what the node under the pointer is and costs
        self.quad(DETAIL_X, DETAIL_Y, DETAIL_WIDTH, DETAIL_HEIGHT, faded(NAVY, 0.7), z=0.2)
        for sy in (-1, 1):
            self.quad(DETAIL_X, DETAIL_Y + sy * DETAIL_HEIGHT / 2, DETAIL_WIDTH, 0.003, faded(BLUE, 0.7), z=0.15)
        left, top = DETAIL_X - DETAIL_WIDTH / 2 + 0.025, DETAIL_Y + DETAIL_HEIGHT / 2
        self.detail = {
            'name': Label(parent=board, text='', origin=(-0.5, 0), position=(left, top - 0.045, -0.02), scale=1.3, color=CYAN),
            'body': Label(parent=board, text='', origin=(-0.5, 0.5), position=(left, top - 0.09, -0.02), scale=0.8, color=ICE),
            'level': Label(parent=board, text='', origin=(-0.5, 0), position=(left, top - 0.27, -0.02), scale=0.8, color=STEEL),
            'cost': Label(parent=board, text='', origin=(-0.5, 0), position=(left, top - 0.33, -0.02), scale=1.15, color=GOLD)}

        go = self.add_button('go', GO_X, ROW_GO, GO_WIDTH, GO_HEIGHT)
        go['text'] = self.words(go, 'NEXT LEVEL', 0, 0, 1.2, centred=True)

        # the fireworks: pixels (the HUD's, drawn over everything), rings that open out, and light
        # that runs along the tree
        self.pixels = game.hud.sparks
        self.rings = [{'entity': Entity(parent=board, model='quad', texture=ring_texture(), z=-0.09, enabled=False,
                                        ignore=True), 'life': 0.0} for _ in range(RINGS)]
        self.pulses = [{'entity': Entity(parent=board, model='quad', texture=glow_texture(), scale=0.05, z=-0.08,
                                         color=color.white, enabled=False, ignore=True), 'life': 0.0}
                       for _ in range(PULSES)]
        self.key = self.quad(0, 0, 0.03, 0.03, GOLD, z=-0.12, rotation_z=45, enabled=False)
        self.key_flight = None      # {'from', 'to', 't'} while a key is on its way to a branch
        self.flash = self.quad(0, 0, 4, 2, faded(ICE, 0), z=-0.2, parent=self.screen)

    def quad(self, x, y, width, height, tint, z=0.0, parent=None, **kwargs):
        return Entity(parent=parent or self.board, model='quad', position=(x, y, z), scale=(width, height), color=tint,
                      ignore=True, **kwargs)

    def words(self, button, text, x, y, scale, centred=False):
        return Label(parent=button['holder'], text=text, origin=(0, 0) if centred else (-0.5, 0), position=(x, y, -0.02),
                    scale=scale, color=ICE)

    def add_button(self, name, x, y, width, height, bare=False):
        """Something that can be pressed: a pane of glass in a lit frame, unless it is `bare`."""
        holder = Entity(parent=self.board, position=(x, y), ignore=True)
        button = {'holder': holder, 'x': x, 'y': y, 'width': width, 'height': height, 'visible': True, 'shake': 0.0,
                  'lit': False, 'tint': CYAN}
        if not bare:
            button['edge'] = self.quad(0, 0, width, height, STEEL, z=0.03, parent=holder)
            button['pane'] = self.quad(0, 0, width - 0.006, height - 0.006, NAVY, z=0.02, parent=holder)
        self.buttons[name] = button
        return button

    # --- opening and closing ---

    def open(self, after_level):
        self.is_open = True
        self.after_level = after_level
        self.armed = None
        self.focus = None
        self.opened = self.boot = 0.0
        self.shown_chips = float(self.game.progress.chips)
        self.screen.enabled = True
        self.buttons['go']['text'].text = 'NEXT LEVEL' if after_level else 'BACK'
        self.say('')
        self.refresh()

    def close(self):
        self.is_open = False
        self.screen.enabled = False
        self.game.shop_closed(self.after_level)

    def say(self, message, tint=ICE):
        self.note.text = message
        self.note.color = tint
        self.note_time = NOTE_TIME if message else 0.0

    # --- what is shown ---

    @property
    def branch(self):
        """The branch whose tree is on the board: the one last clicked, else the one carried."""
        branches = TREES.get(self.weapon)
        if not branches:
            return None
        held = mods.branch(self.weapon)
        wanted = self.pick.get(self.weapon, held.id if held else branches[0].id)
        return mods.find(self.weapon, wanted)

    def refresh(self):
        """Put what the player owns on the screen."""
        weapon, progress = self.weapon, self.game.progress
        self.keys.text = f'KEYS {progress.tokens}'
        branches = TREES.get(weapon, ())
        held, shown = mods.branch(weapon), self.branch
        self.empty.enabled = not branches

        for name in WEAPONS:
            tab = self.buttons[f'tab {name}']
            tab['lit'] = name == weapon
            carried = mods.branch(name)
            tab['text'].text = f'{name}' if carried is None else f'{name} / {carried.name}'
            tab['text'].scale = 1.0 if carried is None else 0.72
        for i, card in enumerate(self.cards):
            self.show(card, i < len(branches))
            if i >= len(branches):
                continue
            of = branches[i]
            owned = mods.unlocked(weapon, of.id)
            card['name'].text = of.name
            card['blurb'].text = of.blurb
            card['state'].text = ('CARRIED' if of is held else 'OWNED  //  CLICK TO CARRY' if owned
                                  else f'LOCKED  //  1 KEY + {T.BRANCH_COST} CHIPS')
            card['state'].color = CYAN if of is held else ICE if owned else GOLD
            card['lit'] = of is shown
            card['tint'] = CYAN if owned else STEEL
        plain = self.buttons['plain']
        self.show(plain, bool(branches))
        plain['name'].text = weapon
        plain['state'].text = 'CARRIED' if held is None else 'CLICK TO CARRY'
        plain['state'].color = CYAN if held is None else ICE
        plain['lit'] = False

        owned = shown is not None and mods.unlocked(weapon, shown.id)
        self.header.text = '' if shown is None else (f'{shown.name}  //  SKILL TREE' if owned
                                                      else f'{shown.name}  //  SKILL TREE  //  LOCKED')
        for i, button in enumerate(self.tree):
            self.show(button, shown is not None)
            if shown is None:
                continue
            node = shown.nodes[i]
            level, cost = mods.node_level(weapon, shown, node), mods.node_cost(weapon, shown, node)
            reachable = owned and mods.node_open(weapon, shown, node)
            button['state'] = ('shut' if not reachable else 'full' if cost is None else 'part' if level else 'open')
            button['afford'] = reachable and cost is not None and progress.chips >= cost
            button['level'].text = (('ON' if level else 'PERK') if i in PERKS else f'{level}/{len(node.costs)}')
            button['label'].text = node.label
        for link in self.links:
            link['entity'].enabled = shown is not None
            if shown is not None:
                link['lit'] = owned and mods.node_level(weapon, shown, shown.nodes[link['from']]) > 0
        for text in self.detail.values():
            text.enabled = shown is not None
        self.describe(self.focus)

    def describe(self, index):
        """Fill the detail panel for a node of the tree on the board, or with how the shop works."""
        shown, detail = self.branch, self.detail
        if shown is None:
            return
        weapon = self.weapon
        owned = mods.unlocked(weapon, shown.id)
        if index is None:
            detail['name'].text = shown.name
            detail['body'].text = ('POINT AT A NODE TO SEE IT.\nCLICK IT TO BUY A LEVEL.\n\nDIAMONDS ARE PERKS:\nTHEY ADD SOMETHING NEW.'
                                   if owned else 'OPEN THIS BRANCH WITH A KEY\nFROM A GOLDEN ENEMY, AND CHIPS.\nITS TREE IS BELOW.')
            detail['level'].text = detail['cost'].text = ''
            return
        node = shown.nodes[index]
        level, cost = mods.node_level(weapon, shown, node), mods.node_cost(weapon, shown, node)
        detail['name'].text = node.label
        if node.blurb:
            detail['body'].text = node.blurb
        else:
            (key, step), = node.effects.items()
            now = mods.numbers(weapon, shown)[key]
            detail['body'].text = (node.show.format(now) if cost is None
                                   else f'{node.show.format(now)}   >   {node.show.format(now + step)}')
        detail['level'].text = f'LEVEL {level}/{len(node.costs)}'
        missing = [other.label for other in shown.nodes
                   if other.id in node.requires and not mods.node_level(weapon, shown, other)]
        detail['cost'].text = ('BRANCH LOCKED' if not owned else 'FULL' if cost is None
                               else 'NEEDS ' + ' + '.join(missing) if missing else f'{cost} CHIPS')
        detail['cost'].color = GOLD if owned and cost is not None and not missing else STEEL

    def show(self, button, visible):
        button['holder'].enabled = button['visible'] = visible

    # --- buying ---

    def click(self, name):
        """A button was pressed and let go."""
        game, weapon = self.game, self.weapon
        if name == 'go':
            game.sfx.play('switch')
            self.close()
            return
        kind, _, which = name.partition(' ')
        if kind == 'tab':
            self.weapon = which
            self.focus = None
            self.boot = 0.0
            game.sfx.play('switch')
        elif kind == 'plain':
            if mods.branch(weapon) is not None:
                mods.equip_branch(weapon, None)
                self.carried(name, f'PLAIN {weapon} CARRIED')
        elif kind == 'branch':
            of = TREES[weapon][int(which)]
            if self.pick.get(weapon) != of.id:
                self.pick[weapon] = of.id
                self.focus = None
                self.boot = 0.0
            if not mods.unlocked(weapon, of.id):
                if not mods.unlock_branch(weapon, of.id):
                    short = T.BRANCH_COST - game.progress.chips
                    return self.refuse(name, 'NO KEY: GOLDEN ENEMIES DROP THEM' if game.progress.tokens < 1
                                       else f'{short} MORE CHIPS NEEDED')
                self.unlocked(name, of)
            elif mods.branch(weapon) is not of:
                mods.equip_branch(weapon, of.id)
                self.carried(name, f'{of.name} CARRIED')
        elif kind == 'node':
            index = int(which)
            of = self.branch
            node = of.nodes[index]
            cost = mods.node_cost(weapon, of, node)
            if not mods.unlocked(weapon, of.id):
                return self.refuse(name, 'OPEN THE BRANCH FIRST')
            if cost is None:
                return self.refuse(name, 'ALREADY FULL')
            if not mods.node_open(weapon, of, node):
                return self.refuse(name, 'THE NODES BEFORE IT COME FIRST')
            if not mods.buy_node(weapon, of.id, node.id):
                return self.refuse(name, f'{cost - game.progress.chips} MORE CHIPS NEEDED')
            self.bought(index, node)
        self.refresh()

    def carried(self, name, message):
        """A branch was taken up or put away: no money moved."""
        button = self.buttons[name]
        self.game.sfx.play('switch')
        self.game.refresh_weapons()
        self.burst(button['x'], button['y'], CYAN, 10, 0.5)
        self.punch = 0.4
        self.say(message)

    def bought(self, index, node):
        """A level of a node: it flares, throws sparks and a ring, and light runs on down the tree."""
        game = self.game
        button = self.tree[index]
        x, y = button['x'], button['y']
        perk = index in PERKS
        button['pop'] = 1.0
        self.burst(x, y, CYAN, 22 if perk else 12, 1.0 if perk else 0.7)
        self.ring(x, y, color.white, 0.32 if perk else 0.2)
        for link in self.links:
            if link['from'] == index:
                self.pulse((x, y), (self.tree[link['to']]['x'], self.tree[link['to']]['y']))
        self.punch = 1.0 if perk else 0.5
        if perk:
            self.flash_time = 0.25
        game.sfx.play('buy', pitch=1.25 if perk else 1.0)
        game.refresh_weapons()
        self.focus = index
        self.say(f'{node.label} ONLINE' if perk else f'{node.label} RAISED', CYAN)

    def unlocked(self, name, of):
        """A branch opened: the key flies in from the counter, and the card goes off."""
        game = self.game
        card = self.buttons[name]
        self.key_flight = {'from': (0.4, ROW_TITLE), 'to': (card['x'], card['y']), 't': 0.0, 'card': card}
        self.key.enabled = True
        game.sfx.play('unlock')
        game.refresh_weapons()
        self.boot = -0.25       # the tree waits for the key to land
        self.say(f'{of.name} IS YOURS', GOLD)

    def refuse(self, name, message):
        button = self.buttons[name]
        button['shake'] = 1.0
        self.game.sfx.play('deny')
        self.say(message, RED)

    # --- fireworks ---

    def burst(self, x, y, tint, count, power):
        """A burst of pixels: gold ones for gold, icy blue for the rest."""
        look = 'gold' if tint is GOLD else 'frost'
        at = self.board.getPos(camera.ui) + Vec3(x, y, -0.1)
        self.pixels.spray(at, look, count=count, speed=0.6 * power, size=0.005, life=0.55, up=0.15 * power, gravity=1.2,
                          drag=1.0)

    def ring(self, x, y, tint, size):
        ring = min(self.rings, key=lambda r: r['life'])
        ring.update(life=0.4, tint=tint, size=size)
        ring['entity'].position = (x, y, -0.09)
        ring['entity'].enabled = True

    def pulse(self, start, end):
        pulse = min(self.pulses, key=lambda p: p['life'])
        pulse.update(life=0.3, start=start, end=end)
        pulse['entity'].enabled = True

    # --- input ---

    def target_at(self, x, y):
        for name, button in self.buttons.items():
            if (button['visible'] and abs(x - button['x']) <= button['width'] / 2
                    and abs(y - button['y']) <= button['height'] / 2):
                return name
        return None

    def input(self, key):
        if not self.is_open:
            return
        if key == 'left mouse down':
            self.armed = self.target_at(mouse.x, mouse.y)
        elif key == 'left mouse up' and self.armed:
            name, self.armed = self.armed, None
            if self.target_at(mouse.x, mouse.y) == name:
                self.click(name)
        elif key == 'escape' and not self.after_level:
            self.close()

    # --- frame ---

    def update(self):
        if not self.is_open:
            return
        dt = min(time.dt_unscaled, 0.05)    # real time: the match is frozen underneath
        self.clock += dt
        self.opened += dt
        self.boot += dt
        if self.note_time > 0:
            self.note_time -= dt
            if self.note_time <= 0:
                self.note.text = ''
        x, y = mouse.x, mouse.y
        hover = self.target_at(x, y)
        if hover != self.hover:
            self.hover = hover
            if hover is not None:
                self.game.sfx.play('bar_tick', volume=0.25, pitch=1.3)
            focus = int(hover[5:]) if hover and hover.startswith('node ') else self.focus
            if focus != self.focus:
                self.focus = focus
                self.describe(focus)

        # the terminal itself: it unfolds, leans to the pointer, and its scanlines never stop
        follow = 1 - exp(-16 * dt)
        board = self.board
        unfold = clamp(self.opened / OPEN_TIME, 0, 1)
        self.punch *= exp(-9 * dt)
        board.scale_y = max(0.02, 1 - (1 - unfold) ** 3) * (1 + 0.025 * self.punch)
        board.scale_x = (0.9 + 0.1 * unfold) * (1 + 0.025 * self.punch)
        board.rotation_y += (x * 4 - board.rotation_y) * follow * 0.4
        board.rotation_x += (y * 4 - board.rotation_x) * follow * 0.4
        self.scan.texture_offset = (0, self.clock * 0.15 % 1)
        self.sweep.y = FRAME[1] / 2 - (self.clock * 0.25 % 1) * FRAME[1]
        typed = 'ARMORY'
        shown = typed[:int(self.opened * 22)]
        if shown != self.title.text:
            self.title.text = shown
        self.flash_time = max(0.0, self.flash_time - dt)
        self.flash.color = faded(ICE, 0.35 * self.flash_time / 0.25)

        self.roll_chips(dt)
        beat = 0.5 + 0.5 * sin(self.clock * 5)
        for name, button in self.buttons.items():
            if not button['visible']:
                continue
            holder = button['holder']
            button['shake'] = max(0.0, button['shake'] - dt * 3.5)
            shake = button['shake']
            holder.x = button['x'] + sin(shake * 40) * 0.012 * shake
            pressed = self.armed == name
            if 'core' in button:
                self.draw_node(button, name, hover == name, pressed, shake, beat, dt)
                continue
            size = 0.97 if pressed else 1.03 if hover == name else 1.0
            holder.scale = holder.scale_x + (size - holder.scale_x) * follow
            lit = button['lit'] or name == 'go'
            edge = RED if shake > 0.05 else color.white if hover == name else button['tint'] if lit else STEEL
            button['edge'].color = edge
            button['pane'].color = mixed(NAVY, BLUE, 0.55 if lit and name != 'go' else 0.3 if hover == name else
                                         0.25 + 0.15 * beat if name == 'go' else 0.0)
            if 'mark' in button:
                button['mark'].enabled = lit
        for link in self.links:
            if link['entity'].enabled:
                link['entity'].color = mixed(BLUE, CYAN, beat) if link['lit'] else STEEL
        self.fireworks(dt)

    def draw_node(self, button, name, hovered, pressed, shake, beat, dt):
        """A node of the tree: dark if it can't be had yet, ringed if it can, filled once it is owned."""
        index = int(name[5:])
        state = button['state']
        button['pop'] = max(0.0, button['pop'] - dt * 3)
        pop = button['pop']
        # nodes switch on one after another when the tree comes up
        booted = clamp((self.boot - index * 0.04) / 0.16, 0, 1)
        size = booted * (1 + 0.5 * pop + (0.1 if hovered else 0) - (0.06 if pressed else 0)
                         + (0.04 * beat if state in ('part', 'full') else 0))
        button['holder'].scale = max(size, 0.001)
        rim = (RED if shake > 0.05 else color.white if hovered and state != 'shut'
               else STEEL if state == 'shut' else CYAN)
        core = {'shut': NAVY, 'open': GLASS, 'part': mixed(GLASS, BLUE, 0.7), 'full': CYAN}[state]
        button['rim'].color = rim
        button['core'].color = mixed(core, color.white, pop)
        button['level'].color = NAVY if state == 'full' or pop > 0.3 else STEEL if state == 'shut' else ICE
        button['label'].color = STEEL if state == 'shut' else ICE
        glow = button['afford'] and state != 'full'
        button['halo'].enabled = glow or pop > 0
        if button['halo'].enabled:
            button['halo'].color = faded(color.white if pop > 0 else CYAN, max(pop, 0.25 + 0.3 * beat if glow else 0))

    def roll_chips(self, dt):
        """The counter runs to what is really in the bank, ticking as it goes."""
        real = self.game.progress.chips
        if abs(self.shown_chips - real) > 0.5:
            before = round(self.shown_chips)
            step = max(30.0, abs(self.shown_chips - real) * 6) * dt
            self.shown_chips += clamp(real - self.shown_chips, -step, step)
            if round(self.shown_chips) != before:
                self.game.sfx.play('bar_tick', volume=0.2, pitch=1.6)
            self.chips.scale = 1.75
        else:
            self.shown_chips = float(real)
            self.chips.scale = self.chips.scale_x + (1.5 - self.chips.scale_x) * min(1.0, 10 * dt)
        text = f'CHIPS {round(self.shown_chips)}'
        if text != self.chips.text:
            self.chips.text = text

    def fireworks(self, dt):
        for ring in self.rings:
            if ring['life'] <= 0:
                continue
            ring['life'] -= dt
            t = 1 - max(ring['life'], 0) / 0.4
            ring['entity'].enabled = ring['life'] > 0
            ring['entity'].scale = ring['size'] * (0.3 + 0.7 * (1 - (1 - t) ** 2))
            ring['entity'].color = faded(ring['tint'], 1 - t)
        for pulse in self.pulses:
            if pulse['life'] <= 0:
                continue
            pulse['life'] -= dt
            t = 1 - max(pulse['life'], 0) / 0.3
            (ax, ay), (bx, by) = pulse['start'], pulse['end']
            pulse['entity'].enabled = pulse['life'] > 0
            pulse['entity'].position = (ax + (bx - ax) * t, ay + (by - ay) * t, -0.08)
        flight = self.key_flight
        if flight is not None:
            flight['t'] += dt / 0.25
            t = min(flight['t'], 1.0)
            (ax, ay), (bx, by) = flight['from'], flight['to']
            self.key.position = (ax + (bx - ax) * t * t, ay + (by - ay) * t + 0.08 * sin(pi * t), -0.12)
            self.key.rotation_z = 45 + 720 * t
            if t >= 1:
                # the key lands: the lock goes, and the card with it
                self.key_flight = None
                self.key.enabled = False
                self.burst(bx, by, GOLD, 14, 1.2)
                self.burst(bx, by, CYAN, 14, 1.0)
                self.ring(bx, by, GOLD, 0.6)
                self.punch = 1.6
                self.flash_time = 0.25
