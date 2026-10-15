"""Every balance number in one place. Units are metres, seconds and degrees."""

# --- keys ---
# these are the defaults: the controls menu rebinds them at run time (data/controls.py)
KEY_FORWARD = 'w'
KEY_BACK = 's'
KEY_LEFT = 'a'
KEY_RIGHT = 'd'
KEY_JUMP = 'space'
KEY_DASH = 'left shift'
KEYS_SLIDE = ('left control', 'c')
KEY_RESPAWN = 'backspace'
KEY_RELOAD = 'r'
KEY_FIRE = 'left mouse'
KEY_SCOPE = 'right mouse'      # only the Longshot has a scope
KEY_KATANA = 'f'            # slash, and parry anything green
KEYS_WEAPON = ('1', '2', '3', '4', '5')
KEY_NEXT_WEAPON = 'scroll down'
KEY_PREVIOUS_WEAPON = 'scroll up'
KEY_SPAWN_MANY = 'p'        # debug: fill the arena to ENEMY_CAP

# --- player body ---
PLAYER_HEIGHT = 1.8
PLAYER_RADIUS = 0.4
EYE_HEIGHT = 1.6
SLIDE_EYE_HEIGHT = 0.8
STEP_HEIGHT = 0.45          # ledges lower than this are walked up
WALKABLE_NORMAL_Y = 0.7     # surfaces flatter than this count as ground
MOUSE_SENSITIVITY = 40
MAX_DT = 1 / 30             # physics never steps further than this
PLAYER_HP = 100
RALLY_HOLD = 3.0            # health just lost stays winnable this long...
RALLY_DRAIN = 5.0           # ...then drains away at this much a second
RALLY_SHARE = 0.3           # of the damage dealt in Overdrive that wins it back
RALLY_KILL = 8              # and a kill in Overdrive wins back this much more
HEART_ESCAPE = 1.4          # it shows itself on the screen this long before it is out in the arena
HEART_TIME = 20.0           # the runaway heart: how long there is to catch it...
HEART_HEAL = 30             # ...what it pours back in when caught...
HEART_GLUGS = 5             # ...in this many glugs...
HEART_PUNCH = 10            # ...and what it punches out if it gets away
HEART_SPEED = 12.0          # a little faster than a run
HEART_CATCH = 1.6           # touching distance
HEART_JUKE_AT = 7.0         # closer than this and it leaps aside...
HEART_JUKE_EVERY = 1.2
HEART_JUKE_SPEED = 16.0
HEART_AFTER = 0.4           # it gets out once this share of a round's enemies are down...
HEART_LATEST = 15.0         # ...or this many seconds into the fight, whichever comes first
BEACON_AFTER = 3            # the miniboss beacon rises when this round is cleared...
BEACON_TIME = 12.0          # ...and stays this long, unless it is shot
BOSS_SIZE = 2.6             # a miniboss is a giant of its kind
BOSS_HEAL = ((15.0, 100), (45.0, 30))   # killed inside 15 s it gives 100 health back, sliding to 30 at 45 s
BOSS_CHIPS = 15
BOSS_INTRO = 1.2            # from the beacon bursting to the giant stepping out
BOSS_SHOT_SIZE = 1.8        # what a miniboss throws is this much bigger
PLAYER_HURT_INVULNERABLE = 0.5

# --- running ---
GRAVITY = 32.0
RUN_SPEED = 11.0
GROUND_ACCEL = 9.0
GROUND_FRICTION = 7.0
STOP_SPEED = 3.0
GROUND_MOMENTUM_DECAY = 1.3  # share of speed above RUN_SPEED lost per second while running forward
GROUND_COAST_DECAY = 5.5    # the same, while not pushing forward: letting go no longer glides
GROUND_STEER = 6.0
AIR_ACCEL = 2.5
AIR_STEER = 4.0             # how fast velocity turns toward the held direction
AIR_DRAG = 0.075            # share of speed above RUN_SPEED lost per second in the air

