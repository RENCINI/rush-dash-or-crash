# RUSH (working title) — design and scope

## Context

The project folder is empty. The goal is a fast-paced, low-graphics, very colourful single-player FPS whose feedback (SFX, VFX, escalating numbers) is as satisfying and addictive as Balatro's. Balatro is the reference for *feel only*: there are no cards and no deckbuilding. This document fixes the game's identity and the scope of the first playable version.

Decisions already made:

- **Tech:** true 3D first-person in Python with Ursina.
- **Opponents:** single-player against AI only.
- **Session:** short score-chasing matches.
- **Scope:** a tight vertical slice first, expanded only once it is fun.
- **Core hook:** speed is damage.
- **First mode:** Rush Hour.
- **Theme:** neon toybox.

## The game in one paragraph

You are a tiny fighter in a neon toybox arena full of hostile geometric shapes. The faster you move, the harder you hit. Slides, dashes, wall-kicks and shotgun-jumps fill a **Rush meter**; kills in quick succession raise a **Chain multiplier**. As both climb, the game gets louder, brighter and faster, and when the match ends the score tallies up on screen number by number.

## Core mechanics

### Rush (speed is damage)
- Rush is a 0–100 meter driven by your current speed, smoothed over about half a second.
- Damage multiplier runs from x0.5 when standing still to x2.0 at full Rush.
- At 100 Rush you are in **Overdrive**: bullets pierce and kills cause a small explosion.
- Rush is shown as a bar around the crosshair, so you never look away from the action.

### Movement
- Sprint by default, with no walk key.
- **Slide:** crouch while moving. It keeps momentum and gains speed downhill.
- **Double jump** and **wall-kick** (jump off any wall, once per wall touch).
- **Dash:** short burst in the move direction, 2 charges, 1 s recharge each.
- **Jump pads** and **weapon recoil** (the Scatter launches you backwards) for big speed spikes.

### Chain
- Each kill within 2.5 s of the previous one raises the Chain by one tier, up to x10.
- Score per kill = base value × Chain × Rush multiplier, plus style bonuses: airborne, slide kill, long range, multi-kill.
- Taking damage drops the Chain by two tiers; letting the timer lapse resets it.

### Health
- 100 HP with no regeneration. Enemies drop small health orbs, and more of them the higher your Chain, so playing aggressively is how you heal.

## Feedback ("juice") — the Balatro part

This is the main feature, not polish. Every item below is in the slice.

| Event | Visual | Sound |
|---|---|---|
| Shot fired | Muzzle flash, weapon kick, slight FOV punch | Punchy shot with small random pitch |
| Hit | Hit marker, enemy flashes white and squashes, damage number pops | Tick, pitched by damage |
| Kill | 2–4 frame hitstop, confetti burst in the enemy's colour, score number flies to the HUD | Pop whose pitch climbs one semitone per Chain tier |
| Chain tier up | Multiplier slams and shakes on the HUD, screen-edge glow steps up | Rising chime, and one more music layer fades in |
| Overdrive | Colour saturation up, chromatic aberration, speed lines, wider FOV | Filter sweep, bass layer |
| Chain lost | Colours desaturate briefly, multiplier shatters | Descending "deflate" sound |
| Match end | Tally screen: each score line counts up in turn, then the multiplier is applied with flames and shake | Accelerating ticks into a final hit |

- **Sound** is generated procedurally with numpy (sfxr-style) and cached as WAV files, so there are no asset dependencies.
- **Music** is 4 stacked loops at one tempo, unlocked by Chain tier.

## Content

Items marked **slice** are in the first version. The rest is the backlog, in rough priority order.

### Gamemodes
1. **Rush Hour (slice):** 3-minute score attack against escalating waves.
2. **Gold Rush:** enemies drop coins that decay in your pocket; you bank them at a zone that moves around the map.
3. **Floor Is Fading:** tiles you stand on too long fall away and the arena shrinks.
4. **Piñata:** one giant loot-filled boss that you chip apart against the clock.
5. **Countdown:** you start with 30 seconds, and kills are the only way to add time.

### Characters
Each has one passive, one active skill and one ultimate charged by Chain.

| Character | Passive | Skill | Ultimate |
|---|---|---|---|
| **Zip** (slice) | Slide kills refund a dash charge | Blink: instant short teleport that keeps momentum | Afterimage: 5 s of slow motion for everything but you |
| **Brick** (slice) | Fall damage dealt to enemies you land on, scaling with height | Slam: dive downward, shockwave on landing | Wrecking Ball: 6 s of rolling invulnerable through enemies |
| Volt | Every fifth hit arcs to a nearby enemy | Tether: link two enemies so damage is shared | Storm: lightning strikes every enemy on screen |
| Hook | Faster air control | Grapple: swing from any surface | Yank: pull all nearby enemies to one point |
| Echo | Kills leave a decoy for 2 s | Rewind: return to your position from 3 s ago | Replay: a ghost repeats your last 8 s of shooting |

### Weapons
- **Popper (slice):** fast, accurate hitscan pistol. The reliable Chain keeper.
- **Scatter (slice):** shotgun whose recoil launches you. The movement tool.
- **Lobber (slice):** bouncing grenade launcher for groups.
- Later: **Rail** (charged piercing line) and **Yo-yo** (disc that returns and hits twice).

### Enemies
- **Cube (slice):** chases and bumps you. Fodder for chains.
- **Pyramid (slice):** keeps distance and fires slow, dodgeable projectiles.
- **Sphere (slice):** rolls at you and explodes; explosions set off other Spheres.
- Later: **Prism** (shielded from the front), **Splitter** (breaks into smaller copies), **Crown** (boss).

