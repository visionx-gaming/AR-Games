"""Game engine: paddles, the CPU, ball physics, collisions, scoring and round flow.

Power-ups and obstacles live in game.powerups; the vs-CPU difficulty ramp in game.difficulty."""

import random
import math
from game.config import (
    WINDOW_WIDTH, WINDOW_HEIGHT, BALL_RADIUS, PADDLE_WIDTH, LEFT_PADDLE_X, RIGHT_PADDLE_X,
    PADDLE_LERP_FACTOR, DIFFICULTY_SPEEDS, DIFFICULTY_AI_SPEEDS, DIFFICULTY_AI_ERROR,
    RAMP_AI_SPEED, RAMP_AI_ERROR, RAMP_BALL_SPEED, SPEED_INCREMENT, MAX_BALL_SPEED,
    SERVE_SPEED_FACTOR, SERVE_MAX_SLOPE, PHYSICS_MAX_STEP, KEYBOARD_PADDLE_STEP,
    POWERUP_RADIUS, SPEED_BOOST_MULTIPLIER, SLOW_MOTION_MULTIPLIER, TIME_ATTACK_DURATION,
    get_theme,
)
from game.state import Ball
from game import difficulty, effects, keys, powerups

_KEY_UP_RAW = keys.UP
_KEY_DOWN_RAW = keys.DOWN


# ===================================================================
#  PADDLE
# ===================================================================

def _lerp_factor(dt):
    """PADDLE_LERP_FACTOR is defined per 60 fps frame; convert for any dt."""
    return 1.0 - (1.0 - PADDLE_LERP_FACTOR) ** (dt * 60.0)


def apply_keyboard_paddles(state, key, key_raw):
    """Keyboard fallback / assist: W/S move the left paddle, arrows the right
    (arrows also drive the left paddle when playing against the AI)."""
    up = key in (ord('w'), ord('W'))
    down = key in (ord('s'), ord('S'))
    arrow_up = key_raw == _KEY_UP_RAW
    arrow_down = key_raw == _KEY_DOWN_RAW
    cpu = state.cpu_side()

    d_left = 0
    d_right = 0
    if cpu is None:
        d_left = (1 if down else 0) - (1 if up else 0)
        d_right = (1 if arrow_down else 0) - (1 if arrow_up else 0)
    else:                                # vs CPU: W/S and the arrows all steer your paddle
        d = (1 if (down or arrow_down) else 0) - (1 if (up or arrow_up) else 0)
        if cpu == "right":
            d_left = d
        else:
            d_right = d
    if d_left:
        state.left_paddle_target += d_left * KEYBOARD_PADDLE_STEP
    if d_right:
        state.right_paddle_target += d_right * KEYBOARD_PADDLE_STEP


def update_paddles(state):
    """Update paddle positions with lerp smoothing."""
    dt = state.dt

    # Each paddle follows its hand, except the CPU's (see _update_ai)
    cpu = state.cpu_side()
    if cpu != "left" and state.hand_pos["Left"]:
        state.left_paddle_target = float(
            state.hand_pos["Left"][1] - state.left_paddle_height // 2
        )
    if cpu != "right" and state.hand_pos["Right"]:
        state.right_paddle_target = float(
            state.hand_pos["Right"][1] - state.right_paddle_height // 2
        )
    if cpu:
        _update_ai(state, dt, cpu)

    # Keep targets reachable (keyboard steps can push them off-screen)
    state.left_paddle_target = max(
        0.0, min(WINDOW_HEIGHT - state.left_paddle_height, state.left_paddle_target))
    state.right_paddle_target = max(
        0.0, min(WINDOW_HEIGHT - state.right_paddle_height, state.right_paddle_target))

    # Smooth movement (frame-rate independent)
    f = _lerp_factor(dt)
    state.left_paddle_y += (state.left_paddle_target - state.left_paddle_y) * f
    state.right_paddle_y += (state.right_paddle_target - state.right_paddle_y) * f

    # Clamp to screen
    state.left_paddle_y = max(
        0, min(WINDOW_HEIGHT - state.left_paddle_height, state.left_paddle_y)
    )
    state.right_paddle_y = max(
        0, min(WINDOW_HEIGHT - state.right_paddle_height, state.right_paddle_y)
    )


