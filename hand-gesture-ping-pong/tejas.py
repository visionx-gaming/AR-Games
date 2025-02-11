import cv2
import mediapipe as mp
import numpy as np
import random
import time

# Initialize MediaPipe Hands
mp_hands = mp.solutions.hands
hands = mp_hands.Hands(max_num_hands=1, min_detection_confidence=0.7)
mp_draw = mp.solutions.drawing_utils

# Game variables
bubble_size = 30
base_speed = 3
score = 0
missed_bubbles = 0
max_misses = 15
bubbles = []
basket_width = 100
basket_height = 20
level = 1
spawn_interval = 0.5  # Initial bubble spawn interval
speed_increase_interval = 30  # Points needed to increase difficulty

# Initialize webcam
cap = cv2.VideoCapture(0)
cv2.namedWindow("Bubble Catching Game", cv2.WINDOW_NORMAL)

def create_bubble(frame_width):
    x = random.randint(bubble_size, frame_width - bubble_size)
    return {'pos': [x, 0], 'active': True, 'speed': base_speed + (level * 0.3)}

def reset_game():
    global score, missed_bubbles, bubbles, level, spawn_interval
    score = 0
    missed_bubbles = 0
    bubbles = []
    level = 1
    spawn_interval = 0.5

reset_game()
last_bubble_time = time.time()
performance_history = []

while True:
    success, img = cap.read()
    if not success:
        continue

    img = cv2.flip(img, 1)
    h, w, _ = img.shape
    rgb_img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
    results = hands.process(rgb_img)
    
    hand_x = None
    if results.multi_hand_landmarks:
        for hand_landmark in results.multi_hand_landmarks:
            index_finger = hand_landmark.landmark[8]
            hand_x = int(index_finger.x * w)
            mp_draw.draw_landmarks(img, hand_landmark, mp_hands.HAND_CONNECTIONS)

    # Dynamic difficulty adjustment
    if score > level * speed_increase_interval:
        level += 1
        spawn_interval = max(0.2, spawn_interval * 0.9)  # Faster spawning
        performance_history.clear()

    # Create new bubbles with dynamic intervals
    if time.time() - last_bubble_time > spawn_interval:
        bubbles.append(create_bubble(w))
        last_bubble_time = time.time()

    # Track active bubbles
    active_bubbles = [b for b in bubbles if b['active']]
    bubbles = active_bubbles  # Remove inactive bubbles

    # Update bubble positions
    for bubble in bubbles:
        bubble['pos'][1] += bubble['speed']
        
        # Catch detection
        if hand_x and (bubble['pos'][1] + bubble_size > h - basket_height):
            if (bubble['pos'][0] > hand_x - basket_width//2 and 
                bubble['pos'][0] < hand_x + basket_width//2):
                score += 10
                bubble['active'] = False
                performance_history.append(1)  # Track successes
        
        # Miss detection
        if bubble['pos'][1] > h:
            missed_bubbles += 1
            bubble['active'] = False
            performance_history.append(0)  # Track misses
        
        # Draw active bubbles
        if bubble['active']:
            # Fix: Ensure center coordinates are integers
            cv2.circle(img, (int(bubble['pos'][0]), int(bubble['pos'][1])), bubble_size, (255, 0, 255), -1)

    # Adaptive difficulty based on performance (last 10 catches)
    recent_performance = performance_history[-10:]
    if len(recent_performance) > 5:
        success_rate = sum(recent_performance)/len(recent_performance)
        # Auto-adjust speed based on player skill
        if success_rate > 0.7:  # Player is doing well
            base_speed = min(8, base_speed + 0.1)
        elif success_rate < 0.3:  # Player struggling
            base_speed = max(3, base_speed - 0.1)

    # Draw basket
    if hand_x:
        cv2.rectangle(img, 
                     (hand_x - basket_width//2, h - basket_height),
                     (hand_x + basket_width//2, h), 
                     (0, 255, 0), -1)

    # Game HUD
    cv2.putText(img, f"Score: {score}", (10, 30), 
               cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2)
    cv2.putText(img, f"Missed: {missed_bubbles}/{max_misses}", (10, 60), 
               cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
    cv2.putText(img, f"Level: {level}", (w-150, 30), 
               cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 0), 2)

    # Game over check
    if missed_bubbles >= max_misses:
        cv2.putText(img, "GAME OVER! Press 'R' to restart", (50, h//2), 
                   cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 3)

    cv2.imshow("Bubble Catching Game", img)

    key = cv2.waitKey(1)
    if key == ord('q'):
        break
    elif key == ord('r'):
        reset_game()

cap.release()
cv2.destroyAllWindows()

#