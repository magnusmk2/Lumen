"""Dependency-free source topology, validated normalized regions and persistence."""
import hashlib
import json
import math

VERSION = 1


def _union(intervals):
    out = []
    for lo, hi in sorted(set(map(tuple, intervals))):
        if out and lo <= out[-1][1]:
            out[-1][1] = max(out[-1][1], hi)
        else:
            out.append([lo, hi])
    return out


def discover(bridge, area_id=None, cancelled=None):
    """Read capabilities once, outside the frame loop. Never expose credentials."""
    def read(kind):
        if cancelled and cancelled():
            raise ValueError('Discovery cancelled')
        return bridge.get(kind)
    areas = read('entertainment_configuration')
    area = next((a for a in areas if a['id'] == area_id), None) if area_id else next(iter(areas), None)
    if not area or not area.get('channels'):
        raise ValueError('No Entertainment area with channels')
    services = {s['id']: s for s in read('entertainment')}
    devices = {d['id']: d for d in read('device')}
    lights = {l['id']: l for l in read('light')}
    bridge_id = next((b['bridge_id'] for b in read('bridge') if b.get('bridge_id')), None)
    if not bridge_id:
        raise ValueError('Bridge identity unavailable')
    channels, groups, signature = [], {}, []
    for raw in sorted(area['channels'], key=lambda c: c['channel_id']):
        cid = raw['channel_id']
        if type(cid) is not int or not 0 <= cid <= 255:
            raise ValueError('Invalid Entertainment channel ID')
        members = raw.get('members', [])
        sids = sorted(set(m['service']['rid'] for m in members))
        if not sids:
            raise ValueError('Channel has no source members')
        pos = raw.get('position', {})
        ch = {'id': cid, 'position': pos, 'sources': sids, 'intervals': [],
              'coverage': None, 'warnings': []}
        sigmembers, names = [], []
        for sid in sids:
            service = services.get(sid, {})
            device = devices.get(service.get('owner', {}).get('rid'), {})
            light = lights.get(service.get('renderer_reference', {}).get('rid'), {})
            table = service.get('segments', {}).get('segments', [])
            pixels = light.get('gradient', {}).get('pixel_count')
            names.append(device.get('metadata', {}).get('name', 'Unknown source'))
            g = groups.setdefault(sid, {'id': sid, 'name': names[-1],
                'device_id': device.get('id'), 'channels': [], 'segments': len(table),
                'pixels': pixels, 'palette_points': light.get('gradient', {}).get('points_capable'),
                'coverage_available': False})
            g['channels'].append(cid)
            indices = [m.get('index') for m in members if m['service']['rid'] == sid]
            intervals = []
            for index in indices:
                if type(index) is not int or not 0 <= index < len(table):
                    ch['warnings'].append('segment_reference')
                    continue
                seg = table[index]
                lo, size = seg.get('start'), seg.get('length')
                if type(lo) is not int or type(size) is not int or lo < 0 or size <= 0:
                    ch['warnings'].append('segment_bounds')
                    continue
                intervals.append([lo, lo + size])
            ordered_intervals = sorted(intervals)
            if any(a[1] > b[0] for a, b in zip(ordered_intervals, ordered_intervals[1:])):
                ch['warnings'].append('segment_overlap')
            merged = _union(intervals)
            if len(sids) == 1:
                ch['intervals'] = merged
            sigmembers.append([sid, indices, table, pixels, device.get('id')])
        if len(sids) != 1:
            ch['warnings'].append('shared_channel')
        ch['name'] = ' / '.join(dict.fromkeys(names))
        channels.append(ch)
        signature.append([cid, pos, sigmembers])
    if len({c['id'] for c in channels}) != len(channels):
        raise ValueError('Duplicate Entertainment channel ID')
    for sid, g in groups.items():
        cs = [c for c in channels if c['sources'] == [sid]]
        spans = [c['intervals'][0] for c in cs if len(c['intervals']) == 1]
        ordered = sorted(spans)
        extent = max((hi for _, hi in spans), default=0)
        complete = (len(cs) == len(g['channels']) == len(spans)
            and not any(c['warnings'] for c in cs) and ordered and ordered[0][0] == 0
            and all(a[1] == b[0] for a, b in zip(ordered, ordered[1:]))
            and (g['pixels'] is None or g['pixels'] == extent))
        g['coverage_available'] = bool(complete)
        if complete:
            for c in cs:
                lo, hi = c['intervals'][0]
                c['coverage'] = [lo / extent, hi / extent]
        g['order'] = [c['id'] for c in sorted(
            [c for c in channels if c['id'] in g['channels']],
            key=lambda c: (c['position'].get('x', 0), c['id']))]
        xs = [c['position'].get('x', 0) for c in cs]
        g['ambiguous_order'] = len(xs) != len(set(xs))
    digest = hashlib.sha256(json.dumps([signature, area.get('locations')],
        sort_keys=True, separators=(',', ':')).encode()).hexdigest()
    return {'bridge_id': bridge_id, 'area_id': area['id'],
        'name': area.get('metadata', {}).get('name', '?'), 'channels': channels,
        'devices': list(groups.values()), 'signature': digest}


