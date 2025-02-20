import cv2
import mediapipe as mp
import numpy as np
import random
import time

# Initialize MediaPipe Hands
mp_hands = mp.solutions.hands
hands = mp_hands.Hands(max_num_hands=1, min_detection_confidence=0.7)
mp_draw = mp.solutions.drawing_utils

# Load assets
car_img = cv2.imread('assets/car.png')  # Player's car
obstacle_img = cv2.imread('assets/obstacle.png')  # Opponent cars
background_img = cv2.imread('assets/road.png')  # Road background

# Resize assets
car_width, car_height = 60, 80
obstacle_width, obstacle_height = 60, 80
car_img = cv2.resize(car_img, (car_width, car_height))
obstacle_img = cv2.resize(obstacle_img, (obstacle_width, obstacle_height))
background_img = cv2.resize(background_img, (640, 480))  # Adjust size to fit window

# Game variables
lane_width = 100
base_speed = 5
score = 0
level = 1
misses = 0
max_misses = 5
obstacles = []
spawn_interval = 1.5
speed_increase_interval = 20  # Score to increase difficulty

# Initialize webcam
cap = cv2.VideoCapture(0)
cv2.namedWindow("Hand-Controlled Racing Game", cv2.WINDOW_NORMAL)

def create_obstacle(frame_width):
    x = random.randint(50, frame_width - obstacle_width - 50)
    return {'pos': [x, 0], 'speed': base_speed + (level * 0.5), 'active': True}

def reset_game():
    global score, misses, obstacles, level, spawn_interval
    score = 0
    misses = 0
    obstacles = []
    level = 1
    spawn_interval = 1.5

reset_game()
last_spawn_time = time.time()

while True:
    success, img = cap.read()
    if not success:
        continue

    img = cv2.flip(img, 1)
    h, w, _ = img.shape
    img = cv2.resize(img, (640, 480))
    img = cv2.addWeighted(img, 0.5, background_img, 0.5, 0)  # Overlay background

    rgb_img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
    results = hands.process(rgb_img)
    
    hand_x = w // 2
    if results.multi_hand_landmarks:
        for hand_landmark in results.multi_hand_landmarks:
            index_finger = hand_landmark.landmark[8]
            hand_x = int(index_finger.x * w)
            mp_draw.draw_landmarks(img, hand_landmark, mp_hands.HAND_CONNECTIONS)

    # Increase difficulty as score grows
    if score > level * speed_increase_interval:
        level += 1
        spawn_interval = max(0.5, spawn_interval * 0.9)  # Faster spawning

    # Spawn new obstacles
    if time.time() - last_spawn_time > spawn_interval:
        obstacles.append(create_obstacle(w))
        last_spawn_time = time.time()

    # Update obstacles
    active_obstacles = []
    for obs in obstacles:
        obs['pos'][1] += obs['speed']
        
        # Collision detection
        if h - car_height < obs['pos'][1] < h:
            if abs(obs['pos'][0] - hand_x) < car_width // 2:
                misses += 1
                obs['active'] = False
            else:
                score += 10
                obs['active'] = False
        
        if obs['pos'][1] > h:
            obs['active'] = False
        
        if obs['active']:
            active_obstacles.append(obs)
            img[obs['pos'][1]:obs['pos'][1]+obstacle_height, obs['pos'][0]:obs['pos'][0]+obstacle_width] = obstacle_img
    obstacles = active_obstacles

    # Draw car (controlled by hand position)
    img[h - car_height:h, hand_x - car_width // 2:hand_x + car_width // 2] = car_img

    # Game HUD
    cv2.putText(img, f"Score: {score}", (10, 30), 
                cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2)
    cv2.putText(img, f"Misses: {misses}/{max_misses}", (10, 60), 
                cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
    cv2.putText(img, f"Level: {level}", (w-150, 30), 
                cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 0), 2)

    # Game over condition
    if misses >= max_misses:
        cv2.putText(img, "GAME OVER! Press 'R' to restart", (50, h//2), 
                    cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 3)
    
    cv2.imshow("Hand-Controlled Racing Game", img)

    key = cv2.waitKey(1)
    if key == ord('q'):
        break
    elif key == ord('r'):
        reset_game()

cap.release()
cv2.destroyAllWindows()