def _update_ai(state, dt, side="right"):
    """AI paddle: tracks the ball only while it is coming, with a per-return
    aiming error; otherwise drifts back to centre."""
    diff_idx = state.settings["difficulty"]
    base_ai = DIFFICULTY_AI_SPEEDS[diff_idx]
    toward = (lambda b: b.vx > 0) if side == "right" else (lambda b: b.vx < 0)
    incoming = [b for b in state.balls if b.alive and toward(b)]
    # the ball that will reach the CPU first (any ball, not just the "main" one)
    main_ball = (min(incoming, key=lambda b: (WINDOW_WIDTH - b.x) if side == "right" else b.x)
                 if incoming else next((b for b in state.balls if b.is_main), None))
    ai_speed = min(base_ai + (main_ball.hit_count * 3 if main_ball else 0), base_ai * 1.8) * difficulty.ramp(state, RAMP_AI_SPEED)

    height = getattr(state, f"{side}_paddle_height")
    target_attr = f"{side}_paddle_target"
    center = WINDOW_HEIGHT / 2 - height / 2
    coming = main_ball is not None and (main_ball.vx > 0 if side == "right" else main_ball.vx < 0)
    ai_target = main_ball.y + state.ai_aim_offset - height / 2 if coming else center

    diff = ai_target - getattr(state, target_attr)
    max_move = ai_speed * dt
    if abs(diff) > max_move:
        setattr(state, target_attr, getattr(state, target_attr) + (max_move if diff > 0 else -max_move))
    else:
        setattr(state, target_attr, ai_target)


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
    t = state.game_time
    if "speed_boost" in state.active_effects and state.active_effects["speed_boost"] > t:
        mult *= SPEED_BOOST_MULTIPLIER
    if "slow_motion" in state.active_effects and state.active_effects["slow_motion"] > t:
        mult *= SLOW_MOTION_MULTIPLIER
    return mult


def update_balls(state):
    """Advance all balls by state.dt: spin curve, power-up speed easing, move."""
    dt = state.dt
    mult = _get_speed_multiplier(state)
    ease = 1.0 - math.exp(-8.0 * dt)
    spin_decay = 0.98 ** (dt * 60.0)
    for ball in state.balls:
        if not ball.alive:
            continue
        # Apply spin curve
        ball.vy += ball.curve * dt * 200
        ball.curve *= spin_decay

        # Ease speed toward base_speed * power-up multiplier. This applies
        # speed-boost / slow-motion to a ball already in flight (and restores
        # it when they expire), and keeps spin from exceeding the speed cap.
        speed = math.hypot(ball.vx, ball.vy)
        want = ball.base_speed * mult
        if speed > 1e-6 and abs(speed - want) > 0.5:
            k = (speed + (want - speed) * ease) / speed
            ball.vx *= k
            ball.vy *= k

        ball.x += ball.vx * dt
        ball.y += ball.vy * dt


def step_physics(state, sound_mgr, dt):
    """Run ball / collision / obstacle updates in small fixed-size substeps so
    fast balls cannot tunnel through paddles at low frame rates."""
    n = max(1, math.ceil(dt / PHYSICS_MAX_STEP))
    step = dt / n
    try:
        for _ in range(n):
            state.dt = step
            update_balls(state)
            powerups.update_obstacles(state)
            check_all_collisions(state, sound_mgr)
            if state.game_state != "PLAYING":
                break
    finally:
        state.dt = dt
    for ball in state.balls:
        if ball.alive:
            ball.trail.append((ball.x, ball.y))


def reset_ball(state, serve_toward=None):
    """Create / reset the main ball at center.

    serve_toward: "left" / "right" serves at the player who just lost the
    point; None picks a random direction (start of a game).  The serve is
    slower and flatter than a rally shot (see SERVE_SPEED_FACTOR)."""
    base_speed = DIFFICULTY_SPEEDS[state.settings["difficulty"]] * difficulty.ramp(state, RAMP_BALL_SPEED) * SERVE_SPEED_FACTOR
    if serve_toward == "left":
        direction = -1
    elif serve_toward == "right":
        direction = 1
    else:
        direction = random.choice([-1, 1])
    angle = random.uniform(-SERVE_MAX_SLOPE, SERVE_MAX_SLOPE)
    main_ball = Ball(
        WINDOW_WIDTH // 2, WINDOW_HEIGHT // 2,
        base_speed * direction, base_speed * angle,
        is_main=True,
    )
    main_ball.base_speed = math.hypot(main_ball.vx, main_ball.vy)
    # Keep only alive extra balls
    state.balls = [b for b in state.balls if not b.is_main and b.alive]
    state.balls.insert(0, main_ball)


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
        effects.paddle_hit(state, side, ball, math.hypot(ball.vx, ball.vy) / MAX_BALL_SPEED)
        effects.increment_combo(state)
        if state.combo_count > 0 and state.combo_count % 5 == 0:
            sound_mgr.play_combo()
        state.survival_rally += 1
        if state.survival_rally > state.max_rally:
            state.max_rally = state.survival_rally
        if state.cpu_side() and side != state.cpu_side():
            # New return incoming: the AI picks a fresh (imperfect) aim point
            err = DIFFICULTY_AI_ERROR[state.settings["difficulty"]] * difficulty.ramp(state, RAMP_AI_ERROR)
            state.ai_aim_offset = random.uniform(-err, err)
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
        if state.game_state != "PLAYING":
            break

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
        if state.game_state != "PLAYING" or not ball.alive:
            continue
        _check_one_paddle(state, ball, "right", sound_mgr, theme)
        if state.game_state != "PLAYING" or not ball.alive:
            continue

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
                    # Reflect away from the obstacle (never toward it), so a
                    # moving block can't reverse a ball that is leaving it.
                    if ox < oy:
                        if ball.x < obs.x + obs.w / 2:
                            ball.vx = -abs(ball.vx)
                            ball.x = obs.x - BALL_RADIUS
                        else:
                            ball.vx = abs(ball.vx)
                            ball.x = obs.x + obs.w + BALL_RADIUS
                    else:
                        if ball.y < obs.y + obs.h / 2:
                            ball.vy = -abs(ball.vy)
                            ball.y = obs.y - BALL_RADIUS
                        else:
                            ball.vy = abs(ball.vy)
                            ball.y = obs.y + obs.h + BALL_RADIUS
                    sound_mgr.play_wall()
                    effects.spawn_particles(state, ball.x, ball.y,
                                            theme["obstacle"], 8)

        # ---- Power-up collection ----
        for pu in state.powerups[:]:
            dist = math.sqrt((ball.x - pu.x) ** 2 + (ball.y - pu.y) ** 2)
            if dist < BALL_RADIUS + POWERUP_RADIUS:
                powerups.activate_powerup(state, ball, pu, sound_mgr, theme)
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
    base = DIFFICULTY_SPEEDS[state.settings["difficulty"]] * difficulty.ramp(state, RAMP_BALL_SPEED) + ball.hit_count * SPEED_INCREMENT
    base = min(base, MAX_BALL_SPEED)
    ball.base_speed = base
    speed = base * _get_speed_multiplier(state)

    max_angle = math.pi / 4
    bounce_angle = relative_hit * max_angle

    ball.vx = direction * abs(speed * math.cos(bounce_angle))
    ball.vy = speed * math.sin(bounce_angle)
    ball.curve = relative_hit * 0.5          # Spin based on edge of paddle hit

    sound_mgr.play_hit()
    state.hit_animation_time = state.current_time