# --- jumping ---
JUMP_SPEED = 11.5
AIR_JUMPS = 1
DOUBLE_JUMP_SPEED = 10.5
JUMP_BUFFER = 0.12
COYOTE_TIME = 0.1

# --- wall-kick ---
WALL_DETECT_DISTANCE = 0.4  # beyond the body radius
WALL_GRACE = 0.15
WALLKICK_PUSH = 9.0
WALLKICK_UP = 11.0

# --- slide ---
SLIDE_START_SPEED = 6.0
SLIDE_END_SPEED = 4.0
SLIDE_FRICTION = 0.175
SLIDE_ACCEL = 1.5
SLIDE_STEER = 2.0
SLIDE_BOOST = 5.0
SLIDE_BOOST_CAP = 24.0      # no boost when already faster than this
SLIDE_BOOST_COOLDOWN = 1.0
SLIDE_LAND_CONVERT = 0.35   # share of fall speed turned into slide speed
SLIDE_LAND_BONUS_MAX = 6.0
SLIDE_SLOPE_GAIN = 1.5

# --- dash ---
DASH_CHARGES = 2
DASH_RECHARGE = 1.0
DASH_SPEED = 26.0
DASH_BONUS = 6.0            # added on top of current speed if already fast
DASH_MAX_SPEED = 48.0
DASH_TIME = 0.14

# --- boost gates ---
GATE_BOOST = 6.0
GATE_MAX_SPEED = 46.0
GATE_COOLDOWN = 0.8

# --- rush ---
RUSH_MIN_SPEED = 6.0        # speed that gives 0 Rush
RUSH_MAX_SPEED = 36.0       # speed that gives 100 Rush
RUSH_OVERSHOOT = 130.0
RUSH_RISE = 0.35
RUSH_FALL = 1.4
RUSH_DAMAGE_MIN = 0.5
RUSH_DAMAGE_MAX = 2.0
OVERDRIVE_EXIT = 75.0       # Overdrive starts at 100 and ends below this
OVERDRIVE_KILL_BLAST_RADIUS = 4.0
OVERDRIVE_KILL_BLAST_DAMAGE = 40

# --- camera ---
FOV_BASE = 95.0
FOV_SPEED_BONUS = 32.0
FOV_FULL_SPEED = 44.0       # speed at which the whole bonus applies
FOV_DASH_KICK = 8.0
FOV_OVERDRIVE = 6.0          # wider again while in Overdrive
OVERDRIVE_SATURATION = 1.35  # the picture's colour in Overdrive (1 is as drawn)
OVERDRIVE_ABERRATION = 0.004 # red and blue pulled apart at the screen's edge
SPEED_SMEAR = 0.45           # the radial smear at full speed
STRAFE_ROLL = 2.0
SLIDE_ROLL = 4.0
LAND_DIP_PER_SPEED = 0.012
LAND_DIP_MAX = 0.3

# --- speed feedback ---
SPEED_LINES_START = 14.0    # streaks begin to show above this speed
SPEED_LINES_FULL = 36.0
WIND_START = 8.0
WIND_FULL = 44.0
BAR_FOLLOW = 14.0           # how fast the speed bar's fill chases the Rush meter