### Maps
- **The Blender (slice):** round two-level arena with a slow spinning bar in the centre, four jump pads and a ring of walls for wall-kicks.
- Later: **Stack** (vertical tower), **Pinball** (bumpers that launch you and enemies), **Halfpipe** (a bowl built for sliding), **Conveyor** (moving floors).

## Vertical slice — definition of done

- 1 map, 1 mode, 2 characters, 3 weapons, 3 enemy types.
- All movement, Rush, Chain and every row of the feedback table.
- Title screen, character select, HUD, tally screen, local high-score table saved to JSON.
- Holds 60 fps with 40 enemies alive.

Out of the slice: multiplayer, unlocks and progression, settings beyond volume and mouse sensitivity, controller support.

## Technical approach

- Python 3.11+, `ursina`, `numpy`. Entry point `main.py`.
- Proposed layout, all new files under the project folder:
  - `main.py` — app setup and scene switching
  - `game/player.py` — custom first-person controller (Ursina's built-in one has no slide, dash or wall-kick)
  - `game/rush.py`, `game/chain.py`, `game/score.py` — the meters and scoring
  - `game/weapons.py`, `game/enemies.py`, `game/spawner.py`, `game/characters.py`
  - `game/maps/blender.py`
  - `fx/juice.py` (hitstop, shake, FOV), `fx/particles.py` (pooled), `fx/popups.py`, `fx/postfx.py` (shader)
  - `audio/synth.py` (numpy sound generation), `audio/mixer.py` (pitch ladder, music layers)
  - `ui/hud.py`, `ui/menus.py`, `ui/tally.py`
  - `data/tuning.py` — every balance number in one place
- **Main risk:** Ursina slows down with many entities. Particles and popups are pooled and reused, enemies are capped at 40, and confetti is drawn as one combined mesh per burst rather than one entity per piece.

## Build order

1. **Movement sandbox:** grey-box Blender map, full movement set, Rush meter. Not done until moving around is fun with nothing to shoot.
2. **Shooting:** three weapons, Cube enemy, hit and kill feedback, procedural SFX.
3. **Chain and score:** multiplier, popups, pitch ladder, music layers, Overdrive post-effects.
4. **Rush Hour:** wave spawner, Pyramid and Sphere, health orbs, 3-minute timer.
5. **Characters:** Zip and Brick skills and ultimates.
6. **Shell:** menus, tally screen, high scores, tuning pass.

## Verification

- Run `python main.py` after each step and play it; each step has a playable result.
- Step 1 check: reach and hold full Rush for 10 s using only movement.
- Step 3 check: reach Chain x10 and confirm every row of the feedback table fires.
- Performance check: a debug key spawns 40 enemies; the on-screen frame counter stays at or above 60.
- End-to-end: play a full 3-minute match with each character, see the tally, and confirm the score appears in the high-score table after restarting the game.

## Changes since the plan was approved

After the first play-test (2026-10-12):

- **The Blender is bigger and more open.** Radius went from 32 m to 60 m. Ramps, pillars, jump pads and balconies sit at the rim, leaving a wide loop lane around the spinning bar.
- **Boost gates** were added: four arches across the loop lane that add speed in the direction of travel.
- **Overdrive needs more speed.** Full Rush is at 40 m/s (was 22). Run speed is still 11.
- **Speed sticks on the ground.** Speed above run speed now bleeds off slowly while running forward, instead of being lost almost at once.
- **Speed feedback** was added to step 1: screen-edge streaks, a wider field of view, a large speed readout and a wind sound that rises with speed.
- **The Lobber does not rocket-jump.** Grenades bounce twice and burst on a fuse or on touching an enemy; the Scatter's recoil is the movement tool.
- **Overdrive is easier to reach.** Full Rush is at 36 m/s (was 40), Overdrive holds until Rush drops below 75 (was 90), and the meter falls half as fast.
- **Dashes recharge in 1 s** (was 3 s).
- **Speed is lost half as fast** on the ground, in the air and in a slide. Letting go of forward at speed now coasts instead of stopping; holding back still brakes.
- **The Scatter launches you.** Recoil is 28 m/s (was 15): a shot at the floor throws you about 12 m up, and it cancels a fall first. Recoil cannot push horizontal speed past 48 m/s.

Weapons and HUD pass (2026-10-13):

- **Five weapons** on keys 1-5: Popper, Scatter, Lobber, plus the **Buzzer** (SMG: 9 damage every 0.06 s with a little spread) and the **Longshot** (sniper: 150 damage, always pierces, one shot per click). The Popper slowed to one 22-damage shot every 0.18 s so the Buzzer owns the high rate of fire.
- **Quickscope.** Right mouse scopes the Longshot in 0.14 s. A shot fired from 70% scoped until 0.3 s after fully scoped deals x1.5; a gold ring round the crosshair shows the window. A quickscope kill halves the cooldown, so they chain. Unscoped shots spread by up to 2.5 degrees.
- **Cartoon view models.** Every gun is built in `fx/toon.py` from boxes, tubes and extruded side profiles with banded shading and a dark outline, in soft colours. Slides, pump, drum and bolts move.
- **Speed bar.** A vertical meter on the left replaces the speed readout and the multiplier under the crosshair. It fills with Rush, and shows speed above and the damage multiplier below. In Overdrive it turns into a scrolling rainbow and throws lightning, with a strike sound on entry, a hum while it lasts, and a blip at each quarter on the way up.

Menu (2026-10-13):

- **Title and pause menu** in `ui/menus.py`. The game opens on it with the match frozen behind; ESC brings it back mid-match, where the button reads RESUME. It is made of `fx/toon.py` solids like the weapons: a block-letter title, a name field, colour swatches, a volume slider and a chunky play button.
- **Name** (up to 12 capitals) shows under the kill count. **Colour** paints the body of every weapon and tints the crosshair dot and name; CLASSIC keeps each weapon's own paint. **Volume** is the master level.
- Choices are kept in `settings.json` next to `main.py` (`data/settings.py`).
- `fx/toon.py` gained `plate` (a front-view outline extruded back) and `blocks` (grid cubes fused into one solid, so the outline runs round a shape that is not convex).

Katana and parry (2026-10-13):

- **Katana on `F`**, usable with any gun out. One press is one slash: 45 damage (times the Rush multiplier) to every enemy within 3.2 m in a 110 degree cone. The gun drops out of the way and cannot fire for the 0.28 s sweep; cooldown 0.45 s.
- **Green means parry.** Enemies and projectiles coloured green (hue 130) can be parried, and hit 2.5 times harder when they are not. Nothing else can be parried.
- **Parrying** happens when the slash catches something green, or a green hit from the front lands during the first 0.22 s of the slash. A parried enemy takes double katana damage, is thrown back and is stunned for 1 s. A parried projectile is sent back to whoever fired it at 1.6 times its speed for 120 damage; a tracking projectile retargets to its sender instead of the player.
- **Drive.** Each parry adds one drive charge (up to 3, lost on death), shown as pips under the speed bar. Nothing spends them yet.
- **Hook for new enemies** (details at the top of `game/katana.py`): an enemy needs `green`, `centre` and `stagger(seconds)` and passes `source=self, green=self.green` to `player.take_damage`. Projectiles are read from `game.projectiles`, an iterable of objects with `pos`, `vel`, `green`, `owner`; after a parry the katana sets `target = owner` and `friendly = True` and calls `reflect(speed, damage)` if it exists.

Spaceship and astronauts (2026-10-13):

- **The theme is now a spaceship**, not a neon toybox. The Blender keeps its layout and every collider, but is redrawn as an engine deck from `fx/toon.py` solids: hull panels with painted windows and consoles, catwalks and gangways, coolant tanks, thruster pads, airlock boost gates, a reactor with the spinning arm, and roof girders with stars and a planet beyond (the roof was plated and made solid in the playtest pass below). Colliders are invisible boxes; what is seen is baked section by section into a few meshes. `fx/toon.py` gained `placed` (turn and move a solid before baking, so fixed scenery shares one light).
- **Astronauts replace the cubes** (`game/enemies.py`): white suits, gold visors, a flag on the left shoulder. **Brawlers** (red stripes) run at you a little slower than you run, draw an arm back for 0.28 s and punch for 12. **Throwers** (blue stripes) hold 14-26 m, circling, and every 2.4 s or so lob a **giant marker pen** for 12. The throw only half allows for your movement, so running makes it miss.
- **Green suits are the parryable ones** (`GREEN_SHARE` of the astronauts): green stripes and visor, throbbing. A green brawler's punch and a green thrower's green pens follow the katana rules above; a parried pen flies back and follows its thrower. The pens in the air are `game.projectiles`.

Controls page (2026-10-13):

- **CONTROLS** on the menu opens a second page: a mouse sensitivity slider (5-100, default 40) over key slots for movement, combat and weapon switching. Click a slot, then press the new key, mouse button or wheel direction; ESC cancels. A key already in use swaps with the action that had it. The wheel is refused for actions that are held down, and `P` stays reserved for the debug fill. DEFAULTS restores everything.
- The rebindable actions are listed in `data/controls.py`. Their defaults are the `KEY_*` values in `data/tuning.py`, which `controls.apply` overwrites at run time, so game code keeps reading keys from tuning. Compare input events with `controls.pressed(key, T.KEY_...)`, which also matches mouse buttons.
- Bindings and sensitivity are saved in `settings.json` with the other menu choices, and the HUD help lines show the current keys.

Rockets and drawn bullets (2026-10-13):

- **The Lobber is now the Boomer**, a rocket launcher. Rockets fly dead straight at 60 m/s and burst on the first wall or enemy, or after 4 s. Firing throws you back at 1.5 times the Scatter's recoil (42 m/s, capped at 56 m/s horizontal). Being inside the 5.5 m blast costs you up to 35 HP (40% of that at the edge); enemies still take 80. One shot every 0.95 s.
- **The Longshot is 1.2 times bigger**, like the Boomer.
- **Every bullet is drawn**: an outlined trail with an outlined cartoon bullet at its head and an outlined star where it lands (`streak_mesh`, `slug_mesh`, `burst_mesh` in `fx/toon.py`). Hits are still instant; only the drawing travels. The rocket is an outlined model with fins and an exhaust trail.
- **Explosions** (`fx/blast.py`) throw an outlined shock ring with a white star at the centre, dark smoke and a white screen flash when close; the explosion and launch sounds were rebuilt.

Levels, chips and weapon branches (2026-10-13):

- **The game is played in levels of rounds**, not as an endless sandbox. `game/director.py` runs them from `data/levels.py`: a round sends in a set number of astronauts, a few at a time, and ends when they are all down; the next starts 3 s later. Dying restarts the level at round 1. Clearing the last round opens the upgrade shop.
- **Level 1** has 5 rounds of 10, 14, 18, 24 and 30 enemies, with 5 to 12 alive at once. Rounds 1 and 2 are brawlers only; throwers come in from round 3 (25%, then 35%, then 40%). Green suits rise from 20% to 40% and health from x1.0 to x1.3.
- **Only level 1 is written.** (No longer: see "Levels 2 and 3" below. Past the last level they now come round again, each lap with 25% more enemies, 15% more health and 2 more alive at once.)
- **Glowing astronauts** (cyan halo, suit washing cyan) drop 3 **toon chips**, the currency. **Golden astronauts** (gold suit, gold halo, sparkles, double health, never green) drop 8 chips and a **branch key**. Level 1 has 17 glowing and 4 golden: 83 chips and 4 keys. Drops fly to you inside 6 m, and whatever is left flies in when the round ends (`game/pickups.py`).
- **The upgrade shop** (`ui/shop.py`) opens after each level, and from UPGRADES on the title screen. Each weapon has two **branches** (the Scatter's came in the second playtest pass); see the playtest pass below for how they are opened and for their skill trees.
- **Everything earned is kept** in `progress.json` beside `settings.json` (`data/progress.py`): chips, keys, levels cleared, the branches opened and carried, and the nodes bought.
- **Popper branches.** *Flamethrower*: hold to spray a 12 m, 14 degree cone, 10 damage every 0.1 s to everything in it, and it burns for 8 a second for 3 s. *Taser*: a 16-damage shot that arcs to the 3 nearest enemies within 8 m of each other at 70%, and stuns them all for 0.25 s.
- **Longshot branches.** *Dragon*: 300 damage, 1.8 s between shots; in Overdrive x1.5 damage, a 4 m blast where it lands and 40% off the cooldown. *Semi-auto*: 90 damage; see the playtest pass below for its two rates of fire.
- **Boomer branches.** *Tiger*: a rocket 2.2 times the size and half as thick again, from a fatter launcher, 130 damage in 8 m (11 m since playtest pass 2), up to 30 to yourself. *Poison*: a small rocket, 60 damage in 4.5 m (was 20 in 3 m), that leaves a 10 m cloud dealing 18 a second for 6 s; it never hurts you (`game/clouds.py`).
- **Buzzer branches.** *Darkness*: 8 damage every 0.045 s; each hit has a 2% chance to steal 10 health and a 0.2% chance to turn the enemy into a **fighter** that hunts the others for 30 s. *Light*: 18 damage every 0.1 s; each hit has a 0.5% chance to turn the enemy into a **healer** that follows you for 30 s, mending 4 health a second within 8 m.
- **How it fits together.** The branches and their trees are tables in `data/trees.py`. `game/mods.py` works each weapon's numbers out from them and from what the player owns, and weapons read them with `self.stat(...)` and `self.perk(...)` instead of from `data/tuning.py`. The branch weapons are subclasses in `game/variants.py`; `Arsenal.equip` puts the one carried in its slot. Burn and poison are ticked in `game/enemies.py` twice a second; converted astronauts move from `enemies.alive` to `enemies.allies`, so bullets and round counts ignore them.

Playtest pass (2026-10-13):

- **Recoil.** The Boomer and the Tiger kick at 1.2 times the old Scatter recoil (33.6 m/s, was 1.5 and 1.4 times). The Scatter kicks at 1.1 times its old recoil (30.8 m/s) for each barrel.
- **The Scatter is a double barrel.** Two shots 0.16 s apart, then a 1 s reload with the pump. (The reload is now part of the ammunition system below.)
- **The Semi-auto has two rates of fire.** From the hip it is cocked by hand, 0.8 s a shot, with the rifle rolled over and the handle hauled back. A quickscope is ready again in 0.16 s, and the scope comes back up at once, so holding the scope and clicking as the gold ring shows fires about five times a second at x2 damage.
- **Darkness shows what it does.** Stolen health flies from the enemy to you as green drops, with a green flash round the screen, the health bar jumping and the amount beside it. A converted astronaut gets a ring, a hitstop, a line under the crosshair and a tag over its head with its role and the seconds it has left; its punches show in its own colour, and it says when it goes. Healers get the same tag.
- **Keys open branches.** A golden astronaut's token is a **key**, counted in `progress.json`. In the shop a branch costs 1 key and 40 chips. A weapon can own both of its branches; clicking an owned one carries it, and PLAIN puts the branch away. Once all eight are open a key is worth 5 chips. The old stacking modifiers are gone.
- **Each branch has a skill tree** of eight nodes (`data/trees.py`): a root, two paths of two nodes that each end in a **perk**, and a link that needs the first node of both paths. Number nodes have 3 levels at 10, 15 and 22 chips (the link 2 levels at 18 and 26); a perk costs 60. A node can be bought once every node it hangs from has a level.
- **The perks.** Flamethrower: *Wildfire* (burn jumps to enemies within 4 m), *Combust* (a burning enemy that dies bursts for 40 in 4 m). Taser: *Fork* (every arc strikes two), *Overload* (stunned enemies take 30% more). Dragon: *Always lit* (half-size burst outside Overdrive), *Ember* (hits burn for 20 a second for 3 s). Semi-auto: *Chain* (each quickscope hit in a row +15%, up to five), *Adrenaline* (a quickscope kill adds 25 Rush). Tiger: *Cluster* (three blasts at 40% round the big one), *Blast suit* (your own blasts do not hurt and throw you 1.5 times as far). Poison: *Plague* (a poisoned enemy that dies leaves a 4 m cloud for 3 s), *Corrode* (poisoned enemies take 25% more). Darkness: *Feast* (a kill gives 3 health), *Legion* (a fighter bursts for 90 in 6 m when its time is up). Light: *Blessing* (a healer gives 25 health as it leaves), *Aegis* (hits hurt 40% less beside a healer).
- **Old saves** keep their branch as opened and carried, and are paid back the chips spent on the old upgrade levels.
- **The shop is a ship's terminal**: navy glass, cyan lines, scanlines, the tree drawn as hexagons (diamonds for perks) joined by lit lines, and a panel that says what the node under the pointer does and costs. Buying a node flares it, throws sparks and a ring and sends light down the tree while the chip counter rolls; opening a branch flies a key into its card; a refusal shakes red and says why.
- **Astronauts come in sizes**, 0.75 to 1.45 (golden ones 1.25 to 1.45). Size scales the body that bullets, blasts and the katana hit, health (size to the power 1.5), reach and knockback; small ones run faster.
- **Astronauts hop, they do not jump.** Every hop leaves the deck at 8 m/s, about 1.2 m up. Every 2.5 to 6 s a brawler 5 to 12 m away **leaps** at you and punches as it lands (a green one can still be parried); otherwise it skips in its stride, and throwers hop the way they were going. The brawler's old jump to any height is gone: to reach a catwalk it runs to the gangway and up it.
- **The roof is solid.** The girders now carry plating with glass skylights, and its whole underside is one mesh collider (`roof_collider` in `game/maps/blender.py`), so the player, bullets, rockets and pens stop on it. It rises from 14.8 m at the hull to 27 m over the reactor.

Second playtest pass (2026-10-13):

- **Ammunition.** Every weapon has a magazine and, but for the Popper and the Taser, a limited supply carried besides: Popper 12 (never runs out), Scatter 2 and 40, Boomer 1 and 14, Buzzer 40 and 320, Longshot 5 and 25; the branches have their own in `data/trees.py`. **R reloads** (respawn moved to Backspace; an old `settings.json` is moved over by itself), and an empty gun reloads without being asked. Reloading tips the gun down and shows a bar under the crosshair; the count is at the bottom right, gold when low and red when out. Everything is filled up when a level starts or restarts. The numbers are `AMMO` in `data/tuning.py`; the logic is `Weapon.spend/load` and `Arsenal.reload` in `game/weapons.py`.
- **Golden astronauts drop 2 ammunition crates** as well as chips and a key. Each tops up one weapon that is short, picked at random, by half of what it can carry; a crate nobody needs is 2 chips.
- **The Scatter has branches.** *Impulse*: a grenade launcher, 4 in the drum. Grenades arc and burst on whatever they touch for 45 in 5 m, hurl enemies away and throw you (26, against the rocket's 16; now 32 and up, against 12: see 2026-10-14) without hurting you. Perks: *Aftershock* (every blast goes off again 0.4 s later at 60%), *Concuss* (what a blast throws is stunned 1 s). *Ice*: the double barrel, 8 a pellet, slowing what it hits by 45% for 2.5 s; slowed astronauts turn blue. Perks: *Deep freeze* (a slowed enemy hit again stands frozen 1 s, once for each chill), *Shatter* (a slowed enemy that dies bursts for 35 in 4 m and slows the rest).
- **The poison rocket hits harder** where it lands: 60 in 4.5 m, before the cloud.
- **Bullets are short streaks.** A shot is drawn as a bullet with a streak 45 times its width behind it, first seen 1.2 m out of the muzzle and gone when it lands, instead of a line back to the gun that seemed to bend when the player moved. The Longshot's lingering white beam is gone too. Taser arcs are still beams.
- **Astronauts come in through doors.** Eight airlocks in the hull, 45 degrees apart (`DOORS` in `game/maps/blender.py`); a spawn picks one at least 22 m from the player, and it slides open under a red lamp.
- **The Tiger is bigger**: a sleeve over the launcher, a wide mouth and a warhead to fit, and a rocket 2.2 times the plain one's size and 1.5 times as thick.
- **Weapons are more detailed.** Every gun has bolts, seams and markings (`Weapon.trim`, which bakes them without an outline), and each branch has a pattern of its own: flames on the Flamethrower's slide, a lightning bolt on the Taser, scales and teeth on the Dragon, a vented handguard and tally marks on the Semi-auto, tiger stripes, poison drips and hazard bands, thorns and a slit eye on Darkness, a sun and a halo on Light, arrows on the Impulse, a snowflake and icicles on Ice.
- **Each rifle has its own sight.** The plain Longshot keeps its round glass and cross lines at 38 degrees. The Dragon has a long gold-banded scope: a narrower red glass ringed with teeth, a chevron to aim by, 28 degrees. The Semi-auto has an open holo sight: a wide cyan frame with a red ring and dot, 50 degrees (`scope_texture` in `ui/hud.py`, `build_scope` on the weapons).
- **The player has a body** (`game/body.py`): gloved hands and sleeves on every weapon and on the katana, with cuffs in the player's colour, and legs under the camera that run, lift in the air and stretch out in a slide. There is no torso: the camera is where it would be.

Permadeath (2026-10-13; taken out again the next day, see "The save is back" below):

- **Dying wiped the save.** Chips, keys, levels cleared, branches and everything bought in their trees were cleared and the run started again at level 1.

Momentum and HUD (2026-10-13):

- **Ground momentum is lost about twice as fast.** Speed above run speed now decays at 1.3 a second while pushing forward (was 0.6) and 5.5 while coasting (was 2.5): from 40 m/s, letting go leaves 18 m/s after a quarter of a second. Air drag and the slide are unchanged.
- **The crosshair is just the dot.** The ring of Rush dots round it and the two dash bars under it are gone; Rush is read from the speed bar. The dash charges are two leaning cartoon bars built with `fx/toon.py` under the speed bar, each filling as its charge comes back and jumping when it is ready.

Levels 2 and 3 (2026-10-13):

- **Three levels, then round again.** `data/levels.py` lists them: THE SHIP, THE JUNGLE, THE CRYSTAL CAVE. Each `Level` names a map and its rounds; a round's `mix` says what share of its enemies is of each kind, and `snipers` and `elites` are sent in besides. After level 3 comes the ship again, a lap harder (more enemies, more health, and from then on one more sniper in every round after a level's first, and one more elite in its last). `py main.py --level 2` plays level 2, over and over, without touching how far the save has got.
- **Maps are plug-ins.** `game/maps/arena.py` has `Arena`, which every map subclasses: the floor, wall and ceiling colliders, raised decks and ramps as data (`add_deck`, `add_ramp`, so `ground_height` and `way_up` work on any map), pads, boost gates, `entries` enemies come in by, `perches` snipers stand on and `anchors` monkeys hang from. To add a map, subclass it and name it in `game/maps/__init__.py`. `Session.load_map` swaps maps between levels.
- **Enemies are plug-ins.** `game/foes/base.py` has `Enemy` (what the astronaut used to be) and `Shot` (what the marker pen used to be: anything thrown, and anything green among it can be parried back). Each species is a subclass in `game/foes/` that builds its own meshes in `models(green, gold)` and decides what to do in `act`; list it in its module's `KINDS` and it can be named in a round's `mix`. `game/enemies.py` is only the manager now. Fire, poison, cold, stuns and turning into an ally work on every kind.
- **Parryable enemies wear neon green**, whatever their own colour, and throb: a crocodile's bandana, belt and claws, a monkey's or golem's crystals, a miner's lamp and pick. What they throw is neon green too.
- **Every enemy has a golden version**: crocodiles wear golden helmets, monkeys a gold crown and gold crystals, golems are gold all through, miners have a gold hard hat and pick, snipers a gold helmet and rifle. They drop what golden astronauts drop.
- **The jungle** (`game/maps/jungle.py`): a clearing walled by rock and trees under a canopy with a hole to the sky, a pond with a stone idol, a dirt track under three vine arches (boost gates), three treehouse decks with log ramps, three mushrooms to bounce on, and five great trees whose crowns can be stood on. Crocodiles come out of dens in the rock.
- **Crocodiles** (`game/foes/crocodiles.py`), walking upright. *Dark green*: ordinary size; bites for 12 up close; from 6 to 14 m it crouches for 0.45 s, eyes flashing, then **dashes** at 30 m/s for half a second straight at where you will be if you keep going as you are, for 14. Changing direction, or jumping, beats it. *Light green*: 0.65 the size, so about half the health; comes on in **rapid leaps**, zigzagging, and bites for 7 where it lands. *Red*: **leaps round the clearing** 12 to 30 m from you and every 3 s or so **throws a mini crocodile**. One that hits bites and blows up (25 in all, and it throws you). One that misses **gets up** and leaps after you like a light green one, and blows up beside you (up to 20), when shot (hurting other crocodiles for 30), or after 8 s. No more than 6 are on their feet at once.
- **The crystal cave** (`game/maps/cave.py`): dark rock under a low dome, lit by crystals of every colour. A great crystal in the middle that changes hue, eight crystal pillars, four arches of leaning crystals (boost gates), four geysers (pads), two rock ledges with slopes, and fourteen crystals hanging from the roof.
- **Cave enemies** (`game/foes/cave.py`). *Crystal monkey*: **hangs** from a roof crystal by one arm, **swings** to another every 2 to 3 s, and **flings a shard** every 2.2 s or so (fast and almost straight, 10). A blast or a stun knocks it down; 1.2 s later it jumps back up. *Crystal golem*: a small cluster of crystals, 0.6 the size, that **rolls** at 16 m/s but turns slowly, and from 5 m **leaps** at you for 10 and bounces off. *Miner*: **tunnels** under the floor where nothing can touch it (a trail of earth shows where), **jumps out of a hole** 8 to 18 m from you, walks for 4 to 6 s swinging its pick (14) or **throwing a pick, a rock or a crystal** (12, 10, 8), then **digs down** again, which takes 0.6 s.
- **Snipers** (`game/foes/snipers.py`), from level 2. They stand on a perch (a tree crown, a pillar, a deck; on the ship a tank or a catwalk) and nothing knocks them off it. A **laser** is on you for **8 s**, light blue, turning **red** over the last 3, with a tick that speeds up and `SNIPER` on the HUD saying which side it is on and counting down. Then the shot: instant, **50 damage**. It misses if something solid is between you, or if you dashed in the last 0.3 s; hurting the sniper does not stop it, killing it does. Three seconds later the laser is back. The **elite** (tech blue, glowing goggles, aerial, gadgets) is the same but its shot does 100: it kills. There is one in rounds 4 and 5 of the jungle and from round 3 of the cave. Neither can be parried.
- **New sounds**: `lock`, `snipe`, `snap`, `growl`, `chime`, `dig` (`audio/synth.py`, now `v6`).

The save is back (2026-10-14):

- **Dying costs the level, not the save.** A death starts the same level again from round 1 and keeps chips, keys, levels cleared, branches and everything bought. `progress.json` is written when a round ends, when the game is paused and when the player dies.
- **DELETE SAVE** is on the menu, on the title screen and when paused. The first click asks (`SURE? CLICK AGAIN`, for 3 s), the second deletes: `Session.erase` empties the save, the weapons go back to plain, and a match under way starts over at level 1. `settings.json` is kept.
- **Once every level is cleared, the menu has a MODE button.** `MODE: ENDLESS` (as before: the levels come round again, each lap harder) or `MODE: LEVEL n`, which plays that level as it was the first time, again and again; clearing it opens the shop but does not count towards the laps. The pick is `Progress.replay` and is saved. Changing it under a running match starts the match over on what was picked. The first time the last level is cleared, the menu opens after the shop to say so.
- `Director.pick` is the level being played over again, if any; `Director.forced` is the same for `--level`, and is not saved.
- **Enemies draw faster.** `Enemy.draw` and the biped `pose` set the body and limbs straight on the Panda3D nodes (`setPos`, `setH`, `setP`) instead of through Ursina's setters: about 2 ms a frame less with the arena full. The smoke test's 40-enemy timing now fills the arena with the ship's crew whatever level ran before it.

Cave, Impulse and rocket blasts (2026-10-14):

- **Golems roll at a pace the eye can follow.** They turned over at a fixed 1/30 s a frame whatever the frame rate, about 1,800° a second at 16 m/s and twice that at 60 fps, so they blurred. Now it is 30° for each metre rolled, never more than 420° a second (`GOLEM_ROLL_PER_M`, `GOLEM_ROLL_MAX`), with a small side-to-side wobble.
- **Monkeys hang from vines.** The stone stalks with crystals under them are gone from the cave's roof. In their place, fourteen vines hang from knobs of rock: teal stems, leaves, glowing buds and a crystal knot at 7.5 m, which is the handhold. Each is a `Vine` (`game/maps/arena.py`): a damped pendulum that sways in the air, is driven by whatever holds it, and swings on by itself after it is let go. `Arena.vines` lies alongside `anchors`.
- **Monkeys move smoothly.** A hanging monkey lies along its vine and swings with it. A throw rocks it back, and arriving from a swing carries it on past and back. It comes round to face the player gradually, and its limbs ease from one pose to the next. A swing between vines kicks the old one back and follows an eased arc.
- **Launcher throws.** A blast throws you 12 from the rocket, 14 from the Tiger and 11 from Poison (16 for all three before). Tiger's Blast Suit still adds half again.
- **The Impulse throws you hard and up.** Its blast now uses `explode(..., lift=True)`. The push is tipped upward, always at least 0.45 steep, so the floor can't soak it up. It also falls off gently, to about half at the very edge. `self_knock` is 32 (was 26), and firing kicks you back 10 (was 5).
- **Sticky grenade.** With the Impulse in hand, the scope key (right click) fires a grenade that sticks to the wall, floor or enemy it hits, and blinks. Pressing it again sets it off. Only one is out at a time, it takes a round from the drum like any grenade, and the blast is the Impulse's own, perks and all. Left alone, it goes off after 20 s, and a new level clears it. Weapons can now have an `alt` shot on that key (`Weapon.alt_now`, `Weapon.alt_fire`). Rockets have a `remote` flag, and `Arsenal.stick` and `Arsenal.detonate` handle sticky ones. There are new sounds, `stick` and `beep` (synth `v7`).
- **Rocket explosions are pixels** (`fx/pixels.py`). The rocket launchers no longer use the toon ring. A blast is about 200 square pixels: a white core, a fireball, a flat ring out to the blast's edge, smoke and embers. Each pixel steps down its look's palette as it cools, never blending. The plain rocket's palette runs from white through yellows, oranges and reds to plum and slate. The **Tiger** uses saturated yellows, oranges and reds, and forms a **tiger's head** above the blast. **Poison** uses greens and purples and forms a **skull**, with a slow ring of pixels showing how far its cloud reaches. The pictures are text art in the module (`TIGER`, `SKULL`). Their pixels fly out of the fire to their places facing the camera, hold for 0.6 s, then fall apart. The Impulse (violet and teal) and the Dragon's bursts (gold through crimson) went to pixels too, without pictures; the perks' blasts keep the toon ring (they went to pixels too: see Playtest pass 2).

Health (2026-10-14):

- **There was no healing in the plain game.** Health carried over from round to round and level to level, and only the Darkness and Light branches gave any back. Four things now do. Every heal goes through `Player.heal`, which never goes past full.
- **Rally.** A hit leaves what it took on the bar as a striped pink chunk. For 3 s it stays (`RALLY_HOLD`), then drains at 5 a second. **Only damage dealt in Overdrive wins it back:** 30% of every hit (`RALLY_SHARE`) and 8 more for a kill. Outside Overdrive the chunk greys and nothing comes back. In Overdrive it glows in the Rush colours, which says "now". `Session.rally`, called from `on_hit` and `on_kill`.
- **The new health bar** (`ui/health.py`):
  - **Parts:** a chunky toon socket with a heart sitting at its left end. In it are a white ghost of what was just lost, which bites and slides away after 0.25 s, the rally chunk, and the fill. The fill eases to the real value, in a colour from mint green to hot red, with a gloss strip and a bright leading edge.
  - **Number:** big, and it bounces when it changes. `+n` and `-n` float off the bar.
  - **Hits and heals:** a hit shakes the bar and chips pixels off its end. A heal swells it and runs a green sweep along it.
  - **Low health:** under 30, the bar throbs, the screen edge beats red and a heartbeat plays, quicker the lower it gets.
- **The runaway heart** (`game/heart.py`).
  - **Getting out:** once a round, when 40% of its enemies are down or 15 s in, a one-eyed red heart on legs gets out through an entry. Its seat on the bar stands empty while it is loose.
  - **Running:** it runs away a little faster than a run, keeps off the walls and out of the pillars, leaps aside when you get within 7 m, bounces off pads and leaves a trail of pink pixels.
  - **20 s to touch it.** The time shows over it and as `CATCH THE HEART  12` at the top of the screen, with arrows when it is off to one side.
  - **Caught:** it flies home to the bar and gives 30 back (it kissed it in at first; it pours it in now: see Playtest pass 2).
  - **Missed:** it spins, winks and vanishes. Then it turns up at the bar with a boxing glove and a scowl and **punches 10 out** (POW, a crack, the bar jolts), but never the last point (`Player.knock_hp`).
  - It doesn't come in a miniboss fight, and a new level or a death sends it home.
- **Minibosses** (`game/beacon.py`, `Level.boss` in `data/levels.py`).
  - **The beacon:** when round 3 is cleared, a beacon rises where the player can see it: a stone base under a tall pulsing pink column. **Shoot it**, with any bullet or blast, and the level's miniboss comes out of it. Leave it 12 s and it sinks and round 4 comes as usual. It is offered once each time a level is played.
  - **The giants:** each is a giant of its level's kind (size 2.6, so about 4.2 times the health of an ordinary one), then multiplied (`Enemy.make_boss`).
    - Ship: *Giant thrower*, speed ×1.5, health ×1.5, power ×1.2.
    - Jungle: *Giant crocodile* (red), ×1.2, ×2, ×1.2.
    - Cave: *Giant miner*, ×1.3 everything.
  - **What the multipliers do:** speed sets how fast it moves and how quickly its own timers run (`Enemy.quick`). Power multiplies its blows and its throws (`Enemy.might`), and what it throws is bigger.
  - **Rules:** it can't be turned into an ally, it drops 15 chips, and a red bar with its name runs across the top of the screen while it lives.
  - **The heal is by speed:** killed inside 15 s it gives **100**, sliding to **30** at 45 s or more (`BOSS_HEAL`). The banner reads `MINIBOSS DOWN  12.4 s  +100 HP`, and then round 4.
- **New sounds:** `smooch`, `whack`, `heartbeat`, `giggle`, `catch`, `beacon`, `roar` (synth `v8`).
- **For the tests:** `Director.hearts` and `Director.beacons` turn the heart and the beacon off.

Playtest pass 2 (2026-10-14):

- **The heart pours, it doesn't kiss.** The lips are gone. Caught, the heart flies to the bar, tips itself up over the fill's end like a jug and **pours 30 back in, in 5 glugs** (`HEART_GLUGS`). Each glug squeezes it a little emptier, sends a stream of red pixels into the bar, sloshes the fill's end and plays `glug`. Empty, it pops back to size in a burst of mint and pink and hops into its seat.
- **The heart escapes on screen first.** When it gets out it wakes in its seat, squeezes out with a pop, flies to the middle of the screen growing big, looks round, winks and dashes off toward where it will run in the arena (off the edge of the screen if that is behind you), trailing pink. That takes 1.4 s (`HEART_ESCAPE`); the heart in the arena only appears, and its 20 s only start, when it has gone.
- **A rounder heart.** `fx/toon.py` gained `ball` (a faceted ball, or a dome) and `loft` (a solid through stacked rings). The heart is now two chubby lobes over a rounded point, with a shine, two blush spots, a white eyeball with a pupil that rides round it, and a lid that rolls down to blink. The glove is a ball fist with a thumb and a cuff. In the arena it has barrel legs with big shoes that stride with the ground it covers, and little arms in white gloves that pump.
- **Pictures in relief.** The Tiger's head and the poison skull are now several pixels deep (2 at the edge to 4 in the middle, with the eyes and nose set back), each layer back two palette steps darker, and the picture swings round up to 35 degrees while it hangs so the depth shows (`relief`, `SPIN` in `fx/pixels.py`). Pixels now hide each other properly. The pool went from 1600 to 3000.
- **A bigger Tiger.** Its blast is 11 m (was 8); each BLAST node still adds 0.5 m. Cluster's three small blasts now go off at 45% of the radius from the middle (was 60%), so they still overlap the big one.
- **Perk blasts in pixels.** Combust bursts in the Dragon's fire, Shatter in a new `frost` palette and Legion in a new violet `legion` one.
- **Minibosses have 4 times the health:** the thrower ×6, the crocodile ×8 and the miner ×5.2 on top of their giant size (about 1500, 2000 and 1300). The heal is still 100 inside 15 s down to 30 at 45 s.
- **One pixel alphabet for every word** (`ui/font.py`). Ursina's default font is gone: every `Text` is now a `Label`, which takes the same arguments.
  - **The letters:** a hand-drawn alphabet five pixels by seven (`GLYPHS`), with every digit and every symbol the game prints. Lower case is set in capitals.
  - **Block style**, for anything 1.2 or bigger: each letter's face, then the same shape stepped back down and to the right in darker shades, inside a dark outline, so it looks solid even on the flat UI. **Flat style**, for small print: the face on a dark rim with a drop shadow.
  - **Cheap to change:** a string's mesh is its glyphs' baked arrays side by side, cached, so numbers that change every frame cost little. With `letters=True` each letter is its own entity, for `drop_in`, `wave` and `jiggle`.
- **UI pixels.** `Pixels(ui=True)` is the same pixel engine flat on the screen (`hud.sparks`, shared by the menus and the shop). New palettes: `gold`, `mint`, `hurt`, `rush`, `white`.
- **What moves now:**
  - **Banners:** the letters drop in one by one with a puff under each, and burst into pixels when the banner goes.
  - **Notices:** they wobble in with a sparkle, then ripple.
  - **Overdrive:** the word waves and throws off rainbow pixels.
  - **The chase line** beats like a heart, and shakes when time is short.
  - **Empty ammo** shakes. The weapon in hand is set in blocks with a little burst.
  - **Kills and chips:** they throw red and gold pixels.
  - **Health bar:** the pixels chipped off the bar's end are real pixels now. Heals sparkle mint, and the boss bar sheds pixels when hit.
  - **Menu:** button letters ripple under the mouse and burst on a click, and the RUSH title glitters.
  - **Shop:** its sparks are pixels.
- **New sound:** `glug` in place of `smooch` (synth `v9`).

Build status: steps 1 and 2 are done, and the wave structure of step 4. `tests/smoke.py` checks movement, weapons, enemies, sound files, the menu, the rounds, the shop, every weapon branch and its perks, ammunition, enemy sizes, hops and doors, the sights, the player's body, the roof, the three levels and their maps, every new enemy, the vines, the sticky grenade, the pixel explosions and their reliefs, the perk blasts, rally, the health bar, the runaway heart's escape and refill, the minibosses and the lettering without opening a window.
