import cv2
import mediapipe as mp
import pygame
import random

# Initialize MediaPipe Pose
mp_pose = mp.solutions.pose
pose = mp_pose.Pose()

# Initialize Pygame
pygame.init()

# Screen settings
WIDTH, HEIGHT = 640, 480
screen = pygame.display.set_mode((WIDTH, HEIGHT))
pygame.display.set_caption("AR Obstacle Avoidance")

# Colors
WHITE = (255, 255, 255)
GREEN = (0, 255, 0)
RED = (255, 0, 0)
BROWN = (139, 69, 19)  # Wood block color
GRAY = (169, 169, 169)  # Stone color
BLACK = (0, 0, 0)  # Wall color

# Player settings (AR Object)
player_size = 50
player_x = WIDTH // 2  # Start at center
player_y = HEIGHT - 100  # Near bottom
jump_threshold = 50  # Minimum jump height detection
jumping = False
gravity = 3
jump_force = -15
velocity_y = 0

# Obstacle settings
obstacle_width = 80
obstacle_height = 40
obstacle_x = random.choice([WIDTH // 4, WIDTH // 2, 3 * WIDTH // 4])  # Random left/middle/right
obstacle_y = 0  # Start from top
obstacle_speed = 5
obstacle_type = random.choice(["side", "full"])  # "side" for left/right, "full" for fullscreen jump
obstacle_appearance = random.choice(["wall", "stone", "wood"])  # Random obstacle structure

# Score
score = 0
previous_y = None  # To track head position for jump detection

# OpenCV Video Capture
cap = cv2.VideoCapture(0)

running = True
while running:
    ret, frame = cap.read()
    if not ret:
        break

    frame = cv2.flip(frame, 1)  # Mirror effect
    rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

    # Process with MediaPipe Pose
    results = pose.process(rgb_frame)

    # Detect head position
    head_x, head_y = None, None
    if results.pose_landmarks:
        head_x = results.pose_landmarks.landmark[mp_pose.PoseLandmark.NOSE].x * WIDTH
        head_y = results.pose_landmarks.landmark[mp_pose.PoseLandmark.NOSE].y * HEIGHT

    # Set initial previous_y
    if previous_y is None and head_y is not None:
        previous_y = head_y

    # Detect jump (if head moves up suddenly)
    if head_y and not jumping and head_y < previous_y - jump_threshold:
        jumping = True
        velocity_y = jump_force

    # Apply jump physics
    if jumping:
        player_y += velocity_y
        velocity_y += gravity
        if player_y >= HEIGHT - 100:  # Stop falling at ground level
            player_y = HEIGHT - 100
            jumping = False  # Reset jump

    # Move player left/right based on head movement
    if head_x:
        if head_x < WIDTH // 3:
            player_x -= 5  # Move left
        elif head_x > 2 * WIDTH // 3:
            player_x += 5  # Move right

    # Keep player inside screen
    player_x = max(0, min(WIDTH - player_size, player_x))

    # Move obstacle down
    obstacle_y += obstacle_speed

    # If obstacle reaches the bottom, reset it with a new type and appearance
    if obstacle_y > HEIGHT:
        obstacle_y = 0
        obstacle_x = random.choice([WIDTH // 4, WIDTH // 2, 3 * WIDTH // 4])
        obstacle_type = random.choice(["side", "full"])
        obstacle_appearance = random.choice(["wall", "stone", "wood"])

    # Convert OpenCV image to Pygame surface
    frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    frame = cv2.resize(frame, (WIDTH, HEIGHT))
    frame_surface = pygame.surfarray.make_surface(frame)
    frame_surface = pygame.transform.rotate(frame_surface, -90)
    frame_surface = pygame.transform.flip(frame_surface, True, False)

    # Pygame rendering
    screen.blit(frame_surface, (0, 0))  # Display live camera feed

    # Determine obstacle color based on type
    if obstacle_appearance == "wall":
        obstacle_color = BLACK
    elif obstacle_appearance == "stone":
        obstacle_color = GRAY
    else:
        obstacle_color = BROWN

    # Draw obstacles
    if obstacle_type == "side":
        pygame.draw.rect(screen, obstacle_color, (obstacle_x, obstacle_y, obstacle_width, obstacle_height))
    else:
        pygame.draw.rect(screen, obstacle_color, (0, obstacle_y, WIDTH, obstacle_height))  # Full-screen obstacle

    # Draw player
    pygame.draw.rect(screen, GREEN, (player_x, player_y, player_size, player_size))

    # Collision Detection
    if (
        obstacle_type == "side"
        and obstacle_y + obstacle_height >= player_y  # If obstacle reaches player
        and player_x < obstacle_x + obstacle_width
        and player_x + player_size > obstacle_x
    ):
        print(f"❌ Hit by {obstacle_appearance.upper()}! Game Over!")
        score = 0  # Reset score

    elif (
        obstacle_type == "full"
        and obstacle_y + obstacle_height >= player_y  # If full-screen obstacle reaches player
        and not jumping  # If player didn't jump in time
    ):
        print(f"❌ Hit by {obstacle_appearance.upper()}! Game Over!")
        score = 0  # Reset score

    # Display Score
    font = pygame.font.Font(None, 36)
    score_text = font.render(f"Score: {score}", True, (0, 255, 0))
    screen.blit(score_text, (10, 10))

    # Event Handling
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            running = False

    pygame.display.flip()

# Cleanup
cap.release()
cv2.destroyAllWindows()
pygame.quit()
