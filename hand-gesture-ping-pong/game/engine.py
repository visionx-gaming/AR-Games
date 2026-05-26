"""Game engine: ball/paddle physics, collision detection, power-ups, obstacles."""

import random
import math
from game.config import (
    WINDOW_WIDTH, WINDOW_HEIGHT, BALL_RADIUS, PADDLE_WIDTH, PADDLE_HEIGHT,
    LEFT_PADDLE_X, RIGHT_PADDLE_X, PADDLE_LERP_FACTOR, TRAIL_LENGTH,
    DIFFICULTY_SPEEDS, DIFFICULTY_AI_SPEEDS, SPEED_INCREMENT, MAX_BALL_SPEED,
    POWERUP_TYPES, POWERUP_RADIUS, POWERUP_SPAWN_MIN, POWERUP_SPAWN_MAX,
    POWERUP_LIFETIME,
    BIG_PADDLE_MULTIPLIER, SPEED_BOOST_MULTIPLIER, SLOW_MOTION_MULTIPLIER,
    OBSTACLE_COUNT, OBSTACLE_MIN_SIZE, OBSTACLE_MAX_SIZE,
    OBSTACLE_SPEED_MIN, OBSTACLE_SPEED_MAX,
    TIME_ATTACK_DURATION,
    get_theme,
)
from game.state import Ball, PowerUpItem, Obstacle
from game import effects
from game.utils import lerp


# ===================================================================
#  PADDLE
# ===================================================================

def update_paddles(state):
    """Update paddle positions with lerp smoothing."""
    dt = state.dt

    # Left paddle — hand-controlled
    if state.hand_pos["Left"]:
        state.left_paddle_target = float(
            state.hand_pos["Left"][1] - state.left_paddle_height // 2
        )

    # Right paddle — AI or hand-controlled
    if state.settings["ai_enabled"]:
        base_ai = DIFFICULTY_AI_SPEEDS[state.settings["difficulty"]]
        main_ball = next((b for b in state.balls if b.is_main), None)
        ai_speed = min(base_ai + (main_ball.hit_count * 3 if main_ball else 0), base_ai * 1.8)
        if main_ball:
            ai_target = main_ball.y - state.right_paddle_height // 2
            diff = ai_target - state.right_paddle_target
            max_move = ai_speed * dt
            if abs(diff) > max_move:
                state.right_paddle_target += max_move if diff > 0 else -max_move
            else:
                state.right_paddle_target = ai_target
    else:
        if state.hand_pos["Right"]:
            state.right_paddle_target = float(
                state.hand_pos["Right"][1] - state.right_paddle_height // 2
            )

    # Smooth movement
    state.left_paddle_y = lerp(
        state.left_paddle_y, state.left_paddle_target, PADDLE_LERP_FACTOR
    )
    state.right_paddle_y = lerp(
        state.right_paddle_y, state.right_paddle_target, PADDLE_LERP_FACTOR
    )

    # Clamp to screen
    state.left_paddle_y = max(
        0, min(WINDOW_HEIGHT - state.left_paddle_height, state.left_paddle_y)
    )
    state.right_paddle_y = max(
        0, min(WINDOW_HEIGHT - state.right_paddle_height, state.right_paddle_y)
    )


