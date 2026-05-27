Run a quick import smoke test to verify the game modules load without errors.

Run this command:
```
venv\Scripts\python.exe -c "import cv2, mediapipe, pygame, numpy; from game import config, state, engine, renderer, screens, handlers, hand_tracking, sound, effects, stats, utils; print('All imports OK')"
```

Report:
- "All imports OK" → everything is fine
- Any ImportError or ModuleNotFoundError → name the missing package and suggest `venv\Scripts\pip.exe install <package>`
- Any other error → show the full traceback

This does NOT start the game or open any window — it only checks that all dependencies and game modules are importable.