# --- weapons ---
POPPER_INTERVAL = 0.18
POPPER_DAMAGE = 22
POPPER_RANGE = 200
SCATTER_INTERVAL = 0.16     # between the first barrel and the second; then it is reloaded
SCATTER_PELLETS = 9
SCATTER_DAMAGE = 9
SCATTER_SPREAD = 5.5
SCATTER_RANGE = 60
SCATTER_RECOIL = 30.8       # each barrel launches the player away from the aim direction
SCATTER_MAX_SPEED = 48.0    # recoil can't push horizontal speed past this
ROCKET_INTERVAL = 0.95
ROCKET_SPEED = 60.0         # straight line: no gravity, no bounce
ROCKET_LIFE = 4.0           # bursts by itself after this long
ROCKET_RADIUS = 5.5
ROCKET_DAMAGE = 80
ROCKET_RECOIL = 33.6        # the hardest kick of any weapon
ROCKET_MAX_SPEED = 56.0     # recoil can't push horizontal speed past this
ROCKET_SELF_DAMAGE = 35     # to you at the centre of your own blast, less toward its edge
ROCKET_PLAYER_KNOCK = 12.0     # how hard each launcher's blast throws you
TIGER_PLAYER_KNOCK = 14.0
POISON_PLAYER_KNOCK = 11.0
ROCKET_CLIMB = 2.5          # degrees the view jumps on firing
BUZZER_INTERVAL = 0.06
BUZZER_DAMAGE = 9
BUZZER_SPREAD = 1.5
BUZZER_RANGE = 120
LONGSHOT_INTERVAL = 1.0
LONGSHOT_DAMAGE = 150
LONGSHOT_RANGE = 400
LONGSHOT_RECOIL = 4.0           # shoves the player back
LONGSHOT_CLIMB = 4.5            # degrees the view jumps up, then settles back
LONGSHOT_FOV_KICK = 13.0
LONGSHOT_PUSH = 16.0            # how hard a hit enemy is thrown
LONGSHOT_HITSTOP = 0.05
LONGSHOT_HIP_SPREAD = 2.5       # unscoped; shrinks to nothing as the scope comes up
LONGSHOT_SCOPE_TIME = 0.14
LONGSHOT_UNSCOPE_TIME = 0.08
LONGSHOT_SCOPE_FOV = 38.0
LONGSHOT_SCOPE_SENSITIVITY = 0.45   # share of normal mouse speed while fully scoped
LONGSHOT_RECHAMBER = 0.45       # after a shot the scope stays down this long
LONGSHOT_QUICK_START = 0.7      # a quickscope may fire once the scope is this far up
LONGSHOT_QUICK_WINDOW = 0.3     # ...and until this long after it is fully up
LONGSHOT_QUICK_BONUS = 1.5      # damage multiplier for a quickscope
LONGSHOT_QUICK_KILL_REFUND = 0.5    # share of the cooldown left after a quickscope kill

# --- ammunition ---
# for each weapon: rounds in the gun, rounds carried besides (None: it never runs out), and
# seconds to reload (0: no longer than the wait between its shots). Branches have their own
# in data/trees.py. Everything is filled up when a level starts.
AMMO = {'POPPER': (12, None, 0.9), 'SCATTER': (2, 40, 1.0), 'BOOMER': (1, 14, 0), 'BUZZER': (40, 320, 1.3),
        'LONGSHOT': (5, 25, 1.6)}
AMMO_CRATES = 2             # dropped by a golden astronaut
AMMO_CRATE_SHARE = 0.5      # of what one weapon can carry, in each crate
SPARE_AMMO_CHIPS = 2        # for a crate when nothing needs ammunition

# --- katana and parry ---
KATANA_DAMAGE = 45
KATANA_REACH = 3.2          # to the surface of an enemy
KATANA_CONE = 110.0         # full width of the slash
KATANA_SLASH_TIME = 0.28
KATANA_COOLDOWN = 0.45
KATANA_KNOCK = 9.0
KATANA_PARRY_WINDOW = 0.22  # from the start of the slash
KATANA_PARRY_DAMAGE = 2.0   # damage multiplier against the green enemy that was parried
KATANA_STUN = 1.0
KATANA_PROJECTILE_REACH = 4.0
KATANA_REFLECT_SPEED = 1.6  # a parried projectile flies back this many times faster
KATANA_REFLECT_DAMAGE = 120
GREEN_HUE = 130             # enemies and projectiles of this colour can be parried
GREEN_DAMAGE_MULTIPLIER = 2.5   # ...and hit this much harder when they are not
DRIVE_MAX = 3               # charges earned by parrying