def center_paddles(state):
    """Reset paddles to center position."""
    cl = float(WINDOW_HEIGHT // 2 - state.left_paddle_height // 2)
    cr = float(WINDOW_HEIGHT // 2 - state.right_paddle_height // 2)
    state.left_paddle_y = cl
    state.right_paddle_y = cr
    state.left_paddle_target = cl
    state.right_paddle_target = cr


# ===================================================================
#  BALL
# ===================================================================

def _get_speed_multiplier(state):
    """Get ball speed multiplier from active power-ups."""
    mult = 1.0
    t = state.current_time
    if "speed_boost" in state.active_effects and state.active_effects["speed_boost"] > t:
        mult *= SPEED_BOOST_MULTIPLIER
    if "slow_motion" in state.active_effects and state.active_effects["slow_motion"] > t:
        mult *= SLOW_MOTION_MULTIPLIER
    return mult


def update_balls(state):
    """Update all ball positions with spin/curve physics."""
    dt = state.dt
    for ball in state.balls:
        if not ball.alive:
            continue
        # Apply spin curve
        ball.vy += ball.curve * dt * 200
        ball.curve *= 0.98  # Decay spin
        # Move
        ball.x += ball.vx * dt
        ball.y += ball.vy * dt
        # Trail (deque with maxlen=TRAIL_LENGTH handles overflow automatically)
        ball.trail.append((ball.x, ball.y))


def reset_ball(state):
    """Create / reset the main ball at center with a random direction."""
    base_speed = DIFFICULTY_SPEEDS[state.settings["difficulty"]]
    direction = random.choice([-1, 1])
    angle = random.uniform(-0.5, 0.5)
    main_ball = Ball(
        WINDOW_WIDTH // 2, WINDOW_HEIGHT // 2,
        base_speed * direction, base_speed * angle,
        is_main=True,
    )
    # Keep only alive extra balls
    state.balls = [b for b in state.balls if not b.is_main and b.alive]
    state.balls.insert(0, main_ball)


def _spawn_extra_ball(state):
    """Spawn an extra (non-scoring) ball for multi-ball power-up."""
    base_speed = DIFFICULTY_SPEEDS[state.settings["difficulty"]]
    direction = random.choice([-1, 1])
    angle = random.uniform(-0.7, 0.7)
    extra = Ball(
        WINDOW_WIDTH // 2, WINDOW_HEIGHT // 2,
        base_speed * direction, base_speed * angle,
        is_main=False,
    )
    state.balls.append(extra)


# ===================================================================
#  COLLISIONS
# ===================================================================

def _check_one_paddle(state, ball, side, sound_mgr, theme):
    """Check collision and miss for one paddle side. Returns True if ball was hit."""
    if side == "left":
        edge = LEFT_PADDLE_X + PADDLE_WIDTH
        pad_y = state.left_paddle_y
        pad_h = state.left_paddle_height
        moving_toward = ball.vx < 0
        hit_cond = (ball.x - BALL_RADIUS <= edge
                    and ball.x + BALL_RADIUS >= LEFT_PADDLE_X)
        miss_cond = ball.x - BALL_RADIUS <= 0
        bounce_dir = +1
        clamp_x = edge + BALL_RADIUS
        color = theme["left_paddle"]
    else:
        edge = RIGHT_PADDLE_X - PADDLE_WIDTH
        pad_y = state.right_paddle_y
        pad_h = state.right_paddle_height
        moving_toward = ball.vx > 0
        hit_cond = (ball.x + BALL_RADIUS >= edge
                    and ball.x - BALL_RADIUS <= RIGHT_PADDLE_X)
        miss_cond = ball.x + BALL_RADIUS >= WINDOW_WIDTH
        bounce_dir = -1
        clamp_x = edge - BALL_RADIUS
        color = theme["right_paddle"]

    in_y = (ball.y + BALL_RADIUS >= pad_y
            and ball.y - BALL_RADIUS <= pad_y + pad_h)

    if moving_toward and hit_cond and in_y:
        _apply_paddle_bounce(state, ball, pad_y, pad_h, bounce_dir, sound_mgr)
        ball.x = clamp_x
        effects.spawn_particles(state, ball.x, ball.y, color, 15)
        effects.add_shockwave(state, ball.x, ball.y, color)
        effects.increment_combo(state)
        if state.combo_count > 0 and state.combo_count % 5 == 0:
            sound_mgr.play_combo()
        if state.settings["game_mode"] == 1:
            state.survival_rally += 1
        return True

    if moving_toward and miss_cond:
        _handle_miss(state, ball, side, sound_mgr, theme)
    return False


def check_all_collisions(state, sound_mgr):
    """Check wall, paddle, obstacle, power-up collisions for all balls."""
    theme = get_theme(state.settings)

    for ball in state.balls[:]:                       # iterate copy
        if not ball.alive:
            continue

        # ---- Wall collision (top / bottom) ----
        if ball.y <= BALL_RADIUS:
            ball.vy = abs(ball.vy)
            ball.y = BALL_RADIUS
            sound_mgr.play_wall()
        elif ball.y >= WINDOW_HEIGHT - BALL_RADIUS:
            ball.vy = -abs(ball.vy)
            ball.y = WINDOW_HEIGHT - BALL_RADIUS
            sound_mgr.play_wall()

        # ---- Paddle collisions ----
        _check_one_paddle(state, ball, "left", sound_mgr, theme)
        _check_one_paddle(state, ball, "right", sound_mgr, theme)

        # ---- Obstacle collisions ----
        if state.settings["obstacles_enabled"]:
            for obs in state.obstacles:
                if (ball.x + BALL_RADIUS > obs.x
                        and ball.x - BALL_RADIUS < obs.x + obs.w
                        and ball.y + BALL_RADIUS > obs.y
                        and ball.y - BALL_RADIUS < obs.y + obs.h):
                    ox = min(ball.x + BALL_RADIUS - obs.x,
                             obs.x + obs.w - (ball.x - BALL_RADIUS))
                    oy = min(ball.y + BALL_RADIUS - obs.y,
                             obs.y + obs.h - (ball.y - BALL_RADIUS))
                    if ox < oy:
                        ball.vx = -ball.vx
                        if ball.x < obs.x + obs.w / 2:
                            ball.x = obs.x - BALL_RADIUS
                        else:
                            ball.x = obs.x + obs.w + BALL_RADIUS
                    else:
                        ball.vy = -ball.vy
                        if ball.y < obs.y + obs.h / 2:
                            ball.y = obs.y - BALL_RADIUS
                        else:
                            ball.y = obs.y + obs.h + BALL_RADIUS
                    sound_mgr.play_wall()
                    effects.spawn_particles(state, ball.x, ball.y,
                                            theme["obstacle"], 8)

        # ---- Power-up collection ----
        for pu in state.powerups[:]:
            dist = math.sqrt((ball.x - pu.x) ** 2 + (ball.y - pu.y) ** 2)
            if dist < BALL_RADIUS + POWERUP_RADIUS:
                _activate_powerup(state, ball, pu, sound_mgr)
                state.powerups.remove(pu)

    # Remove dead balls
    state.balls = [b for b in state.balls if b.alive]

    # Safety: always have a main ball while playing
    if state.game_state == "PLAYING" and not any(b.is_main for b in state.balls):
        reset_ball(state)


def _apply_paddle_bounce(state, ball, paddle_y, paddle_h, direction, sound_mgr):
    """Bounce the ball off a paddle with angle-based physics and spin."""
    relative_hit = (ball.y - (paddle_y + paddle_h / 2)) / (paddle_h / 2)
    relative_hit = max(-1, min(1, relative_hit))

    ball.hit_count += 1
    speed = DIFFICULTY_SPEEDS[state.settings["difficulty"]] + ball.hit_count * SPEED_INCREMENT
    speed = min(speed, MAX_BALL_SPEED)  # cap to prevent tunneling through paddles
    speed *= _get_speed_multiplier(state)

    max_angle = math.pi / 4
    bounce_angle = relative_hit * max_angle

    ball.vx = direction * abs(speed * math.cos(bounce_angle))
    ball.vy = speed * math.sin(bounce_angle)
    ball.curve = relative_hit * 0.5          # Spin based on edge of paddle hit

    sound_mgr.play_hit()
    state.hit_animation_time = state.current_time


def _handle_miss(state, ball, side, sound_mgr, theme):
    """Handle when a ball goes past a paddle (miss/score)."""
    if not ball.is_main:
        ball.alive = False
        return

    sound_mgr.play_lose()
    miss_x = 0 if side == "left" else WINDOW_WIDTH
    effects.spawn_particles(state, miss_x, ball.y, (50, 50, 255), 20)
    effects.trigger_screen_shake(state)
    effects.reset_combo(state)

    game_mode = state.settings["game_mode"]

    if game_mode == 0:                       # Classic
        if side == "left":
            state.score[1] += 1
            state.score_flash_time[1] = state.current_time
            effects.add_floating_text(
                state, WINDOW_WIDTH * 3 // 4, 80, "+1", theme["score_popup"]
            )
            if state.score[1] >= state.settings["score_to_win"]:
                state.winner = "Right Player"
                _trigger_game_over(state)
                return
        else:
            state.score[0] += 1
            state.score_flash_time[0] = state.current_time
            effects.add_floating_text(
                state, WINDOW_WIDTH // 4, 80, "+1", theme["score_popup"]
            )
            if state.score[0] >= state.settings["score_to_win"]:
                state.winner = "Left Player"
                _trigger_game_over(state)
                return
        _reset_round(state)

    elif game_mode == 1:                     # Survival
        state.winner = f"Rally: {state.survival_rally}"
        _trigger_game_over(state)

    elif game_mode == 2:                     # Time Attack
        if side == "left":
            state.score[1] += 1
            state.score_flash_time[1] = state.current_time
            effects.add_floating_text(
                state, WINDOW_WIDTH * 3 // 4, 80, "+1", theme["score_popup"]
            )
        else:
            state.score[0] += 1
            state.score_flash_time[0] = state.current_time
            effects.add_floating_text(
                state, WINDOW_WIDTH // 4, 80, "+1", theme["score_popup"]
            )
        _reset_round(state)


def _trigger_game_over(state):
    """Transition to GAMEOVER state."""
    high = max(state.score)
    if state.settings["game_mode"] == 1:
        high = state.survival_rally
    if high > state.high_score:
        state.high_score = high
    state.game_state = "GAMEOVER"
    state.restart_gesture_time = None


def _reset_round(state):
    """Reset for next round after a score."""
    reset_ball(state)
    state.powerups.clear()  # prevent stale power-ups from blocking new spawns
    state.countdown_start = state.current_time
    state.game_state = "COUNTDOWN"


# ===================================================================
#  POWER-UPS
# ===================================================================

def update_powerups(state, sound_mgr):
    """Spawn new power-ups periodically and expire active effects."""
    t = state.current_time

    # Spawn
    if t >= state.next_powerup_time and len(state.powerups) < 2:
        ptype = random.choice(list(POWERUP_TYPES.keys()))
        margin = 200
        x = random.randint(margin, WINDOW_WIDTH - margin)
        y = random.randint(80, WINDOW_HEIGHT - 80)
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

    # Remove extra balls when multi_ball effect ends
    if "multi_ball" not in state.active_effects:
        state.balls = [b for b in state.balls if b.is_main]

    # Expire uncollected court power-ups
    state.powerups = [pu for pu in state.powerups
                      if t - pu.spawn_time < POWERUP_LIFETIME]


def _activate_powerup(state, ball, pu, sound_mgr):
    """Activate a collected power-up. ball is the one that touched it."""
    t = state.current_time
    info = POWERUP_TYPES[pu.type]
    duration = info["duration"]

    sound_mgr.play_powerup()
    effects.add_floating_text(state, pu.x, pu.y - 30, info["label"], (0, 255, 255))

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
            _spawn_extra_ball(state)


# ===================================================================
#  OBSTACLES
# ===================================================================

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


def check_time_attack(state):
    """End the game if Time Attack timer has expired."""
    if state.settings["game_mode"] != 2:
        return
    if state.game_state != "PLAYING":
        return
    elapsed = state.current_time - state.play_start_time
    if elapsed >= TIME_ATTACK_DURATION:
        if state.score[0] > state.score[1]:
            state.winner = "Left Player"
        elif state.score[1] > state.score[0]:
            state.winner = "Right Player"
        else:
            state.winner = "Draw"
        _trigger_game_over(state)
