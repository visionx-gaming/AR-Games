"""Platform-aware key codes for cv2.waitKeyEx.

Arrow keys come back as large "extended" codes whose values differ per OS
(and per OpenCV GUI backend), so they are defined here instead of as magic
numbers scattered through the handlers.
"""

import sys

if sys.platform == "win32":
    UP, DOWN, LEFT, RIGHT = 2490368, 2621440, 2424832, 2555904
elif sys.platform == "darwin":
    UP, DOWN, LEFT, RIGHT = 63232, 63233, 63234, 63235
else:                                   # Linux / GTK
    UP, DOWN, LEFT, RIGHT = 65362, 65364, 65361, 65363

NO_KEY = 255