# --- enemies ---
ENEMY_CAP = 40
SPAWN_MIN_DISTANCE = 22.0
THROWER_SHARE = 0.4         # of the astronauts alive; the rest are brawlers
GREEN_SHARE = 0.4           # of either kind: green suits can be parried
ASTRO_HP = 60               # of an astronaut of ordinary size
ASTRO_SIZE = (0.75, 1.45)   # each one is some size between these; hit radius, health and reach follow
GOLD_SIZE = (1.25, 1.45)
ASTRO_JUMP = 8.0            # every hop leaves the deck this fast: about 1.2 m, far less than the player
HOP_EVERY = (2.5, 6.0)      # seconds between one astronaut's hops
ASTRO_HIT_RADIUS = 0.95     # sphere round the middle of the body, for bullets, blasts and blades
ASTRO_GRAVITY = 26.0
ASTRO_ACCEL = 9.0           # how fast an astronaut's velocity turns to where it wants to go
BRAWLER_SPEED = 9.5         # a little under the player's run speed
BRAWLER_REACH = 1.9         # stops and winds up inside this distance
BRAWLER_WINDUP = 0.28
BRAWLER_PUNCH_REACH = 2.6   # the punch lands if the player is still this close
BRAWLER_DAMAGE = 12
BRAWLER_KNOCK = 12.0
BRAWLER_COOLDOWN = 0.9
LEAP_RANGE = (5.0, 12.0)    # a brawler this far away may leap at the player...
LEAP_SPEED = 15.0           # ...this fast along the deck, and punches as it comes down
THROWER_SPEED = 6.0
THROWER_NEAR = 14.0         # backs away inside this, closes in beyond THROWER_FAR, strafes between
THROWER_FAR = 26.0
THROWER_RANGE = 48.0
THROWER_INTERVAL = 2.4
THROWER_WINDUP = 0.45
MARKER_SPEED = 24.0         # along the ground; the arc is worked out from it
MARKER_GRAVITY = 18.0
MARKER_LEAD = 0.5           # share of the player's movement a throw allows for
MARKER_DAMAGE = 12
MARKER_KNOCK = 9.0
MARKER_HIT_RADIUS = 0.7     # how close to the player's body counts as a hit
MARKER_LIFE = 5.0

# --- snipers: from level 2. They stand on a perch and aim; see game/foes/snipers.py ---
SNIPER_AIM = 8.0            # seconds the laser is on the player before the shot
SNIPER_WARN = 3.0           # for this long at the end the laser is turning red
SNIPER_REST = 3.0           # after a shot, before the laser comes back
SNIPER_DAMAGE = 50
ELITE_DAMAGE = PLAYER_HP    # the advanced sniper's shot kills
SNIPER_KNOCK = 8.0
SNIPER_DODGE = 0.3          # a dash begun this long before the shot carries the player clear of it
SNIPER_HP = 0.7             # times an astronaut's
ELITE_HP = 1.2

# --- crocodiles: level 2 (game/foes/crocodiles.py) ---
CROC_SPEED = 8.5
CROC_REACH = 2.0            # stops and opens its jaws inside this distance
CROC_BITE_REACH = 2.7       # the bite lands if the player is still this close
CROC_WINDUP = 0.3
CROC_BITE = 12
CROC_KNOCK = 11.0
CROC_COOLDOWN = 1.0
CROC_DASH_RANGE = (6.0, 14.0)   # a dark green one this far away may dash...
CROC_DASH_EVERY = (2.5, 5.0)    # ...this often,
CROC_CROUCH = 0.45              # crouching this long first, which is the warning,
CROC_DASH_SPEED = 30.0          # then going this fast in a straight line
CROC_DASH_TIME = 0.5
CROC_DASH_LEAD = 0.7            # share of the player's movement the dash allows for
CROC_DASH_HIT = 1.7             # it hits a player it passes this close to
CROC_DASH_DAMAGE = 14
CROC_DASH_KNOCK = 16.0
CROC_WINDED = 0.8               # and stands this long afterwards
SNAPPER_SCALE = 0.65        # the light green ones: small, so quick and frail
SNAPPER_SPEED = 13.0        # along the ground in a leap
SNAPPER_JUMP = 6.5
SNAPPER_HOP = 0.5           # seconds on the ground between leaps
SNAPPER_ZIGZAG = 0.55       # how far to the side each leap is aimed
SNAPPER_REACH = 1.9
SNAPPER_BITE = 7
SNAPPER_KNOCK = 6.0
LOBBER_RANGE = (12.0, 30.0)     # the red ones leap about, staying this far from the player
LOBBER_LEAP_EVERY = 1.5
LOBBER_JUMP = 13.0
LOBBER_THROW_EVERY = 3.0
LOBBER_WINDUP = 0.4
MINI_SPEED = 20.0           # a thrown mini crocodile, along the ground
MINI_GRAVITY = 18.0
MINI_BITE = 10              # if it lands on the player it bites...
MINI_BLAST = 15             # ...and blows up
MINI_SCALE = 0.4            # if it misses it gets up and comes after them
MINI_HP = 15
MINI_FUSE = 8.0             # and blows up by itself after this long,
MINI_TRIGGER = 1.6          # or this close to the player,
MINI_BLAST_RADIUS = 3.0
MINI_BLAST_DAMAGE = 20      # for this much, less with distance;
MINI_ENEMY_DAMAGE = 30      # other enemies caught in it take this
MINI_CAP = 6                # no more than this many on their feet at once

