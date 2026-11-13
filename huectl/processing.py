"""Validated colour settings and time-based smoothing, shared by GUI and CLI."""
import math
import time
from .capture import punch

DEFAULTS = {'saturation': 1.6, 'brightness': 1.0, 'gamma': 1.0, 'response_ms': 0.0}
LIMITS = {'saturation': (0, 4), 'brightness': (0, 1), 'gamma': (.1, 5), 'response_ms': (0, 2000)}


def validate(patch, base=None):
    if not isinstance(patch, dict) or set(patch) - set(DEFAULTS):
        raise ValueError('Invalid colour settings')
    options = dict(DEFAULTS if base is None else base)
    options.update(patch)
    for name, (lo, hi) in LIMITS.items():
        value = options.get(name)
        if type(value) not in (int, float) or not math.isfinite(value) or not lo <= value <= hi:
            raise ValueError(f'{name} must be between {lo} and {hi}')
    return options


def from_config(cfg):
    return validate({k: cfg.get('sync_'+k, v) for k, v in DEFAULTS.items()})


def config_patch(options):
    return {'sync_'+k: v for k, v in validate(options).items()}


class ColorProcessor:
    """Response is an exponential time constant in milliseconds (63% at tau).

    Retain float history, round only outgoing bytes. Identity settings preserve
    the existing punch result exactly; first sample and setting changes snap to
    target so old parameters/streams cannot bleed into a new session.
    """
    def __init__(self, options=None):
        self.options = validate({} if options is None else options)
        self.reset()

    def reset(self):
        self._colors = None
        self._time = None

    def configure(self, options):
        options = validate(options)
        if options != self.options:
            self.options = options
            self.reset()

    def process(self, colors, now=None):
        now = time.monotonic() if now is None else now
        o = self.options
        targets = [tuple(c * o['brightness'] for c in punch(rgb, o['saturation'], o['gamma'])) for rgb in colors]
        if not o['response_ms'] or self._colors is None or len(targets) != len(self._colors):
            self._colors = targets
        else:
            elapsed = max(0, now-self._time)
            alpha = -math.expm1(-elapsed / (o['response_ms']/1000))
            self._colors = [tuple(old+(new-old)*alpha for old,new in zip(previous,target))
                            for previous,target in zip(self._colors,targets)]
        self._time = now
        return [tuple(max(0,min(255,round(c))) for c in rgb) for rgb in self._colors]
