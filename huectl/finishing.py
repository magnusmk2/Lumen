"""Best-effort, ownership-checked graceful-stop light behavior.

Hue has no compare-and-swap light writes: checks narrow races but cannot make
restoration atomic. Missing/changed ownership or ordinary state means no write.
"""
import copy
from . import entertainment


def light_ids(bridge, area):
    ids={r['rid'] for r in area.get('light_services',[]) if r.get('rtype')=='light'}
    if not ids:
        services={m['service']['rid'] for c in area.get('channels',[]) for m in c.get('members',[])}
        ids={s['renderer_reference']['rid'] for s in bridge.get('entertainment')
             if s['id'] in services and (s.get('renderer_reference') or {}).get('rtype')=='light'}
    return ids


def payload(light):
    result={}
    if 'on' in light:result['on']={'on':light['on']['on']}
    if light.get('dimming') is not None:
        result['dimming']={'brightness':light['dimming']['brightness']}
    gradient=light.get('gradient') or {}
    ct=light.get('color_temperature') or {}
    if gradient.get('points'):
        result['gradient']={'points':copy.deepcopy(gradient['points'])}
        if gradient.get('mode'):result['gradient']['mode']=gradient['mode']
    elif ct.get('mirek_valid') and ct.get('mirek') is not None:
        result['color_temperature']={'mirek':ct['mirek']}
    elif (light.get('color') or {}).get('xy'):
        result['color']={'xy':dict(light['color']['xy'])}
    effect=(light.get('effects') or {}).get('status')
    if effect and effect in (light.get('effects') or {}).get('effect_values',[]):
        result['effects']={'effect':effect}
    return result


def snapshot(bridge, ids):
    lights={l['id']:l for l in bridge.get('light')}
    if not ids or not ids<=lights.keys():
        raise ValueError('Entertainment light state is incomplete')
    states={rid:payload(lights[rid]) for rid in sorted(ids)}
    if any(not state for state in states.values()):
        raise ValueError('Entertainment light state cannot be restored')
    return states


def scene_allowed(scene, ids):
    targets=[a.get('target') or {} for a in scene.get('actions',[])]
    return bool(targets) and all(t.get('rtype')=='light' and t.get('rid') in ids for t in targets)


def owned(area, identity):
    owner=area.get('active_streamer') or {}
    return bool(identity) and area.get('status')=='active' and owner.get('rid')==identity and owner.get('rtype')=='auth_v1'


class FinishSession:
    def __init__(self, bridge, area, options, identity):
        if not identity:raise ValueError('Cannot confirm bridge ownership for stop behavior')
        self.bridge,self.area_id,self.options,self.identity=bridge,area['id'],options,identity
        self.ids=light_ids(bridge,area)
        self.saved=snapshot(bridge,self.ids)
        if options['stop_behavior']=='scene':self._scene()

    def _scene(self):
        scene=next((s for s in self.bridge.get('scene') if s['id']==self.options['stop_scene']),None)
        if not scene or not scene_allowed(scene,self.ids):
            raise ValueError('Stop scene must contain only lights in this Entertainment area')
        return scene

    def _idle(self):
        for area in self.bridge.get('entertainment_configuration'):
            if area.get('status')=='active' and light_ids(self.bridge,area)&self.ids:
                return False
        return True

    def before_release(self):
        return snapshot(self.bridge,self.ids)==self.saved

    def apply(self, unchanged, allowed=lambda: True):
        if not allowed():return {'status':'skipped','reason':'interrupted'}
        if not unchanged or not self._idle() or snapshot(self.bridge,self.ids)!=self.saved:
            return {'status':'skipped','reason':'changed'}
        if self.options['stop_behavior']=='scene':
            scene=self._scene()
            if not allowed():return {'status':'skipped','reason':'interrupted'}
            if not self._idle():return {'status':'skipped','reason':'ownership'}
            self.bridge.put('scene',scene['id'],{'recall':{'action':'active'}})
        else:
            # Recheck each target immediately before its write. Another
            # controller's edits to later lights abort the remaining writes.
            written=0
            for rid,state in self.saved.items():
                if not allowed():return {'status':'partial' if written else 'skipped','reason':'interrupted'}
                if not self._idle():return {'status':'partial' if written else 'skipped','reason':'ownership'}
                current=snapshot(self.bridge,self.ids)
                if current!=self.saved:return {'status':'partial' if written else 'skipped','reason':'changed'}
                try:self.bridge.put('light',rid,state)
                except Exception as e:
                    raise RuntimeError(f'Restore failed after {written} light request(s): {e}') from e
                written+=1
        return {'status':'applied','reason':self.options['stop_behavior']}