# --- the crystal cave: level 3 (game/foes/cave.py) ---
MONKEY_SCALE = 1.3             # big enough to hit, hanging 5 m up and swinging about
MONKEY_HP = 0.42               # health grows with size: this keeps it what it was at 0.85 (0.8)
MONKEY_RANGE = (12.0, 30.0)     # hangs from a crystal this far from the player
MONKEY_SWING_EVERY = (2.0, 3.0)
MONKEY_SWING_TIME = 0.8         # from one crystal to the next
MONKEY_THROW_EVERY = 2.2
MONKEY_WINDUP = 0.35
MONKEY_CLIMB = 1.2              # knocked down, it is on the ground this long before it jumps back up
MONKEY_SWAY_STIFFNESS = 3.2     # a vine with a monkey on it: how hard it swings back to hanging straight...
MONKEY_SWAY_DAMPING = 1.1       # ...and how soon it settles
MONKEY_CATCH_KICK = 4.5         # m/s a monkey's catch sets the new vine swinging at, the way it was going
MONKEY_PUSH_OFF = 3.0           # m/s it shoves the old vine back as it lets go
MONKEY_THROW_KICK = 1.5         # m/s a throw rocks its vine back
MONKEY_TURN = 7.0               # how quickly it comes round to face the player
VINE_STIFFNESS = 2.6            # a vine on its own swings back to hanging straight...
VINE_DAMPING = 0.5              # ...and keeps swinging a good while after it is let go
VINE_STIR = 0.06                # the air keeps every vine moving a little
VINE_MAX_LEAN = 0.75            # radians from straight down
SHARD_SPEED = 34.0
SHARD_DAMAGE = 10
SHARD_LEAD = 0.6
GOLEM_SCALE = 0.6
GOLEM_SPEED = 16.0
GOLEM_TURN = 1.5            # radians a second: it cannot follow a sidestep
GOLEM_LEAP_AT = 5.0
GOLEM_LEAP_SPEED = 18.0
GOLEM_REACH = 1.6
GOLEM_DAMAGE = 10
GOLEM_KNOCK = 10.0
GOLEM_BOUNCE = 9.0          # how fast it comes off whatever it hit
GOLEM_COOLDOWN = 1.2
GOLEM_ROLL_PER_M = 30.0     # degrees it is seen to turn over for each metre rolled...
GOLEM_ROLL_MAX = 420.0      # ...but never faster than this a second, so the eye can follow it
GOLEM_WOBBLE = 6.0          # degrees it rocks from side to side as it rolls
MINER_TUNNEL_SPEED = 10.0   # under the ground
MINER_RANGE = (8.0, 18.0)   # comes up this far from the player
MINER_EMERGE = 0.5
MINER_SURFACE = (4.0, 6.0)  # seconds above ground
MINER_SPEED = 5.5
MINER_REACH = 2.2
MINER_WINDUP = 0.35
MINER_PICK_DAMAGE = 14
MINER_COOLDOWN = 1.0
MINER_THROW_EVERY = 1.8
MINER_DIG = 0.6             # going down, when it can still be hit
MINER_HOLE_TIME = 6.0       # a hole is seen this long
# what a miner throws: damage, speed along the ground, gravity
MINER_THROWS = {'pick': (12, 22.0, 18.0), 'rock': (10, 18.0, 24.0), 'crystal': (8, 30.0, 10.0)}

