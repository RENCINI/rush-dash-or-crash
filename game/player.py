from math import cos, exp, pi, radians, sin

from ursina import Entity, Vec3, camera, clamp, held_keys, mouse, raycast, time

from data import tuning as T
from data.controls import pressed
from game.body import Legs
from game.rush import Rush

UP = Vec3(0, 1, 0)
DOWN = Vec3(0, -1, 0)
PROBE_DIRECTIONS = [Vec3(sin(i * pi / 4), 0, cos(i * pi / 4)) for i in range(8)]


def damp(current, target, rate, dt):
    return current + (target - current) * (1 - exp(-rate * dt))


def flat(v):
    return Vec3(v.x, 0, v.z)


class Player(Entity):
    """First-person controller with slide, double jump, wall-kick and dash."""

    def __init__(self, spawn_position, spawn_yaw=0):
        super().__init__(position=spawn_position, rotation_y=spawn_yaw)
        self.spawn_position = Vec3(*spawn_position)
        self.spawn_yaw = spawn_yaw

        self.pivot = Entity(parent=self, y=T.EYE_HEIGHT)
        camera.parent = self.pivot
        camera.position = (0, 0, 0)
        camera.rotation = (0, 0, 0)
        camera.fov = T.FOV_BASE

        self.rush = Rush()
        self.vel = Vec3(0, 0, 0)
        self.grounded = False
        self.ground_normal = UP
        self.ground_entity = None
        self.sliding = False
        self.air_jumps = T.AIR_JUMPS
        self.dash_charges = T.DASH_CHARGES
        self.dash_recharge = 0.0

        self.jump_buffer = 0.0
        self.coyote = 0.0
        self.dash_timer = 0.0
        self.slide_boost_cooldown = 0.0
        self.land_impact = 0.0
        self.land_timer = 0.0
        self.wall_normal = None
        self.wall_timer = 0.0
        self.last_kick_normal = None

        self.eye_height = T.EYE_HEIGHT
        self.moved = 0.0
        self.land_dip = 0.0
        self.fov_kick = 0.0
        self.base_fov = T.FOV_BASE
        self.zoom = 0.0         # 0-1, set by a scoped weapon
        self.zoom_fov = T.LONGSHOT_SCOPE_FOV    # the field of view when it is fully scoped

        self.hp = T.PLAYER_HP
        self.rally = 0.0        # health just lost that can still be won back, by hitting in Overdrive
        self.rally_hold = 0.0   # until it starts to drain away
        self.invulnerable = 0.0
        self.boost_cooldown = 0.0
        self.on_event = None    # callback(name, value) for sound and effects
        self.parry = None       # callback(source) -> True if a green hit was parried
        self.guard = None       # callback() -> the share of a hit that gets through
        self.legs = Legs(self)
        self.drive = 0          # charges earned by parrying, up to DRIVE_MAX

    def emit(self, name, value=0.0):
        if self.on_event is not None:
            self.on_event(name, value)

    # --- state other systems read ---

    @property
    def centre(self):
        return self.position + UP * (T.PLAYER_HEIGHT / 2)

    @property
    def speed(self):
        return self.vel.length()

    @property
    def flat_speed(self):
        return flat(self.vel).length()

    @property
    def dash_progress(self):
        """Charges including the partly recharged one, e.g. 1.5."""
        return self.dash_charges + self.dash_recharge / T.DASH_RECHARGE

    # --- input ---

    def input(self, key):
        if pressed(key, T.KEY_JUMP):
            self.jump_buffer = T.JUMP_BUFFER
        elif pressed(key, T.KEY_DASH):
            self.dash()
        elif pressed(key, T.KEY_RESPAWN):
            self.respawn()

    def wish_direction(self):
        yaw = radians(self.rotation_y)
        forward = Vec3(sin(yaw), 0, cos(yaw))
        right = Vec3(cos(yaw), 0, -sin(yaw))
        wish = (forward * (held_keys[T.KEY_FORWARD] - held_keys[T.KEY_BACK])
                + right * (held_keys[T.KEY_RIGHT] - held_keys[T.KEY_LEFT]))
        return wish.normalized() if wish.length() > 0.01 else Vec3(0, 0, 0)

    def respawn(self):
        self.position = self.spawn_position
        self.rotation_y = self.spawn_yaw
        self.pivot.rotation_x = 0
        self.vel = Vec3(0, 0, 0)
        self.sliding = False
        self.hp = T.PLAYER_HP
        self.rally = self.rally_hold = 0.0
        self.invulnerable = 1.0

    # --- health ---

    def heal(self, amount):
        """Give health back, never past full. Returns how much was given."""
        given = max(0.0, min(amount, T.PLAYER_HP - self.hp))
        self.hp += given
        self.rally = min(self.rally, T.PLAYER_HP - self.hp)
        return given

    def knock_hp(self, amount):
        """Take health straight off, whatever else is going on, but never the last of it: for
        what the HUD does to the bar. Returns how much was taken."""
        taken = max(0.0, min(amount, self.hp - 1))
        self.hp -= taken
        self.rally = min(self.rally, T.PLAYER_HP - self.hp)
        return taken

    def win_back(self, amount):
        """Turn up to `amount` of the rally back into health. Returns how much came back."""
        gained = min(self.rally, max(0.0, amount))
        self.rally -= gained
        self.hp = min(T.PLAYER_HP, self.hp + gained)
        return gained

    def update_rally(self, dt):
        if self.rally <= 0:
            return
        self.rally_hold -= dt
        if self.rally_hold <= 0:
            self.rally = max(0.0, self.rally - T.RALLY_DRAIN * dt)

    def knock(self, velocity):
        """Throw the player, replacing their velocity, e.g. from a hazard."""
        self.vel = Vec3(*velocity)
        self.grounded = False
        self.sliding = False
        self.coyote = 0.0

    def add_impulse(self, impulse, cap=None):
        """Push the player on top of their velocity, e.g. recoil or a blast.
        With `cap`, the push can't take horizontal speed past it."""
        before = self.flat_speed
        if impulse.y > 0 and self.vel.y < 0:
            self.vel.y = 0      # an upward push always lifts, even out of a fall
        self.vel += impulse
        if cap is not None:
            speed = self.flat_speed
            limit = max(before, cap)
            if speed > limit:
                self.vel.x *= limit / speed
                self.vel.z *= limit / speed
        if self.vel.y > 0:
            self.grounded = False
            self.sliding = False
            self.coyote = 0.0

    def boost(self, amount, cap):
        """Speed up along the current direction of travel. Returns True if it did anything."""
        v = flat(self.vel)
        speed = v.length()
        if speed < 1:
            return False
        target = min(max(speed, T.RUN_SPEED) + amount, cap)
        if target <= speed:
            return False
        v = v / speed * target
        self.vel.x = v.x
        self.vel.z = v.z
        self.fov_kick = T.FOV_DASH_KICK
        self.emit('boost')
        return True

    def take_damage(self, amount, knock=None, source=None, green=False):
        """`green` hits can be parried; the ones that land hurt far more."""
        if self.invulnerable > 0:
            return
        if green:
            if self.parry is not None and self.parry(source):
                return
            amount *= T.GREEN_DAMAGE_MULTIPLIER
        if self.guard is not None:
            amount *= self.guard()
        self.hp -= amount
        # what was just lost can still be won back for a while, up to what the bar has room for
        self.rally = min(self.rally + amount, T.PLAYER_HP - max(self.hp, 0))
        self.rally_hold = T.RALLY_HOLD
        self.invulnerable = T.PLAYER_HURT_INVULNERABLE
        if knock is not None:
            self.add_impulse(knock)
        self.emit('hurt', amount)
        if self.hp <= 0:
            self.drive = 0
            self.emit('death')
            self.respawn()

    def dash(self):
        if self.dash_charges < 1:
            return
        direction = self.wish_direction()
        if direction.length() < 0.5:
            yaw = radians(self.rotation_y)
            direction = Vec3(sin(yaw), 0, cos(yaw))
        speed = min(max(self.flat_speed + T.DASH_BONUS, T.DASH_SPEED), T.DASH_MAX_SPEED)
        self.vel = direction * speed
        self.dash_timer = T.DASH_TIME
        self.dash_charges -= 1
        self.fov_kick = T.FOV_DASH_KICK
        self.emit('dash')

    # --- frame ---

    def update(self):
        dt = min(time.dt, T.MAX_DT)
        if dt <= 0:
            return
        self.look()
        wish = self.wish_direction()
        self.tick_timers(dt)
        self.update_rally(dt)
        self.handle_jump()
        self.update_slide()
        self.update_velocity(wish, dt)
        self.move_horizontal(dt)
        self.move_vertical(dt)
        self.probe_walls()      # last, so a fall into the side of a ledge is pushed back out
        self.use_jump_pad()
        if self.y < -20:
            self.respawn()
        self.rush.update(self.speed, dt)
        self.update_camera(dt)

    def look(self):
        if not mouse.locked:
            return
        turn = T.MOUSE_SENSITIVITY * (1 - (1 - T.LONGSHOT_SCOPE_SENSITIVITY) * self.zoom)
        self.rotation_y += mouse.velocity[0] * turn
        self.pivot.rotation_x = clamp(self.pivot.rotation_x - mouse.velocity[1] * turn, -89, 89)

    def tick_timers(self, dt):
        self.jump_buffer -= dt
        self.coyote -= dt
        self.dash_timer -= dt
        self.slide_boost_cooldown -= dt
        self.land_timer -= dt
        self.wall_timer -= dt
        self.invulnerable -= dt
        self.boost_cooldown -= dt
        if self.dash_charges < T.DASH_CHARGES:
            self.dash_recharge += dt
            if self.dash_recharge >= T.DASH_RECHARGE:
                self.dash_recharge = 0.0
                self.dash_charges += 1

    def handle_jump(self):
        if self.jump_buffer <= 0:
            return
        if self.grounded or self.coyote > 0:
            self.vel.y = T.JUMP_SPEED
            self.emit('jump')
        elif self.can_wall_kick():
            n = self.wall_normal
            into = flat(self.vel).dot(n)
            if into < 0:
                self.vel -= n * into
            self.vel += n * T.WALLKICK_PUSH
            self.vel.y = T.WALLKICK_UP
            self.last_kick_normal = n
            self.emit('wall_kick')
        elif self.air_jumps > 0:
            self.vel.y = T.DOUBLE_JUMP_SPEED
            self.air_jumps -= 1
            self.emit('double_jump')
        else:
            return
        self.jump_buffer = 0.0
        self.coyote = 0.0
        self.grounded = False
        self.sliding = False

    def can_wall_kick(self):
        if self.wall_normal is None or self.wall_timer <= 0:
            return False
        # one kick per wall touch: the same wall can't be kicked twice in a row
        return self.last_kick_normal is None or self.wall_normal.dot(self.last_kick_normal) < 0.9

    def update_slide(self):
        want = any(held_keys[key] for key in T.KEYS_SLIDE)
        speed = self.flat_speed
        if self.sliding:
            self.sliding = want and self.grounded and speed > T.SLIDE_END_SPEED
            return
        if not (want and self.grounded and speed > T.SLIDE_START_SPEED):
            return
        self.sliding = True
        self.emit('slide')
        if self.slide_boost_cooldown <= 0 and speed < T.SLIDE_BOOST_CAP:
            boost = T.SLIDE_BOOST
            if self.land_timer > 0:
                boost += min(self.land_impact * T.SLIDE_LAND_CONVERT, T.SLIDE_LAND_BONUS_MAX)
            self.vel += flat(self.vel).normalized() * boost
            self.slide_boost_cooldown = T.SLIDE_BOOST_COOLDOWN

    def update_velocity(self, wish, dt):
        if self.dash_timer > 0:
            return
        if not self.grounded:
            speed = self.flat_speed
            if speed > T.RUN_SPEED:
                scale = (T.RUN_SPEED + (speed - T.RUN_SPEED) * exp(-T.AIR_DRAG * dt)) / speed
                self.vel.x *= scale
                self.vel.z *= scale
            self.steer(wish, T.AIR_STEER, dt)
            self.accelerate(wish, T.RUN_SPEED, T.AIR_ACCEL, dt)
        elif self.sliding:
            scale = max(0.0, 1 - T.SLIDE_FRICTION * dt)
            self.vel.x *= scale
            self.vel.z *= scale
            self.steer(wish, T.SLIDE_STEER, dt)
            self.accelerate(wish, T.RUN_SPEED, T.SLIDE_ACCEL, dt)
            # gravity along the slope speeds up downhill slides
            n = self.ground_normal
            downhill = DOWN - n * DOWN.dot(n)
            self.vel += flat(downhill) * T.GRAVITY * T.SLIDE_SLOPE_GAIN * dt
        else:
            speed = self.flat_speed
            along = flat(self.vel).dot(wish)
            if speed > T.RUN_SPEED and along >= 0:
                # momentum above run speed bleeds off slowly while you keep pushing forward,
                # faster while coasting; only holding against it brakes with full friction
                pushing = along > 0.3 * speed
                decay = T.GROUND_MOMENTUM_DECAY if pushing else T.GROUND_COAST_DECAY
                scale = (T.RUN_SPEED + (speed - T.RUN_SPEED) * exp(-decay * dt)) / speed
                self.vel.x *= scale
                self.vel.z *= scale
                if pushing:
                    self.steer(wish, T.GROUND_STEER, dt)
                return
            if speed > 0.01:
                drop = max(speed, T.STOP_SPEED) * T.GROUND_FRICTION * dt
                scale = max(speed - drop, 0) / speed
                self.vel.x *= scale
                self.vel.z *= scale
            self.accelerate(wish, T.RUN_SPEED, T.GROUND_ACCEL, dt)

    def steer(self, wish, rate, dt):
        """Turn the velocity toward `wish` without changing its size."""
        v = flat(self.vel)
        speed = v.length()
        if speed < 0.01 or wish.length() < 0.5 or v.dot(wish) <= 0:
            return
        turned = (v / speed + wish * rate * dt).normalized() * speed
        self.vel.x = turned.x
        self.vel.z = turned.z

    def accelerate(self, wish, wish_speed, accel, dt):
        """Only adds speed along `wish` up to `wish_speed`, so momentum above it is kept."""
        missing = wish_speed - flat(self.vel).dot(wish)
        if missing > 0:
            self.vel += wish * min(accel * wish_speed * dt, missing)

    # --- collision ---

    def move_horizontal(self, dt):
        move = flat(self.vel) * dt
        self.moved = move.length()
        for _ in range(3):
            distance = move.length()
            if distance < 1e-5:
                return
            direction = move / distance
            blocker = None
            for height in (T.STEP_HEIGHT, T.PLAYER_HEIGHT / 2, T.PLAYER_HEIGHT - 0.1):
                hit = raycast(self.position + UP * height, direction, distance=distance + T.PLAYER_RADIUS)
                if hit.hit and hit.world_normal.y < T.WALKABLE_NORMAL_Y:
                    if blocker is None or hit.distance < blocker.distance:
                        blocker = hit
            if blocker is None:
                self.position += move
                return
            n = flat(blocker.world_normal)
            n = n.normalized() if n.length() > 0.01 else -direction
            allowed = max(blocker.distance - T.PLAYER_RADIUS - 0.01, 0)
            self.position += direction * allowed
            rest = move - direction * allowed
            move = rest - n * rest.dot(n)
            self.block_velocity(n)

    def block_velocity(self, n):
        into = flat(self.vel).dot(n)
        if into < 0:
            self.vel -= n * into

    def probe_walls(self):
        """Push out of anything closer than the body radius and remember nearby walls. The waist
        looks all round; the knees and the head, where a ledge's edge or a roof's lip can be, look
        where the body is going. (Only the waist counts as a wall to kick off.)"""
        reach = T.PLAYER_RADIUS + T.WALL_DETECT_DISTANCE
        waist = T.PLAYER_HEIGHT / 2
        heading = flat(self.vel)
        rays = [(waist, d, reach) for d in PROBE_DIRECTIONS]
        if heading.length() > 0.1:
            heading = heading.normalized()
            ahead = [heading]
            rays += [(h, d, T.PLAYER_RADIUS) for h in (T.STEP_HEIGHT, T.PLAYER_HEIGHT - 0.1) for d in ahead]
        nearest = None
        for height, direction, distance in rays:
            hit = raycast(self.position + UP * height, direction, distance=distance)
            if not hit.hit or hit.world_normal.y >= T.WALKABLE_NORMAL_Y:
                continue
            n = flat(hit.world_normal)
            if n.length() < 0.01:
                continue
            n = n.normalized()
            if hit.distance < T.PLAYER_RADIUS:
                self.position += n * (T.PLAYER_RADIUS - hit.distance) * max(-direction.dot(n), 0)
                self.block_velocity(n)
            if height == waist and (nearest is None or hit.distance < nearest[0]):
                nearest = (hit.distance, n)
        if nearest is not None:
            self.wall_normal = nearest[1]
            self.wall_timer = T.WALL_GRACE

    def move_vertical(self, dt):
        if self.dash_timer > 0:
            self.vel.y = 0
        else:
            self.vel.y -= T.GRAVITY * dt
        step = self.vel.y * dt
        was_grounded = self.grounded

        if self.vel.y > 0:
            if self.blocked_above(step + 0.05):
                self.vel.y = 0
            else:
                self.y += step
            self.grounded = False
            return

        # the ray starts above the feet so ledges and up-slopes are stepped onto, and
        # reaches a little below them while grounded so the player sticks to down-slopes
        lift = 1.2
        max_rise = max(T.STEP_HEIGHT, self.moved * 1.05 + 0.05)
        snap = 0.35 if was_grounded else 0.0
        hit = raycast(self.position + UP * lift, DOWN, distance=lift - step + snap)
        if (hit.hit and hit.world_normal.y >= T.WALKABLE_NORMAL_Y
                and hit.world_point.y - self.y <= max_rise):
            if not was_grounded:
                self.land(-self.vel.y)
            self.y = hit.world_point.y
            self.vel.y = 0
            self.grounded = True
            self.ground_normal = Vec3(*hit.world_normal)
            self.ground_entity = hit.entity
        else:
            self.y += step
            self.grounded = False
            if was_grounded:
                self.coyote = T.COYOTE_TIME

    def blocked_above(self, distance):
        """Whether anything is within `distance` over the head: over its middle or over its rim, so
        the edge of a ledge or a roof beside the player stops a jump the same as one overhead."""
        rim = T.PLAYER_RADIUS * 0.9
        for dx, dz in ((0, 0), (rim, 0), (-rim, 0), (0, rim), (0, -rim)):
            if raycast(self.position + Vec3(dx, T.PLAYER_HEIGHT, dz), UP, distance=distance).hit:
                return True
        return False

    def land(self, impact):
        self.air_jumps = T.AIR_JUMPS
        self.last_kick_normal = None
        self.land_impact = impact
        self.land_timer = 0.12
        self.land_dip = min(impact * T.LAND_DIP_PER_SPEED, T.LAND_DIP_MAX)
        self.emit('land', impact)

    def use_jump_pad(self):
        launch = getattr(self.ground_entity, 'pad_velocity', None) if self.grounded else None
        if launch is None:
            return
        self.vel += flat(launch)
        self.vel.y = launch.y
        self.grounded = False
        self.sliding = False
        self.air_jumps = T.AIR_JUMPS
        self.fov_kick = T.FOV_DASH_KICK
        self.emit('pad')

    # --- camera ---

    def update_camera(self, dt):
        self.eye_height = damp(self.eye_height, T.SLIDE_EYE_HEIGHT if self.sliding else T.EYE_HEIGHT, 14, dt)
        self.land_dip = damp(self.land_dip, 0, 10, dt)
        self.pivot.y = self.eye_height - self.land_dip

        self.fov_kick = damp(self.fov_kick, 0, 6, dt)
        fast = clamp((self.speed - T.RUN_SPEED) / (T.FOV_FULL_SPEED - T.RUN_SPEED), 0, 1)
        target_fov = T.FOV_BASE + T.FOV_SPEED_BONUS * fast + self.fov_kick + T.FOV_OVERDRIVE * self.rush.overdrive
        self.base_fov = damp(self.base_fov, target_fov, 10, dt)
        zoom = self.zoom * self.zoom * (3 - 2 * self.zoom)
        camera.fov = self.base_fov + (self.zoom_fov - self.base_fov) * zoom

        strafe = held_keys[T.KEY_RIGHT] - held_keys[T.KEY_LEFT]
        roll = -strafe * (T.SLIDE_ROLL if self.sliding else T.STRAFE_ROLL)
        camera.rotation_z = damp(camera.rotation_z, roll, 10, dt)
