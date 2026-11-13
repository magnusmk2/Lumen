import copy
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch,Mock
from huectl import finishing, preferences, config, sync, capture
from test_mapping import FakeBridge


class Bridge(FakeBridge):
    def __init__(self):
        super().__init__()
        self.data['light'][0].update(on={'on':True},dimming={'brightness':40},color={'xy':{'x':.3,'y':.4}})
        self.data['entertainment_configuration'][0].update(status='inactive',light_services=[{'rid':'light','rtype':'light'}])
        self.data['scene']=[{'id':'scene','actions':[{'target':{'rid':'light','rtype':'light'},'action':{'on':{'on':True}}}]}]
        self.writes=[];self.fail_light=False;self.fail_state_reads=False
    def get(self,kind):
        if kind=='light' and self.fail_state_reads:raise OSError('read unavailable')
        return super().get(kind)
    def application_id(self):return 'app'
    def put(self,kind,rid,payload):
        self.writes.append((kind,rid,payload))
        if kind=='entertainment_configuration':
            self.data[kind][0].update(status='active' if payload['action']=='start' else 'inactive',active_streamer={'rid':'app','rtype':'auth_v1'})
        if kind=='light' and self.fail_light:raise OSError('light unavailable')


class FinishingTests(unittest.TestCase):
    def session(self,bridge,mode='restore'):
        return finishing.FinishSession(bridge,bridge.data['entertainment_configuration'][0],dict(preferences.DEFAULTS,stop_behavior=mode,stop_scene='scene'), 'app')
    def test_owned_identity_not_just_active(self):
        self.assertTrue(finishing.owned({'status':'active','active_streamer':{'rid':'app','rtype':'auth_v1'}},'app'))
        self.assertFalse(finishing.owned({'status':'active','active_streamer':{'rid':'other','rtype':'auth_v1'}},'app'))
    def test_state_snapshot_uses_writable_values_and_correct_colour_mode(self):
        l={'on':{'on':False},'color':{'xy':{'x':.2,'y':.3}},'color_temperature':{'mirek_valid':True,'mirek':350}}
        p=finishing.payload(l);self.assertNotIn('color',p);self.assertEqual(p['color_temperature'],{'mirek':350})
        l['gradient']={'points':[{'color':{'xy':{'x':.2,'y':.3}}}],'mode':'interpolated_palette','points_capable':5}
        p=finishing.payload(l);self.assertNotIn('color_temperature',p);self.assertNotIn('points_capable',p['gradient'])
    def test_restore_and_scene_are_limited_to_area(self):
        for mode in ['restore','scene']:
            b=Bridge();s=self.session(b,mode)
            self.assertTrue(s.before_release());result=s.apply(True)
            self.assertEqual(result['status'],'applied')
            self.assertEqual(b.writes[0][0],'light' if mode=='restore' else 'scene')
    def test_interrupted_finish_does_not_write(self):
        b=Bridge();s=self.session(b)
        self.assertEqual(s.apply(True,allowed=lambda:False),{'status':'skipped','reason':'interrupted'})
        self.assertFalse(b.writes)

    def test_external_light_change_skips(self):
        b=Bridge();s=self.session(b);b.data['light'][0]['dimming']['brightness']=80
        self.assertFalse(s.before_release());self.assertEqual(s.apply(False)['status'],'skipped');self.assertFalse(b.writes)
    def test_other_active_area_skips(self):
        b=Bridge();s=self.session(b);b.data['entertainment_configuration'][0]['status']='active'
        self.assertEqual(s.apply(True)['status'],'skipped');self.assertFalse(b.writes)
    def test_edited_or_out_of_area_scene_is_rejected(self):
        b=Bridge();s=self.session(b,'scene');b.data['scene'][0]['actions'].append({'target':{'rid':'other','rtype':'light'}})
        with self.assertRaises(ValueError):s.apply(True)
        self.assertFalse(b.writes)
    def test_partial_restoration_stops_after_an_external_change(self):
        b=Bridge();extra=copy.deepcopy(b.data['light'][0]);extra['id']='other'
        b.data['light'].append(extra)
        b.data['entertainment_configuration'][0]['light_services'].append({'rid':'other','rtype':'light'})
        s=self.session(b)
        original=b.put
        def edit(kind,rid,state):
            original(kind,rid,state)
            b.data['light'][1]['dimming']['brightness']=99
        b.put=edit
        self.assertEqual(s.apply(True),{'status':'partial','reason':'changed'})
        self.assertEqual(len(b.writes),1)

    def test_missing_identity_refuses_even_default_streaming(self):
        with patch.object(Bridge,'application_id',return_value=None):
            with self.assertRaisesRegex(RuntimeError,'application identity'):self.run_fake(mode='leave')

    def test_missing_identity_or_light_state_refuses_before_activation(self):
        b=Bridge()
        with self.assertRaises(ValueError):finishing.FinishSession(b,b.data['entertainment_configuration'][0],preferences.DEFAULTS,None)
        b.data['light']=[]
        with self.assertRaises(ValueError):self.session(b)
    def test_light_failure_is_not_reported_as_success(self):
        b=Bridge();s=self.session(b);b.fail_light=True
        with self.assertRaisesRegex(RuntimeError,'Restore failed'):s.apply(True)

    def run_fake(self,mode='restore',fail=False,forced=False,takeover=False,read_fail=False,cancel_after_frame=False):
        b=Bridge();b.data['entertainment_configuration'][0]['id']='00000000-0000-0000-0000-000000000001'
        source=sync.ScreenCapture(regions=[(0,(0,0,1,1))])
        source.finish_preferences=dict(preferences.DEFAULTS,stop_behavior=mode,stop_scene='scene')
        source.finish_allowed=not forced
        source.prepare=lambda:None
        cancelled=[]
        def sample(n):
            if cancel_after_frame and source.frames_sent:
                cancelled.append(True)
                raise capture.CaptureCancelled('capture cancelled')
            if takeover:b.data['entertainment_configuration'][0]['active_streamer']['rid']='other'
            if read_fail:b.fail_state_reads=True
            if fail:raise RuntimeError('capture failed')
            return [(10,20,30)]*n
        source.sample=sample
        with tempfile.TemporaryDirectory() as tmp,patch.object(config,'CONFIG_PATH',str(Path(tmp)/'c.json')), \
             patch.object(sync,'load_config',return_value={'bridge_ip':'localhost','app_key':'key','client_key':'client'}), \
             patch.object(sync,'Bridge',return_value=b),patch.object(sync,'HueDTLS'),patch.object(sync.time,'sleep'):
            if fail or read_fail:
                with self.assertRaises(RuntimeError):sync.run_stream(source,config_id=b.data['entertainment_configuration'][0]['id'],should_run=lambda:source.frames_sent<(2 if cancel_after_frame else 1) and not cancelled)
            else:sync.run_stream(source,config_id=b.data['entertainment_configuration'][0]['id'],should_run=lambda:source.frames_sent<(2 if cancel_after_frame else 1) and not cancelled)
        return b,source
    def test_failed_snapshot_still_releases_owned_area_and_reports_error(self):
        b,s=self.run_fake(read_fail=True)
        self.assertEqual(b.data['entertainment_configuration'][0]['status'],'inactive')
        self.assertEqual(s.finish_result['status'],'error')
        self.assertFalse(any(w[0]=='light' for w in b.writes))

    def test_explicit_stop_during_frame_read_still_restores(self):
        b,s=self.run_fake(cancel_after_frame=True)
        self.assertEqual(s.finish_result,{'status':'applied','reason':'restore'})

    def test_normal_stop_restores(self):
        b,s=self.run_fake();self.assertEqual(s.finish_result['status'],'applied')
        self.assertTrue(any(w[0]=='light' for w in b.writes))
    def test_errors_signals_and_takeover_do_not_restore(self):
        for kw in [{'fail':True},{'forced':True},{'takeover':True}]:
            b,s=self.run_fake(**kw)
            self.assertFalse(any(w[0]=='light' for w in b.writes))
            if kw.get('takeover'):
                self.assertFalse(any(w[2].get('action')=='stop' for w in b.writes))