# --- levels and rounds (the rounds themselves are in data/levels.py) ---
ROUND_INTRO = 2.5           # the round's name is up this long before anyone spawns
ROUND_BREATHER = 3.0        # between the last kill of a round and the next round
LEVEL_WON_PAUSE = 2.5       # before the upgrade shop opens
REPLAY_ENEMIES = 0.25       # past the last level, each further one has this many more enemies...
REPLAY_HP = 0.15            # ...with this much more health...
REPLAY_ALIVE = 2            # ...and this many more alive at once...
REPLAY_SNIPERS = 1          # ...and this many more snipers in every round after a level's first

# --- glowing and golden enemies, chips ---
GLOW_CHIPS = 3
GOLD_CHIPS = 8
GOLD_HP = 2.0               # times an ordinary astronaut's
CHIP_MAGNET = 6.0           # chips fly to the player from this far away
CHIP_COLLECT = 1.3
CHIP_PULL = 60.0            # how hard a chip in range is drawn in
CHIP_POP = 6.0              # how fast drops scatter out of a kill
SPARE_TOKEN_CHIPS = 5       # paid out for a key when every branch is already unlocked

# --- upgrade shop (the trees themselves are in data/trees.py) ---
BRANCH_COST = 40            # chips to unlock a branch, on top of one key from a golden enemy
OLD_NODE_COSTS = (10, 15, 20, 25, 30)   # what a level cost before the trees: refunded from old saves

# --- burning, poison and converted astronauts ---
STATUS_PIXEL_EVERY = 0.05   # a burning or poisoned enemy sheds a pixel this often
SQUASH_SPRING, SQUASH_DAMPING = 320.0, 15.0     # how a squashed body springs back
STATUS_TICK = 0.5           # how often burn and poison deal their damage
CLOUD_REFRESH = 0.25        # how often a poison cloud re-poisons what stands in it
POISON_LINGER = 1.0         # poison lasts this long after leaving the cloud
ALLY_SPEED = 11.0
ALLY_DAMAGE = 25            # a fighter's punch
ALLY_REACH = 2.2
ALLY_COOLDOWN = 0.6
ALLY_FOLLOW = 4.0           # how close an ally with nothing to do stays to the player
ALLY_HEAL_RADIUS = 8.0

