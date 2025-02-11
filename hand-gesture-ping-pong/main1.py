# main1.py
import cv2
import numpy as np
import pygame
import time

# ----- Initialize Pygame for sound -----
pygame.init()
pygame.mixer.init()
hit_sound = pygame.mixer.Sound("hit.wav")
lose_sound = pygame.mixer.Sound("lose.mp3")
hit_sound.set_volume(1.0)
lose_sound.set_volume(1.0)

# ----- Game Parameters -----
window_width, window_height = 800, 600
ball_radius = 10
ball_speed = [4, 2]
ball_position = [320, 240]
default_ball_color = (0, 0, 255)  # Blue normally
hit_flash_color = (0, 255, 255)     # Yellow flash on hit

rod_height = 100
rod_width = 20
left_rod_x = 20
right_rod_x = window_width - 40

score = [0, 0]  # [left, right]
high_score = 0

game_state = "START"
hit_animation_time = 0
hit_flash_duration = 0.2

cap = cv2.VideoCapture(0)
cap.set(cv2.CAP_PROP_FRAME_WIDTH, window_width)
cap.set(cv2.CAP_PROP_FRAME_HEIGHT, window_height)

last_time = time.time()

def show_start_screen(frame):
    cv2.putText(frame, "Welcome to Standard Pong!", (window_width//4, window_height//3),
                cv2.FONT_HERSHEY_SIMPLEX, 1, (255,255,255), 2)
    cv2.putText(frame, "Press 'S' to Start", (window_width//4, window_height//2),
                cv2.FONT_HERSHEY_SIMPLEX, 1, (255,255,0), 2)
    cv2.putText(frame, "High Score: {}".format(high_score), (window_width//4, window_height//2 + 50),
                cv2.FONT_HERSHEY_SIMPLEX, 1, (0,255,255), 2)
    return frame

def show_pause_screen(frame):
    cv2.putText(frame, "Game Paused", (window_width//3, window_height//2),
                cv2.FONT_HERSHEY_SIMPLEX, 1, (0,0,255), 2)
    cv2.putText(frame, "Press 'R' to Resume", (window_width//3, window_height//2 + 50),
                cv2.FONT_HERSHEY_SIMPLEX, 1, (0,0,255), 2)
    return frame

def show_game_over_screen(frame, winner):
    cv2.putText(frame, "Game Over!", (window_width//3, window_height//3),
                cv2.FONT_HERSHEY_SIMPLEX, 1, (0,0,255), 2)
    cv2.putText(frame, "{} Wins!".format(winner), (window_width//3, window_height//3 + 50),
                cv2.FONT_HERSHEY_SIMPLEX, 1, (0,0,255), 2)
    cv2.putText(frame, "Score: Left {}  Right {}".format(score[0], score[1]),
                (window_width//3, window_height//3 + 100), cv2.FONT_HERSHEY_SIMPLEX, 1, (255,255,0), 2)
    cv2.putText(frame, "High Score: {}".format(high_score),
                (window_width//3, window_height//3 + 150), cv2.FONT_HERSHEY_SIMPLEX, 1, (0,255,255), 2)
    cv2.putText(frame, "Press 'S' to Restart", (window_width//3, window_height//3 + 200),
                cv2.FONT_HERSHEY_SIMPLEX, 1, (255,255,255), 2)
    return frame

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

    # For this version, rod positions remain fixed (centered vertically)
    left_rod_y = window_height//2 - rod_height//2
    right_rod_y = window_height//2 - rod_height//2

    if game_state == "START":
        frame = show_start_screen(frame)
        if key == ord('s') or key == ord('S'):
            score = [0, 0]
            ball_position = [window_width//2, window_height//2]
            ball_speed = [4, 2]
            game_state = "PLAYING"

    elif game_state == "PLAYING":
        ball_position[0] += ball_speed[0]
        ball_position[1] += ball_speed[1]

        if ball_position[1] <= ball_radius or ball_position[1] >= window_height - ball_radius:
            ball_speed[1] = -ball_speed[1]

        if (ball_position[0] - ball_radius <= left_rod_x + rod_width and
            left_rod_y <= ball_position[1] <= left_rod_y + rod_height):
            ball_speed[0] = -ball_speed[0]
            hit_sound.play()
            hit_animation_time = current_time
        elif ball_position[0] - ball_radius <= 0:
            score[1] += 1
            lose_sound.play()
            game_state = "GAMEOVER"
            winner = "Right"
            if max(score) > high_score:
                high_score = max(score)

        if (ball_position[0] + ball_radius >= right_rod_x - rod_width and
            right_rod_y <= ball_position[1] <= right_rod_y + rod_height):
            ball_speed[0] = -ball_speed[0]
            hit_sound.play()
            hit_animation_time = current_time
        elif ball_position[0] + ball_radius >= window_width:
            score[0] += 1
            lose_sound.play()
            game_state = "GAMEOVER"
            winner = "Left"
            if max(score) > high_score:
                high_score = max(score)

        if current_time - hit_animation_time < hit_flash_duration:
            current_ball_color = hit_flash_color
        else:
            current_ball_color = default_ball_color

        cv2.circle(frame, tuple(ball_position), ball_radius, current_ball_color, -1)
        cv2.rectangle(frame, (left_rod_x, left_rod_y),
                      (left_rod_x + rod_width, left_rod_y + rod_height), (255, 0, 0), -1)
        cv2.rectangle(frame, (right_rod_x - rod_width, right_rod_y),
                      (right_rod_x, right_rod_y + rod_height), (0, 0, 255), -1)

        cv2.putText(frame, f"Left: {score[0]}", (50, 50),
                    cv2.FONT_HERSHEY_SIMPLEX, 1, (255,255,255), 2)
        cv2.putText(frame, f"Right: {score[1]}", (window_width - 200, 50),
                    cv2.FONT_HERSHEY_SIMPLEX, 1, (255,255,255), 2)

        if key == ord('p') or key == ord('P'):
            game_state = "PAUSED"

    elif game_state == "PAUSED":
        frame = show_pause_screen(frame)
        if key == ord('r') or key == ord('R'):
            game_state = "PLAYING"

    elif game_state == "GAMEOVER":
        frame = show_game_over_screen(frame, winner)
        if key == ord('s') or key == ord('S'):
            score = [0, 0]
            ball_position = [window_width//2, window_height//2]
            ball_speed = [4, 2]
            game_state = "PLAYING"

    cv2.imshow("Game", frame)
    pygame.event.pump()

    if key == ord('q'):
        break

cap.release()
cv2.destroyAllWindows()
pygame.quit()
