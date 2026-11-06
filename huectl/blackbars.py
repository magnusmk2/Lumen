"""Conservative, time-stabilized border detection on small raw RGB frames.

No screenshot storage, resampling or extra capture. Paired edge bars only:
ambiguous/dark frames retain the last accepted picture instead of pumping it.
"""
import math
import time


class BlackBarDetector:
    def __init__(self):
        self.reset()

    def reset(self):
        self._size = None
        self._crop = None
        self._candidate = None
        self._since = 0
        self._checked = -math.inf

    def process(self, buf, width, height, bpp, now=None):
        if type(width) is not int or type(height) is not int or min(width, height) < 1 or bpp not in (3, 4):
            raise ValueError('Invalid black-bar frame dimensions')
        if len(buf) != width * height * bpp:
            raise ValueError('Incomplete black-bar frame')
        now = time.monotonic() if now is None else now
        if self._size != (width, height, bpp):
            self.reset()
            self._size = (width, height, bpp)
            self._crop = (0, 0, width, height)
        if now - self._checked < .2:
            return self._crop
        self._checked = now
        candidate = self._detect(buf, width, height, bpp)
        if candidate is None:
            self._candidate = None
            return self._crop
        if candidate != self._candidate:
            self._candidate, self._since = candidate, now
        delay = .4 if candidate == (0, 0, width, height) else 1.0
        if now - self._since >= delay:
            self._crop = candidate
        return self._crop

    @staticmethod
    def _detect(buf, width, height, bpp):
        dark_rows = [0] * height
        dark_cols = [0] * width
        bright = 0
        # A channel maximum avoids misclassifying dark saturated blue as black.
        for y in range(height):
            for x in range(width):
                i = (y * width + x) * bpp
                v = max(buf[i], buf[i+1], buf[i+2])
                if v <= 12:
                    dark_rows[y] += 1
                    dark_cols[x] += 1
                if v >= 32:
                    bright += 1
        if bright < width * height * .12:
            return None

        def edge(values, extent):
            n = 0
            for count in values:
                if count < extent * .9:
                    break
                n += 1
            return n

        top, bottom = edge(dark_rows, width), edge(reversed(dark_rows), width)
        left, right = edge(dark_cols, height), edge(reversed(dark_cols), height)
        # Require balanced paired edges, not a dark object at just one edge.
        if abs(top-bottom) > 1 or abs(left-right) > 1:
            return None
        x, y = min(left, right), min(top, bottom)
        if x > width * .25 or y > height * .25:
            return None
        return (x, y, width-x, height-y)


def remap_regions(regions, width, height, crop, rectangles=None):
    """Map full-frame pixel geometry into the accepted content rectangle."""
    if crop == (0, 0, width, height):
        return regions
    left, top, right, bottom = crop
    w, h = right-left, bottom-top
    out = []
    if rectangles is not None:
        # Resolve normalized geometry directly in the content grid to avoid
        # rounding once in the full frame and again inside the crop.
        from .mapping import pixels
        return [(cid, (a+left, b+top, c+left, d+top))
                for cid, (a,b,c,d) in pixels(rectangles, w, h)]
    for cid, (x0, y0, x1, y1) in regions:
        a = min(right-1, left + round(x0 / width * w))
        b = min(bottom-1, top + round(y0 / height * h))
        c = min(right, left + round(x1 / width * w))
        d = min(bottom, top + round(y1 / height * h))
        out.append((cid, (a, b, max(a+1, c), max(b+1, d))))
    return out
