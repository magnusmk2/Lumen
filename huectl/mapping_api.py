"""UI mapping operations. API calls run off the GTK main loop."""
import threading
from . import mapping, capture
from .bridge import load_bridge
from .config import load_config


class MappingAPI:
    def __init__(self):
        self._lock = threading.RLock()
        self._cache = {}

    def _context(self, area, output, refresh=False):
        key = (area, output)
        with self._lock:
            if refresh or key not in self._cache:
                bridge = load_bridge()
                if bridge is None:
                    raise ValueError('Bridge not paired')
                self._cache[key] = mapping.discover(bridge, area)
            return self._cache[key]

    def get(self, area, output):
        topo = self._context(area, output, True)
        profile, revision = mapping.load_profile(load_config(), topo, output)
        problem = None
        try:
            rects, warnings = mapping.resolve(profile, topo)
        except (ValueError, KeyError, TypeError) as e:
            problem = str(e)
            rects, warnings = mapping.resolve(mapping.default_profile(topo), topo)
        if output == 'portal-selection':
            warnings.append('portal_selection')
        return {'topology': topo, 'profile': profile, 'revision': revision,
                'rectangles': rects, 'warnings': warnings, 'problem': problem,
                'capture_size': [capture.CAPTURE_W, capture.CAPTURE_H]}

    def preview(self, area, output, profile):
        topo = self._context(area, output)
        rects, warnings = mapping.resolve(profile, topo)
        if output == 'portal-selection':
            warnings.append('portal_selection')
        return {'rectangles': rects, 'warnings': warnings,
                'pixels': mapping.pixels(rects, capture.CAPTURE_W, capture.CAPTURE_H)}

    def save(self, area, output, profile, revision, worker):
        with self._lock:
            topo = self._context(area, output, True)
            # Serialize save against start/stop. No capture/network work under worker lock.
            with worker._lock:
                if worker._running and (worker._area != area or worker._output != output):
                    raise ValueError('Stop sync before editing another area or monitor')
                source = worker._source
                if worker._running and (source is None or source.topology is None):
                    raise ValueError('Wait for sync to finish starting')
                if source and source.topology and source.topology['signature'] != topo['signature']:
                    raise ValueError('Source layout changed; stop sync and review the mapping')
                rev = mapping.save_profile(topo, output, profile, revision)
                if source:
                    source.queue_mapping(profile, rev)
            return {'ok': True, 'revision': rev, 'applied': bool(source)}
