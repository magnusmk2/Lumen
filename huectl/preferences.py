"""Validated capture and finishing preferences; existing behavior is default."""
QUALITY = {'economy': (32,18), 'balanced': (64,36), 'detailed': (128,72)}
DEFAULTS = {'quality':'balanced','stop_behavior':'leave','stop_scene':None,'portal_remember':False,'start_on_launch':False,'quit_lights_off':False}


def validate(patch, base=None):
    if not isinstance(patch,dict) or set(patch)-set(DEFAULTS):
        raise ValueError('Invalid capture/finishing settings')
    result=dict(DEFAULTS if base is None else base);result.update(patch)
    if not isinstance(result['quality'],str) or not isinstance(result['stop_behavior'],str) or result['quality'] not in QUALITY or result['stop_behavior'] not in ('leave','restore','scene'):
        raise ValueError('Invalid quality or stop behavior')
    if any(type(result[key]) is not bool for key in ('portal_remember','start_on_launch','quit_lights_off')):
        raise ValueError('Invalid portal preference')
    scene=result['stop_scene']
    if scene is not None and (not isinstance(scene,str) or not scene or len(scene)>128):
        raise ValueError('Invalid stop scene')
    if result['stop_behavior']=='scene' and not scene:
        raise ValueError('Choose a scene before enabling scene-on-stop')
    return result


def from_config(cfg):
    return validate({k:cfg.get('sync_'+k,v) for k,v in DEFAULTS.items()})


def config_patch(options):
    return {'sync_'+k:v for k,v in validate(options).items()}
