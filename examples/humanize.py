import random
import time

###############################################################################

def pause(low=0.35, high=1.1):
    time.sleep(random.uniform(low, high))

###############################################################################

def _curve(x0, y0, x1, y1):
    steps = random.randint(18, 36)
    cx1 = x0 + (x1 - x0) * random.uniform(0.2, 0.45) + random.uniform(-50, 50)
    cy1 = y0 + (y1 - y0) * random.uniform(0.05, 0.4) + random.uniform(-40, 40)
    cx2 = x0 + (x1 - x0) * random.uniform(0.55, 0.85) + random.uniform(-40, 40)
    cy2 = y0 + (y1 - y0) * random.uniform(0.55, 0.95) + random.uniform(-30, 30)
    points = []
    for i in range(steps + 1):
        t = i / steps
        u = 1 - t
        x = (u ** 3) * x0 + 3 * (u ** 2) * t * cx1 + 3 * u * (t ** 2) * cx2 + (t ** 3) * x1
        y = (u ** 3) * y0 + 3 * (u ** 2) * t * cy1 + 3 * u * (t ** 2) * cy2 + (t ** 3) * y1
        if 0 < i < steps:
            x += random.uniform(-1.5, 1.5)
            y += random.uniform(-1.5, 1.5)
        points.append((x, y))
    return points

###############################################################################

def human_move(page, x, y):
    start_x = min(1400, max(8, x + random.uniform(-200, 200)))
    start_y = min(800, max(8, y + random.uniform(-140, 140)))
    for px, py in _curve(start_x, start_y, x, y):
        page.mouse.move(px, py)
        time.sleep(random.uniform(0.004, 0.014))

###############################################################################

def human_click(page, locator):
    box = locator.bounding_box()
    x = box["x"] + box["width"] * random.uniform(0.3, 0.7)
    y = box["y"] + box["height"] * random.uniform(0.35, 0.65)
    human_move(page, x, y)
    pause(0.08, 0.22)
    page.mouse.click(x, y)

###############################################################################

def human_type(page, text):
    for char in text:
        page.keyboard.type(char, delay=random.randint(55, 150))
        if char == " " and random.random() < 0.3:
            pause(0.1, 0.35)