def legacy_regions(topology):
    return {str(c['id']): [max(0, (c['position'].get('x', 0)+1)/2-.2), 0,
        min(1, (c['position'].get('x', 0)+1)/2+.2), 1] for c in topology['channels']}


def default_profile(topology):
    return {'version': VERSION, 'signature': topology['signature'], 'mode': 'legacy',
        'height': .2, 'inset': 0, 'devices': {}, 'overrides': {}}


def _number(v):
    return type(v) in (int, float) and math.isfinite(v)


def validate(profile, topology):
    """Reject invalid settings instead of silently discarding manual calibration."""
    if not isinstance(profile, dict) or type(profile.get('version')) is not int or profile['version'] != VERSION:
        raise ValueError('Unsupported mapping version')
    if profile.get('signature') != topology['signature']:
        raise ValueError('Source layout changed; review and rebind the mapping')
    if profile.get('mode') not in ('legacy', 'desk'):
        raise ValueError('Invalid mapping preset')
    height, inset = profile.get('height'), profile.get('inset')
    if not all(_number(v) for v in (height, inset)) or not (
        .05 <= height <= 1 and 0 <= inset and height + inset <= 1 + 1e-9):
        raise ValueError('Band height plus inset must fit the screen')
    ids = {str(c['id']) for c in topology['channels']}
    overrides, devs = profile.get('overrides'), profile.get('devices')
    if not isinstance(overrides, dict) or not isinstance(devs, dict):
        raise ValueError('Invalid mapping settings')
    if set(overrides) - ids:
        raise ValueError('Unknown channel in mapping')
    for rect in overrides.values():
        if not isinstance(rect, list) or len(rect) != 4 or not all(_number(x) for x in rect):
            raise ValueError('Invalid channel rectangle')
        x0,y0,x1,y1 = rect
        if not (0 <= x0 < x1 <= 1 and 0 <= y0 < y1 <= 1):
            raise ValueError('Channel rectangle must fit the screen')
    known = {g['id']: g for g in topology['devices']}
    if set(devs) - set(known):
        raise ValueError('Unknown source in mapping')
    for sid, d in devs.items():
        if not isinstance(d, dict) or d.get('strategy') not in ('coverage', 'equal'):
            raise ValueError('Invalid region width strategy')
        if d.get('mode', 'inherit') not in ('inherit', 'legacy', 'desk'):
            raise ValueError('Invalid device layout')
        order = d.get('order')
        if not isinstance(order, list) or any(type(c) is not int for c in order) or sorted(order) != sorted(known[sid]['channels']):
            raise ValueError('Channel order must contain each source channel once')
        if type(d.get('reverse', False)) is not bool:
            raise ValueError('Invalid direction')
        lo,hi = d.get('start', 0),d.get('end', 1)
        if not (_number(lo) and _number(hi) and 0 <= lo < hi <= 1):
            raise ValueError('Source range must fit the screen')
    return json.loads(json.dumps(profile, allow_nan=False))