# --- perks of the skill trees ---
COMBUST_RADIUS = 4.0        # a burning enemy that dies bursts
COMBUST_DAMAGE = 40
WILDFIRE_REACH = 4.0        # burn jumps this far, at this share of its strength
WILDFIRE_SHARE = 0.6
OVERLOAD_BONUS = 1.3        # damage to a stunned enemy
CORRODE_BONUS = 1.25        # damage to a poisoned enemy
PLAGUE_RADIUS = 4.0         # the cloud a poisoned enemy leaves when it dies
PLAGUE_TIME = 3.0
LEGION_RADIUS = 6.0         # a fighter bursts when its time is up
LEGION_DAMAGE = 90
AEGIS_SHARE = 0.6           # of the damage gets through with a healer near
BLESSING_HEAL = 25          # from a healer as it leaves
FEAST_HEAL = 3              # a kill
CHAIN_STEP = 0.15           # more damage for each quickscope hit in a row...
CHAIN_MAX = 5
CHAIN_TIME = 4.0            # ...if the next comes this soon
ADRENALINE_RUSH = 0.25      # of the Rush meter for a quickscope kill
CLUSTER_COUNT = 3           # small blasts round the big one
CLUSTER_SHARE = 0.4         # of its damage and radius
BLAST_SUIT_KNOCK = 1.5      # times as far your own blast throws you
ALWAYS_LIT_SHARE = 0.5      # of the Overdrive burst, outside Overdrive
EMBER_BURN = (20.0, 3.0)    # damage a second, seconds
GRENADE_DROP = 16.0         # how fast an impulse grenade falls
IMPULSE_KICK = 10.0         # the launch shoves you back, a little less than a rocket's
IMPULSE_LIFT = 0.8          # an impulse blast throws you up by this much for every 1 away...
IMPULSE_LIFT_MIN = 0.45     # ...and always at least this steeply, so the floor can't soak it up
STICKY_LIFE = 20.0          # a sticky grenade nobody sets off goes off by itself after this long
STICKY_BLINK = 0.5          # its light blinks this often
AFTERSHOCK_DELAY = 0.4      # an impulse grenade goes off again this much later...
AFTERSHOCK_SHARE = 0.6      # ...this hard
CONCUSS_TIME = 1.0          # stun for whatever an impulse grenade throws
FREEZE_TIME = 1.0           # a chilled enemy hit again stands frozen this long, once for each chill
SHATTER_RADIUS = 4.0        # a chilled enemy that dies bursts into ice
SHATTER_DAMAGE = 35

# --- feedback ---
HITSTOP_KILL = 0.045
HITSTOP_BLAST = 0.09
HITSTOP_QUICKSCOPE = 0.08
HITSTOP_PARRY = 0.09
SHAKE_SHOT = 0.12
SHAKE_SCATTER = 0.5
SHAKE_ROCKET = 0.65
SHAKE_BUZZER = 0.07
SHAKE_LONGSHOT = 0.85
SHAKE_SLASH = 0.15
SHAKE_PARRY = 0.5
SHAKE_KILL = 0.3
SHAKE_BLAST = 0.7
SHAKE_HURT = 0.6
MASTER_VOLUME = 0.6

# --- chain and score (the Balatro part: see game/chain.py) ---
CHAIN_WINDOW = 2.5          # a kill this soon after the last climbs the chain a tier...
CHAIN_TOP = 10              # ...up to x10
CHAIN_HURT_DROP = 2         # tiers lost when the player is hit
SCORE_KILL = 100            # a kill, before the chain and the Rush multiplier
SCORE_SPECIAL = {'glow': 3, 'gold': 8}     # times as much for a special enemy
SCORE_BOSS = 25             # times as much for a miniboss
STYLE_AIR = 50              # style bonuses, added before the multipliers
STYLE_SLIDE = 50
STYLE_MULTI = 75            # for each other kill in the same MULTI_WINDOW
MULTI_WINDOW = 0.2
CHAIN_SCALE = (0, 2, 4, 5, 7, 9, 11, 12, 14, 16, 17)   # a kill at chain n plays this many semitones up
HITSTOP_KILL_TIER = 0.004   # a longer freeze on a kill for every chain tier
SHAKE_KILL_TIER = 0.025
FLAMES_FROM = 5             # the chain badge burns from this tier
MUSIC_LAYERS = (0, 2, 4, 7)     # the chain tier at which each music layer comes in
MUSIC_VOLUME = 0.55         # music, as a share of the master volume
MUSIC_FADE = 1.5            # seconds for a layer to fade in or out
TALLY_TIME = 1.3            # a round's score counts up in this long
TALLY_CHAIN_STEP = 0.1      # the level's points are multiplied by 1 + this for each tier of its best chain
HITSTOP_KILL_MAX = 4 / 60   # however long the chain, a kill never freezes longer than four frames
CHAIN_EDGE = 0.045          # the screen-edge glow, for each chain tier...
CHAIN_EDGE_MAX = 0.4        # ...up to this
MUSIC_DUCK = 0.35           # the music under a menu
