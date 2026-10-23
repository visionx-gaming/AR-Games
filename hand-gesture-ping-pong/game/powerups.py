"""Power-ups (collect, activate, expire) and the moving obstacle blocks."""

import random
import math
from game.config import (
    WINDOW_WIDTH, WINDOW_HEIGHT, BALL_RADIUS, PADDLE_HEIGHT, DIFFICULTY_SPEEDS,
    RAMP_BALL_SPEED, POWERUP_TYPES, POWERUP_RADIUS, POWERUP_SPAWN_MIN, POWERUP_SPAWN_MAX,
    POWERUP_LIFETIME, BIG_PADDLE_MULTIPLIER, OBSTACLE_COUNT, OBSTACLE_MIN_SIZE,
    OBSTACLE_MAX_SIZE, OBSTACLE_SPEED_MIN, OBSTACLE_SPEED_MAX, get_powerup_color,
)
from game.state import Ball, PowerUpItem, Obstacle
from game import difficulty, effects


def overlaps_obstacle(state, x, y, r):
    if not state.settings["obstacles_enabled"]:
        return False
    for o in state.obstacles:
        if (x + r > o.x - 10 and x - r < o.x + o.w + 10
                and y + r > o.y - 40 and y - r < o.y + o.h + 40):
            return True
    return False


def update_powerups(state, sound_mgr):
    """Spawn new power-ups periodically and expire active effects."""
    t = state.game_time

    # Spawn
    if (state.settings.get("powerups_enabled", True)
            and t >= state.next_powerup_time and len(state.powerups) < 2):
        ptype = random.choice(list(POWERUP_TYPES.keys()))
        margin = 200
        for _ in range(12):
            x = random.randint(margin, WINDOW_WIDTH - margin)
            y = random.randint(80, WINDOW_HEIGHT - 80)
            if not overlaps_obstacle(state, x, y, POWERUP_RADIUS):
                break
        pu = PowerUpItem(x, y, ptype)
        pu.spawn_time = t
        state.powerups.append(pu)
        state.next_powerup_time = t + random.uniform(
            POWERUP_SPAWN_MIN, POWERUP_SPAWN_MAX
        )

    # Expire active effects
    expired = [k for k, exp in state.active_effects.items() if t >= exp]
    for k in expired:
        if k == "big_paddle_left":
            state.left_paddle_height = PADDLE_HEIGHT
        elif k == "big_paddle_right":
            state.right_paddle_height = PADDLE_HEIGHT
        del state.active_effects[k]

    # Expire uncollected court power-ups
    state.powerups = [pu for pu in state.powerups
                      if t - pu.spawn_time < POWERUP_LIFETIME]


def activate_powerup(state, ball, pu, sound_mgr, theme):
    """Activate a collected power-up. ball is the one that touched it."""
    t = state.game_time
    info = POWERUP_TYPES[pu.type]
    duration = info["duration"]

    sound_mgr.play_powerup()
    pu_color = get_powerup_color(theme, pu.type)
    effects.add_floating_text(state, pu.x, pu.y - 30, info["label"], pu_color)

    if pu.type == "big_paddle":
        # Award big paddle to the side that last touched the ball
        side_key = "big_paddle_left" if ball.vx > 0 else "big_paddle_right"
        state.active_effects[side_key] = t + duration
        if ball.vx > 0:
            state.left_paddle_height = int(PADDLE_HEIGHT * BIG_PADDLE_MULTIPLIER)
        else:
            state.right_paddle_height = int(PADDLE_HEIGHT * BIG_PADDLE_MULTIPLIER)
    else:
        state.active_effects[pu.type] = t + duration
        if pu.type == "multi_ball":
            spawn_extra_ball(state)


def spawn_extra_ball(state):
    """Spawn an extra ball for the multi-ball power-up (at most one at a time).
    It is a full ball: missing it costs a point exactly like missing the other one."""
    if any(not b.is_main and b.alive for b in state.balls):
        return
    base_speed = DIFFICULTY_SPEEDS[state.settings["difficulty"]] * difficulty.ramp(state, RAMP_BALL_SPEED)
    main = next((b for b in state.balls if b.is_main), None)
    # Launch away from the main ball so the two never overlap
    direction = -1 if (main and main.vx > 0) else 1
    y = WINDOW_HEIGHT / 2
    if main:
        y = WINDOW_HEIGHT - main.y
        if abs(y - main.y) < 120:
            y = main.y + (160 if main.y < WINDOW_HEIGHT / 2 else -160)
    y = max(BALL_RADIUS + 40, min(WINDOW_HEIGHT - BALL_RADIUS - 40, y))
    angle = random.uniform(-0.7, 0.7)
    extra = Ball(
        WINDOW_WIDTH // 2, y,
        base_speed * direction, base_speed * angle,
        is_main=False,
    )
    extra.base_speed = math.hypot(extra.vx, extra.vy)
    state.balls.append(extra)


def init_obstacles(state):
    """Initialize obstacle blocks (called when starting a new game)."""
    state.obstacles.clear()
    if not state.settings["obstacles_enabled"]:
        return
    center_x = WINDOW_WIDTH // 2
    zone_w = 300
    for _ in range(OBSTACLE_COUNT):
        w = random.randint(OBSTACLE_MIN_SIZE, OBSTACLE_MAX_SIZE)
        h = random.randint(OBSTACLE_MIN_SIZE, OBSTACLE_MAX_SIZE)
        x = center_x - zone_w // 2 + random.randint(0, zone_w - w)
        y = random.randint(50, WINDOW_HEIGHT - 50 - h)
        vy = random.choice([-1, 1]) * random.uniform(
            OBSTACLE_SPEED_MIN, OBSTACLE_SPEED_MAX
        )
        state.obstacles.append(Obstacle(x, y, w, h, vy))


def update_obstacles(state):
    """Move obstacles and bounce off top/bottom walls."""
    dt = state.dt
    for obs in state.obstacles:
        obs.y += obs.vy * dt
        if obs.y <= 0:
            obs.y = 0
            obs.vy = abs(obs.vy)
        elif obs.y + obs.h >= WINDOW_HEIGHT:
            obs.y = WINDOW_HEIGHT - obs.h
            obs.vy = -abs(obs.vy)
