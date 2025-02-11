import cv2
import mediapipe as mp
import random
import time

# Initialize MediaPipe Hands
mp_hands = mp.solutions.hands
hands = mp_hands.Hands(max_num_hands=1, min_detection_confidence=0.7)
mp_draw = mp.solutions.drawing_utils

# Game variables
base_bubble_size = 30
base_bubble_speed = 3
score = 0
bubbles = []
base_basket_width = 120
basket_height = 25
last_bubble_time = time.time()

# Initialize webcam
cap = cv2.VideoCapture(0)
cv2.namedWindow("Bubble Catching Game+", cv2.WINDOW_NORMAL)

def create_bubble(frame_width, level):
    size = max(15, base_bubble_size - (level // 2))
    x = random.randint(size, frame_width - size)
    color = (255, 0, 255)  # Default pink
    if level >= 6:
        color = (0, 0, 255)  # Red
    elif level >= 3:
        color = (0, 255, 0)  # Green
    return {'pos': [x, 0], 'active': True, 'size': size, 'color': color}

def reset_game():
    global score, bubbles
    score = 0
    bubbles = []

reset_game()

while True:
    success, img = cap.read()
    if not success:
        continue

    img = cv2.flip(img, 1)
    h, w, _ = img.shape
    rgb_img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
    results = hands.process(rgb_img)
    
    # Calculate difficulty level based on score
    current_level = score // 50
    bubble_speed = base_bubble_speed + current_level * 0.7
    spawn_interval = max(0.1, 0.5 - current_level * 0.03)
    max_bubbles = 10 + current_level * 3
    basket_width = max(40, base_basket_width - current_level * 8)
    
    hand_x = None
    if results.multi_hand_landmarks:
        for hand_landmark in results.multi_hand_landmarks:
            index_finger = hand_landmark.landmark[8]
            hand_x = int(index_finger.x * w)
            mp_draw.draw_landmarks(img, hand_landmark, mp_hands.HAND_CONNECTIONS)

    # Create new bubbles
    if time.time() - last_bubble_time > spawn_interval and len(bubbles) < max_bubbles:
        bubbles.append(create_bubble(w, current_level))
        last_bubble_time = time.time()

    # Update bubble positions
    bubbles_to_remove = []
    for bubble in bubbles:
        if bubble['active']:
            bubble['pos'][1] += bubble_speed
            
            # Check collision with basket
            if hand_x and (bubble['pos'][1] + bubble['size'] > h - basket_height):
                basket_left = hand_x - basket_width//2
                basket_right = hand_x + basket_width//2
                if basket_left < bubble['pos'][0] < basket_right:
                    score += 10 + current_level  # Bonus points at higher levels
                    bubble['active'] = False
                    
            # Draw bubble
            if bubble['active']:
                cv2.circle(img, tuple(bubble['pos']), bubble['size'], bubble['color'], -1)
                cv2.circle(img, tuple(bubble['pos']), bubble['size'], (255, 255, 255), 2)
                
            # Check if missed
            if bubble['pos'][1] - bubble['size'] > h:
                score = max(0, score - (5 + current_level))  # Increasing penalty
                bubbles_to_remove.append(bubble)

    # Remove missed bubbles
    for bubble in bubbles_to_remove:
        bubbles.remove(bubble)

    # Draw basket
    if hand_x:
        basket_top = h - basket_height
        cv2.rectangle(img, 
                     (hand_x - basket_width//2, basket_top),
                     (hand_x + basket_width//2, h), 
                     (0, 255, 0), -1)
        # Basket outline
        cv2.rectangle(img, 
                     (hand_x - basket_width//2, basket_top),
                     (hand_x + basket_width//2, h), 
                     (50, 50, 50), 2)

    # Display game info
    cv2.putText(img, f"Score: {score}", (10, 30), 
               cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2)
    cv2.putText(img, f"Level: {current_level}", (w - 150, 30), 
               cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 0), 2)
    cv2.putText(img, f"Speed: x{bubble_speed:.1f}", (10, 65), 
               cv2.FONT_HERSHEY_SIMPLEX, 0.6, (200, 200, 255), 1)
    cv2.putText(img, f"Basket: {basket_width}px", (w - 150, 65), 
               cv2.FONT_HERSHEY_SIMPLEX, 0.6, (200, 255, 200), 1)

    cv2.imshow("Bubble Catching Game+", img)

    key = cv2.waitKey(1)
    if key == ord('q'):
        break
    elif key == ord('r'):
        reset_game()

cap.release()
cv2.destroyAllWindows()