def _award_point(state, missed_side, theme):
    """Give the point for a ball that got past `missed_side`.
    Returns True if that ended the game."""
    idx = 1 if missed_side == "left" else 0
    state.score[idx] += 1
    state.point_log.append((round(state.game_time, 1), idx, state.score[0], state.score[1]))
    state.score_flash_time[idx] = state.current_time
    px = WINDOW_WIDTH * 3 // 4 if idx == 1 else WINDOW_WIDTH // 4
    effects.add_floating_text(state, px, 128, "+1", theme["score_popup"])
    if (state.settings["game_mode"] == 0
            and state.score[idx] >= state.settings["score_to_win"]):
        state.winner = "Right Player" if idx == 1 else "Left Player"
        _trigger_game_over(state)
        return True
    return False


def _handle_miss(state, ball, side, sound_mgr, theme):
    """Handle when a ball goes past a paddle (miss/score)."""
    game_mode = state.settings["game_mode"]
    miss_x = 0 if side == "left" else WINDOW_WIDTH

    # Multi-ball: every ball is equal.  Any ball that gets past a paddle is a miss for
    # that side (one point to the opponent); the round carries on while another ball is
    # still in play and is re-served once the last one is gone.
    ball.alive = False
    sound_mgr.play_lose()
    effects.spawn_particles(state, miss_x, ball.y, (50, 50, 255), 20)
    effects.trigger_screen_shake(state)
    effects.reset_combo(state)

    if game_mode == 1:                       # Survival
        if state.cpu_side() != side:
            state.winner = f"Rally: {state.survival_rally}"
            _trigger_game_over(state)
            return
        # The AI dropping it isn't the player's failure: keep the rally going
        keep_rally = True
    else:                                    # Classic / Time Attack
        if _award_point(state, side, theme):
            return
        keep_rally = False

    others = [b for b in state.balls if b.alive and b is not ball]
    if others:
        if not any(b.is_main for b in others):
            others[0].is_main = True         # play on with the remaining ball
        if len(others) == 1:
            state.active_effects.pop("multi_ball", None)
        return
    _reset_round(state, side, keep_rally=keep_rally)


def _trigger_game_over(state):
    """Transition to GAMEOVER state."""
    state.game_state = "GAMEOVER"
    state.restart_gesture_time = None
    state.gesture_armed = False
    state.gameover_time = state.current_time


def _reset_round(state, missed_side, keep_rally=False):
    """Reset for next round after a score; serve at the player who just lost."""
    state.balls = [b for b in state.balls if b.is_main]
    state.active_effects.pop("multi_ball", None)
    reset_ball(state, serve_toward=missed_side)
    state.powerups.clear()  # prevent stale power-ups from blocking new spawns
    if not keep_rally:
        state.survival_rally = 0
    state.countdown_start = state.current_time
    state.game_state = "COUNTDOWN"


# ===================================================================
#  POWER-UPS
# ===================================================================


# ===================================================================
#  OBSTACLES
# ===================================================================


def check_time_attack(state):
    """End the game if Time Attack timer has expired."""
    if state.settings["game_mode"] != 2:
        return
    if state.game_state != "PLAYING":
        return
    if state.game_time >= TIME_ATTACK_DURATION:
        if state.score[0] > state.score[1]:
            state.winner = "Left Player"
        elif state.score[1] > state.score[0]:
            state.winner = "Right Player"
        else:
            state.winner = "Draw"
        _trigger_game_over(state)