class PreferenceApiTests(unittest.TestCase):
    def test_preferences_and_token_discard_are_one_atomic_update(self):
        from huectl import webapp
        with tempfile.TemporaryDirectory() as tmp,patch.object(config,'CONFIG_PATH',str(Path(tmp)/'c.json')),patch.object(webapp,'web_sync',webapp.WebSync()):
            config.save_config({'sync_portal_remember':True,'sync_portal_tokens':{'portal-window':'test'}})
            result=webapp.Api().set_sync_preferences({'portal_remember':False,'quality':'detailed'})
            self.assertTrue(result['ok']);self.assertNotIn('sync_portal_tokens',config.load_config())
            self.assertEqual(config.load_config()['sync_quality'],'detailed')
    def test_live_or_failed_save_does_not_change_preferences(self):
        from huectl import webapp
        worker=webapp.WebSync();worker._running=True
        with patch.object(webapp,'web_sync',worker),patch.object(webapp,'update_config') as save:
            self.assertIn('error',webapp.Api().set_sync_preferences({'quality':'detailed'}));save.assert_not_called()
        worker._running=False
        with patch.object(webapp,'web_sync',worker),patch.object(webapp,'load_config',return_value={}),patch.object(webapp,'update_config',side_effect=OSError('disk full')):
            self.assertEqual(webapp.Api().set_sync_preferences({'quality':'detailed'})['error'],'disk full')


class PreferenceTests(unittest.TestCase):
    def test_defaults_and_config_roundtrip(self):
        self.assertEqual(preferences.from_config({}),preferences.DEFAULTS)
        p=preferences.validate({'quality':'detailed','portal_remember':True})
        self.assertEqual(preferences.from_config(preferences.config_patch(p)),p)
    def test_invalid_preferences_are_rejected(self):
        for value in [{'quality':[]},{'stop_behavior':'x'},{'portal_remember':1},{'stop_behavior':'scene'},{'stop_scene':''},{'extra':True}]:
            with self.assertRaises(ValueError):preferences.validate(value)
