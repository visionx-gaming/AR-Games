import cv2
import numpy as np
import mediapipe as mp
import pygame
import time

# ----- Initialize Pygame for sound -----
pygame.init()
pygame.mixer.init()
hit_sound = pygame.mixer.Sound("hit.wav")
lose_sound = pygame.mixer.Sound("lose.mp3")
hit_sound.set_volume(1.0)
lose_sound.set_volume(1.0)

# ----- Initialize Mediapipe Hand Tracking -----
mp_hands = mp.solutions.hands
hands_detector = mp_hands.Hands(min_detection_confidence=0.7, min_tracking_confidence=0.7)
mp_drawing = mp.solutions.drawing_utils

# ----- Game Parameters -----
window_width, window_height = 1200, 720
ball_radius = 20
ball_speed = [20, 20]
ball_position = [window_width // 2, window_height // 2]
default_ball_color = (0, 255, 0)   # Green normally
hit_flash_color = (255, 0, 0)        # Red flash on hit

rod_height = 150
rod_width = 20
# For hand control, rod x-positions remain fixed:
left_rod_x = 10
right_rod_x = window_width - 10

# Score tracking and high score
score = [0, 0]  # [left, right]
high_score = 0

# Game states: "START", "PLAYING", "PAUSED", "GAMEOVER"
game_state = "START"

# Hit flash timing
hit_animation_time = 0
hit_flash_duration = 0.2  # seconds

# Variables to track gesture timing in START and GAMEOVER states
restart_gesture_start_time = None
start_gesture_start_time = None
# Time (in seconds) both hands must be detected to trigger a state change
gesture_required_duration = 1.0

# ----- OpenCV Video Capture -----
cap = cv2.VideoCapture(0)
cap.set(cv2.CAP_PROP_FRAME_WIDTH, window_width)
cap.set(cv2.CAP_PROP_FRAME_HEIGHT, window_height)

last_time = time.time()

# ----- Helper functions for overlays -----
def show_start_screen(frame):
    cv2.putText(frame, "Welcome to Hand-Controlled Pong!", (window_width // 4, window_height // 3),
                cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2)
    cv2.putText(frame, "Wave both hands to Start", (window_width // 4, window_height // 2),
                cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 0), 2)
    cv2.putText(frame, "High Score: {}".format(high_score), (window_width // 4, window_height // 2 + 50),
                cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 255), 2)
    return frame

def show_pause_screen(frame):
    cv2.putText(frame, "Game Paused", (window_width // 3, window_height // 2),
                cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2)
    cv2.putText(frame, "Press 'R' to Resume", (window_width // 3, window_height // 2 + 50),
                cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2)
    return frame

def show_game_over_screen(frame, winner):
    cv2.putText(frame, "Game Over!", (window_width // 3, window_height // 3),
                cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2)
    cv2.putText(frame, "{} Wins!".format(winner), (window_width // 3, window_height // 3 + 50),
                cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2)
    cv2.putText(frame, "Score: Left {}  Right {}".format(score[0], score[1]),
                (window_width // 3, window_height // 3 + 100), cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 0), 2)
    cv2.putText(frame, "High Score: {}".format(high_score),
                (window_width // 3, window_height // 3 + 150), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 255), 2)
    cv2.putText(frame, "Wave both hands to Restart", (window_width // 3, window_height // 3 + 200),
                cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2)
    return frame

def detect_hand_position(image, results):
    # Returns the center (x, y) of the detected hand for each side if available.
    hand_positions = {"Left": None, "Right": None}
    if results.multi_hand_landmarks:
        for hand_landmarks, hand_class in zip(results.multi_hand_landmarks, results.multi_handedness):
            x_coords = [lm.x for lm in hand_landmarks.landmark]
            y_coords = [lm.y for lm in hand_landmarks.landmark]
            center = (int(np.mean(x_coords) * window_width), int(np.mean(y_coords) * window_height))
            label = hand_class.classification[0].label
            hand_positions[label] = center
    return hand_positions

# ----- Main Game Loop -----
while True:
    ret, frame = cap.read()
    if not ret:
        break

    frame = cv2.flip(frame, 1)
    frame = cv2.resize(frame, (window_width, window_height))
    current_time = time.time()
    dt = current_time - last_time
    last_time = current_time

    key = cv2.waitKey(1) & 0xFF

    # Process Mediapipe hand detection in states where gesture is needed.
    if game_state in ["START", "PLAYING", "GAMEOVER"]:
        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        results = hands_detector.process(rgb_frame)
        hand_pos = detect_hand_position(rgb_frame, results)
    else:
        hand_pos = {"Left": None, "Right": None}

    # Update rod positions in PLAYING state using detected hand positions.
    if game_state == "PLAYING":
        if hand_pos["Left"]:
            left_rod_y = hand_pos["Left"][1] - rod_height // 2
        else:
            left_rod_y = window_height // 2 - rod_height // 2

        if hand_pos["Right"]:
            right_rod_y = hand_pos["Right"][1] - rod_height // 2
        else:
            right_rod_y = window_height // 2 - rod_height // 2
    else:
        # For non-playing states, center the rods.
        left_rod_y = window_height // 2 - rod_height // 2
        right_rod_y = window_height // 2 - rod_height // 2

    # ----- Game State Management -----
    if game_state == "START":
        frame = show_start_screen(frame)
        # Instead of pressing 'S', check if both hands are detected.
        if hand_pos["Left"] is not None and hand_pos["Right"] is not None:
            if start_gesture_start_time is None:
                start_gesture_start_time = current_time
            elif current_time - start_gesture_start_time >= gesture_required_duration:
                # Both hands detected continuously; start the game.
                score = [0, 0]
                ball_position = [window_width // 2, window_height // 2]
                ball_speed = [20, 20]
                game_state = "PLAYING"
                start_gesture_start_time = None
        else:
            start_gesture_start_time = None

    elif game_state == "PLAYING":
        # Update ball position
        ball_position[0] += ball_speed[0]
        ball_position[1] += ball_speed[1]

        # Collision with top and bottom
        if ball_position[1] <= ball_radius or ball_position[1] >= window_height - ball_radius:
            ball_speed[1] = -ball_speed[1]

        # Collision with left rod (using hand-controlled left_rod_y)
        if (ball_position[0] - ball_radius <= left_rod_x + rod_width and
            left_rod_y <= ball_position[1] <= left_rod_y + rod_height):
            ball_speed[0] = -ball_speed[0]
            hit_sound.play()
            hit_animation_time = current_time
            score[0] += 1  # Left player's score increases on hit
        elif ball_position[0] - ball_radius <= 0:
            lose_sound.play()
            game_state = "GAMEOVER"
            winner = "Right"
            if max(score) > high_score:
                high_score = max(score)
            restart_gesture_start_time = None

        # Collision with right rod (using hand-controlled right_rod_y)
        if (ball_position[0] + ball_radius >= right_rod_x - rod_width and
            right_rod_y <= ball_position[1] <= right_rod_y + rod_height):
            ball_speed[0] = -ball_speed[0]
            hit_sound.play()
            hit_animation_time = current_time
            score[1] += 1  # Right player's score increases on hit
        elif ball_position[0] + ball_radius >= window_width:
            lose_sound.play()
            game_state = "GAMEOVER"
            winner = "Left"
            if max(score) > high_score:
                high_score = max(score)
            restart_gesture_start_time = None

        # Visual hit feedback: flash ball color if hit occurred recently
        if current_time - hit_animation_time < hit_flash_duration:
            current_ball_color = hit_flash_color
        else:
            current_ball_color = default_ball_color

        # Draw game objects
        cv2.circle(frame, tuple(ball_position), ball_radius, current_ball_color, -1)
        cv2.rectangle(frame, (left_rod_x, left_rod_y),
                      (left_rod_x + rod_width, left_rod_y + rod_height), (255, 0, 0), -1)
        cv2.rectangle(frame, (right_rod_x - rod_width, right_rod_y),
                      (right_rod_x, right_rod_y + rod_height), (0, 0, 255), -1)

        # Draw scoreboard
        cv2.putText(frame, f"Left: {score[0]}", (50, 50),
                    cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2)
        cv2.putText(frame, f"Right: {score[1]}", (window_width - 200, 50),
                    cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2)

        if key == ord('p') or key == ord('P'):
            game_state = "PAUSED"

    elif game_state == "PAUSED":
        frame = show_pause_screen(frame)
        if key == ord('r') or key == ord('R'):
            game_state = "PLAYING"

    elif game_state == "GAMEOVER":
        frame = show_game_over_screen(frame, winner)
        # Restart Gesture Detection: require both hands detected for a set duration.
        if hand_pos["Left"] is not None and hand_pos["Right"] is not None:
            if restart_gesture_start_time is None:
                restart_gesture_start_time = current_time
            elif current_time - restart_gesture_start_time >= gesture_required_duration:
                score = [0, 0]
                ball_position = [window_width // 2, window_height // 2]
                ball_speed = [20, 20]
                game_state = "PLAYING"
                restart_gesture_start_time = None
        else:
            restart_gesture_start_time = None

    cv2.imshow("Game", frame)
    pygame.event.pump()

    if key == ord('q'):
        break

cap.release()
cv2.destroyAllWindows()
pygame.quit()
