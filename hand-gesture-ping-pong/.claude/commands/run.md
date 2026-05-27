Launch the hand-gesture ping-pong game using the project venv.

Steps:
1. Run `venv\Scripts\python.exe main.py` from the project root (`C:\Users\tejas.marathe\Github Cloned Repos\AR-Games\hand-gesture-ping-pong`).
2. The game opens an OpenCV window titled "Hand Gesture Ping Pong". The webcam feed starts immediately with hand tracking active.
3. Watch for startup errors in the terminal (import failures, missing MediaPipe models, camera not found). Report any errors to the user.
4. If the game window appears, confirm it reached the START screen (arcade-style neon UI with "PRESS SPACE TO START" banner).
5. Do NOT attempt to interact with the game — it requires a physical webcam and hands. Just confirm it launched successfully and report what you see in the terminal output.

Note: The venv at `venv\Scripts\python.exe` has all dependencies (opencv-python, mediapipe, pygame, numpy). Do not use the system Python.