def resolve(profile, topology):
    profile = validate(profile, topology)
    rects = legacy_regions(topology)
    warnings = sorted({w for c in topology['channels'] for w in c['warnings']})
    assigned = set()
    for g in topology['devices']:
        d = profile['devices'].get(g['id'], {})
        mode = d.get('mode', 'inherit')
        if (profile['mode'] if mode == 'inherit' else mode) != 'desk':
            continue
        order = list(d.get('order', g['order']))
        if d.get('reverse'):
            order.reverse()
        strategy = d.get('strategy', 'coverage' if g['coverage_available'] else 'equal')
        if strategy == 'coverage' and not g['coverage_available']:
            warnings.append('coverage_unavailable')
            strategy = 'equal'
        if g['ambiguous_order']:
            warnings.append('ambiguous_order')
        lo,hi = d.get('start', 0), d.get('end', 1)
        byid = {c['id']:c for c in topology['channels']}
        weights = [(byid[c]['coverage'][1]-byid[c]['coverage'][0])
            if strategy == 'coverage' else 1 for c in order]
        total, cursor = sum(weights), lo
        for i,(cid,weight) in enumerate(zip(order,weights)):
            end = hi if i == len(order)-1 else cursor + (hi-lo)*weight/total
            if len(byid[cid]['sources']) > 1 and str(cid) not in profile['overrides']:
                raise ValueError('Shared channels need an explicit manual rectangle')
            rects[str(cid)] = [cursor, max(0,1-profile['inset']-profile['height']), end,1-profile['inset']]
            assigned.add(cid)
            cursor = end
    rects.update(profile['overrides'])
    return rects, sorted(set(warnings))


def pixels(rectangles, width, height):
    if type(width) is not int or type(height) is not int or min(width,height) < 1:
        raise ValueError('Invalid capture dimensions')
    out=[]
    for cid,(x0,y0,x1,y1) in sorted(rectangles.items(),key=lambda p:int(p[0])):
        a,b=min(width-1,round(x0*width)),min(height-1,round(y0*height))
        c,d=min(width,round(x1*width)),min(height,round(y1*height))
        out.append((int(cid),(a,b,max(a+1,c),max(b+1,d))))
    return out


def profile_key(topology, output):
    if not output:
        raise ValueError('Select a concrete monitor for saved mapping')
    return json.dumps([topology['bridge_id'],topology['area_id'],output],separators=(',',':'))


def load_profile(cfg, topology, output):
    profiles=cfg.get('sync_mapping',{})
    if not isinstance(profiles,dict):
        raise ValueError('Invalid saved mapping collection')
    item=profiles.get(profile_key(topology,output))
    if item is None:
        return default_profile(topology),0
    if not isinstance(item,dict):
        raise ValueError('Invalid saved mapping')
    if not isinstance(item.get('profile'),dict) or type(item.get('revision')) is not int or item['revision'] < 0:
        raise ValueError('Invalid saved mapping entry; restore or remove this profile')
    return item['profile'],item['revision']


def save_profile(topology, output, profile, revision):
    from .config import update_config
    profile=validate(profile,topology)
    resolve(profile,topology)
    key=profile_key(topology,output)
    if type(revision) is not int or revision < 0:
        raise ValueError('Invalid mapping revision')
    def update(cfg):
        _,current=load_profile(cfg,topology,output)
        if revision != current:
            raise ValueError('Settings changed; reload this mapping')
        cfg.setdefault('sync_mapping',{})[key]={'revision':current+1,'profile':profile}
        cfg['sync_area_id']=topology['area_id']
        return current+1
    return update_config(update)
