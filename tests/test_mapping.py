import copy
import json
import math
import os
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch

from huectl import mapping, config, sync, capture


class FakeBridge:
    def __init__(self):
        table = [{'start':s, 'length':n} for s,n in [(0,1),(1,2),(3,3),(6,4),(10,3),(13,2),(15,1)]]
        self.data = {
            'bridge':[{'bridge_id':'test-bridge'}],
            'entertainment_configuration':[{'id':'area','metadata':{'name':'Desk'},'channels':[
                {'channel_id':cid,'position':{'x':x,'z':-.4},'members':[
                    {'service':{'rid':'strip','rtype':'entertainment'},'index':i} for i in ids]}
                for cid,x,ids in [(0,.4,[0,1]),(1,0,[2,3]),(2,-.4,[4,5,6])]]}],
            'entertainment':[{'id':'strip','owner':{'rid':'device'},'renderer_reference':{'rid':'light'},'segments':{'segments':table}}],
            'device':[{'id':'device','metadata':{'name':'Test strip'}}],
            'light':[{'id':'light','gradient':{'pixel_count':16,'points_capable':5}}]}
    def get(self, kind):
        return copy.deepcopy(self.data[kind])


class GeometryTests(unittest.TestCase):
    def setUp(self):
        self.bridge=FakeBridge(); self.topo=mapping.discover(self.bridge,'area')
        self.p=mapping.default_profile(self.topo);self.p['mode']='desk'

    def test_reported_coverage_not_member_count_or_palette_points(self):
        self.assertEqual(len(self.topo['channels']),3)
        r,_=mapping.resolve(self.p,self.topo)
        self.assertEqual(r['2'],[0,.8,.375,1])
        self.assertEqual(r['1'],[.375,.8,.8125,1])
        self.assertEqual(r['0'],[.8125,.8,1,1])

    def test_legacy_regression(self):
        self.p['mode']='legacy'
        rects,_=mapping.resolve(self.p,self.topo)
        for w,h in [(64,36),(65,37),(1,1)]:
            self.assertEqual(mapping.pixels(rects,w,h),sync.channel_regions(
                self.bridge.data['entertainment_configuration'][0],w,h))

    def test_legacy_edges(self):
        self.topo['channels'][0]['position']['x']=1
        self.topo['channels'][2]['position']['x']=-1
        self.assertEqual(mapping.legacy_regions(self.topo)['0'],[.8,0,1,1])
        self.assertEqual(mapping.legacy_regions(self.topo)['2'],[0,0,.2,1])

    def test_equal_and_reversed_order(self):
        self.p['devices']['strip']={'strategy':'equal','order':[2,1,0],'reverse':True}
        r,_=mapping.resolve(self.p,self.topo)
        self.assertEqual(r['0'][0],0)
        self.assertEqual(r['2'][2],1)
        self.assertAlmostEqual(r['1'][0],1/3)

    def test_pixel_edges_adjacent_and_nonempty_on_odd_resolution(self):
        r,_=mapping.resolve(self.p,self.topo)
        p=dict(mapping.pixels(r,65,37))
        self.assertEqual(p[2][2],p[1][0]);self.assertEqual(p[1][2],p[0][0])
        self.assertEqual(p[0][2],65)
        self.assertEqual([c for c,_ in mapping.pixels(r,65,37)],[0,1,2])
        self.assertEqual(mapping.pixels({'4':[.999,.999,1,1]},1,1),[(4,(0,0,1,1))])

    def test_manual_only_changes_one_channel_and_allows_overlap(self):
        self.p['overrides']['1']=[0,.5,1,.9]
        r,_=mapping.resolve(self.p,self.topo)
        self.assertEqual(r['1'],[0,.5,1,.9]);self.assertEqual(r['2'][2],.375)

    def test_band_inset_and_device_subsection(self):
        self.p.update(height=.3,inset=.1)
        self.p['devices']['strip']={'strategy':'equal','order':[2,1,0],'start':.2,'end':.8}
        r,_=mapping.resolve(self.p,self.topo)
        self.assertAlmostEqual(r['2'][0],.2);self.assertAlmostEqual(r['0'][2],.8)
        self.assertAlmostEqual(r['1'][1],.6);self.assertEqual(r['1'][3],.9)

    def test_invalid_rectangles_and_numbers(self):
        for rect in [[0,0,0,1],[-.1,0,1,1],[0,0,1,1.01],[0,0,float('nan'),1], [0,False,1,1]]:
            with self.subTest(rect=rect),self.assertRaises(ValueError):
                p=copy.deepcopy(self.p);p['overrides']['0']=rect;mapping.resolve(p,self.topo)
        for value in [float('inf'),float('nan'),True,-1,1.1]:
            with self.subTest(value=value),self.assertRaises(ValueError):
                p=copy.deepcopy(self.p);p['height']=value;mapping.resolve(p,self.topo)

    def test_unknown_or_duplicate_channels_rejected(self):
        self.p['overrides']['99']=[0,0,1,1]
        with self.assertRaises(ValueError):mapping.resolve(self.p,self.topo)
        self.p['overrides']={};self.p['devices']['strip']={'strategy':'equal','order':[0,0,2]}
        with self.assertRaises(ValueError):mapping.resolve(self.p,self.topo)

    def test_signature_changes_for_geometry_not_name(self):
        old=self.topo['signature']
        self.bridge.data['device'][0]['metadata']['name']='New name'
        self.assertEqual(mapping.discover(self.bridge)['signature'],old)
        self.bridge.data['entertainment'][0]['segments']['segments'][0]['length']=2
        new=mapping.discover(self.bridge)
        self.assertNotEqual(new['signature'],old)
        with self.assertRaises(ValueError):mapping.resolve(self.p,new)

    def test_incomplete_and_disjoint_coverage_falls_back(self):
        self.bridge.data['entertainment_configuration'][0]['channels'][0]['members'][0]['index']=99
        t=mapping.discover(self.bridge);self.assertFalse(t['devices'][0]['coverage_available'])
        p=mapping.default_profile(t);p['mode']='desk'
        r,_=mapping.resolve(p,t);self.assertAlmostEqual(r['2'][2],1/3)

    def test_plain_single_channel_without_segments(self):
        b=self.bridge;b.data['light'][0].pop('gradient')
        b.data['entertainment'][0].pop('segments')
        b.data['entertainment_configuration'][0]['channels']=b.data['entertainment_configuration'][0]['channels'][:1]
        t=mapping.discover(b);p=mapping.default_profile(t);p['mode']='desk'
        self.assertEqual(mapping.resolve(p,t)[0],{'0':[0,.8,1,1]})

    def test_top_color_cannot_affect_bottom_sample_rgb_and_rgba(self):
        r,_=mapping.resolve(self.p,self.topo)
        for bpp in (3,4):
            def frame(top):
                return b''.join(bytes(top if y<28 else (0,0,255))+(b'\x00' if bpp==4 else b'') for y in range(36) for x in range(64))
            for _,box in mapping.pixels(r,64,36):
                self.assertEqual(capture.region_average(frame((255,0,0)),64,bpp,box),(0,0,255))
                self.assertEqual(capture.region_average(frame((0,255,0)),64,bpp,box),(0,0,255))

    def test_runtime_mapping_swaps_between_frames(self):
        src=sync.ScreenCapture(mapping_profile=self.p,topology=self.topo)
        src.regions=mapping.pixels(mapping.resolve(self.p,self.topo)[0],64,36)
        class Stream:
            bpp=3
            def latest(self):return bytes([0,0,255])*(64*36)
        src._open=lambda:Stream()
        p=copy.deepcopy(self.p);p['overrides']['1']=[0,0,1,.5]
        src.queue_mapping(p,7)
        self.assertEqual(src.mapping_revision,0)
        self.assertEqual(len(src.sample(3)),3);self.assertEqual(src.mapping_revision,7)
        self.assertEqual(dict(src.regions)[1],(0,0,64,18))

    def test_multiple_strips_each_get_full_screen_range(self):
        b=self.bridge
        service=copy.deepcopy(b.data['entertainment'][0]);service['id']='strip2'
        b.data['entertainment'].append(service)
        extra=copy.deepcopy(b.data['entertainment_configuration'][0]['channels'])
        for c in extra:
            c['channel_id']+=10
            for m in c['members']:m['service']['rid']='strip2'
        b.data['entertainment_configuration'][0]['channels']+=extra
        t=mapping.discover(b);p=mapping.default_profile(t);p['mode']='desk'
        rects,_=mapping.resolve(p,t)
        self.assertEqual(rects['0'],rects['10'])
        self.assertEqual(rects['2'],rects['12'])

    def test_shared_channel_requires_explicit_override(self):
        b=self.bridge
        service=copy.deepcopy(b.data['entertainment'][0]);service['id']='strip2'
        b.data['entertainment'].append(service)
        b.data['entertainment_configuration'][0]['channels'][0]['members'].append(
            {'service':{'rid':'strip2'},'index':0})
        t=mapping.discover(b);p=mapping.default_profile(t);p['mode']='desk'
        with self.assertRaisesRegex(ValueError,'Shared'):mapping.resolve(p,t)
        p['overrides']['0']=[0,.8,1,1]
        self.assertEqual(mapping.resolve(p,t)[0]['0'],[0,.8,1,1])

    def test_overlapping_member_ranges_disable_coverage(self):
        self.bridge.data['entertainment'][0]['segments']['segments'][0]['length']=3
        t=mapping.discover(self.bridge)
        self.assertFalse(t['devices'][0]['coverage_available'])
        self.assertIn('segment_overlap',t['channels'][0]['warnings'])


    def test_device_layout_can_preserve_legacy_with_desk_preset(self):
        self.p['devices']['strip']={'mode':'legacy','strategy':'equal','order':[2,1,0]}
        r,_=mapping.resolve(self.p,self.topo)
        self.assertEqual(r,mapping.legacy_regions(self.topo))
        self.p['mode']='legacy';self.p['devices']['strip']['mode']='desk'
        self.assertEqual(mapping.resolve(self.p,self.topo)[0]['2'][1],.8)


    def test_nullable_optional_capabilities_allow_manual_mapping(self):
        self.bridge.data['entertainment'][0]['segments']=None
        self.bridge.data['entertainment'][0]['renderer_reference']=None
        self.bridge.data['light'][0]['gradient']=None
        t=mapping.discover(self.bridge)
        self.assertFalse(t['devices'][0]['coverage_available'])
        p=mapping.default_profile(t);p['mode']='desk'
        p['overrides']['0']=[0,0,1,1]
        self.assertEqual(mapping.resolve(p,t)[0]['0'],[0,0,1,1])



class PersistenceTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.patch=patch.object(config,'CONFIG_PATH',str(Path(self.tmp.name)/'config.json'))
        self.patch.start();self.addCleanup(self.patch.stop)
        self.topo=mapping.discover(FakeBridge());self.p=mapping.default_profile(self.topo)
        config.save_config({'app_key':'secret','columns':2})

    def test_preserves_keys_and_permissions(self):
        self.assertEqual(mapping.save_profile(self.topo,'DP-1',self.p,0),1)
        self.assertEqual(config.load_config()['app_key'],'secret')
        self.assertEqual(os.stat(config.CONFIG_PATH).st_mode&0o777,0o600)

    def test_stale_revision_preserves_file(self):
        mapping.save_profile(self.topo,'DP-1',self.p,0)
        before=Path(config.CONFIG_PATH).read_bytes()
        with self.assertRaises(ValueError):mapping.save_profile(self.topo,'DP-1',self.p,0)
        self.assertEqual(before,Path(config.CONFIG_PATH).read_bytes())

    def test_isolation(self):
        mapping.save_profile(self.topo,'DP-1',self.p,0)
        self.assertEqual(mapping.load_profile(config.load_config(),self.topo,'DP-2')[1],0)
        t=copy.deepcopy(self.topo);t['bridge_id']='other'
        self.assertEqual(mapping.load_profile(config.load_config(),t,'DP-1')[1],0)

    def test_concurrent_settings_and_profile_writes(self):
        errors=[]
        def save(i):
            try:config.save_config({str(i):i})
            except Exception as e:errors.append(e)
        ts=[threading.Thread(target=save,args=(i,)) for i in range(20)]
        for t in ts:t.start()
        for t in ts:t.join()
        self.assertFalse(errors)
        for i in range(20):self.assertEqual(config.load_config()[str(i)],i)

    def test_invalid_json_not_silently_overwritten(self):
        Path(config.CONFIG_PATH).write_text('{broken')
        with self.assertRaises(ValueError):config.save_config({'columns':3})
        self.assertEqual(Path(config.CONFIG_PATH).read_text(),'{broken')

    def test_failed_replace_keeps_original_and_cleans_temp(self):
        before=Path(config.CONFIG_PATH).read_bytes()
        with patch.object(config.os,'replace',side_effect=OSError('disk error')):
            with self.assertRaises(OSError):config.save_config({'columns':3})
        self.assertEqual(Path(config.CONFIG_PATH).read_bytes(),before)
        self.assertFalse(list(Path(self.tmp.name).glob('.huectl-*')))


if __name__=='__main__':unittest.main()
