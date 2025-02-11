# Hand-Controlled Pong

Hand-Controlled Pong is a Python-based game that uses OpenCV for real-time video processing, Mediapipe for hand tracking, and pygame for audio feedback. In this game, players control the paddles using hand gestures. Points are scored when a player's paddle successfully hits the ball, and the game features multiple states (start, playing, paused, game over) with gesture-based controls for starting and restarting.

## Features

- **Hand Tracking:** Control paddles using Mediapipe to detect your hand positions.
- **Real-Time Video Processing:** Uses OpenCV to capture and process video from your webcam.
- **Audio Feedback:** Plays sounds for ball hits and game over using pygame.
- **Game State Management:** Includes start screen, pause/resume functionality, and a game-over screen.
- **Gesture-Based Controls:** Wave both hands for 1 second to start or restart the game.
- **Score Logic:** Points are awarded to a player each time their paddle hits the ball.

## Requirements

- Python 3.x
- [opencv-python](https://pypi.org/project/opencv-python/)
- [mediapipe](https://pypi.org/project/mediapipe/)
- [pygame](https://pypi.org/project/pygame/)
- [numpy](https://pypi.org/project/numpy/)

## Installation

1. **Clone the Repository:**

   ```bash
   git clone https://github.com/visionx-gaming/AR-Games.git
   cd hand-gesture-ping-pong

2. **Install requirements.txt**

    ```bash
    pip install -r requirements.txt

3. **run game**

    ```bash
    python main.py
