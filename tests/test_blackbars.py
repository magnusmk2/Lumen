import copy
import unittest
from unittest.mock import patch
from huectl.blackbars import BlackBarDetector, remap_regions
from huectl import mapping, sync
from test_mapping import FakeBridge


def frame(w=64, h=36, bpp=3, x=0, y=0, value=(90, 140, 200), noise=False):
    out=bytearray(w*h*bpp)
    for row in range(h):
        for col in range(w):
            i=(row*w+col)*bpp
            if x <= col < w-x and y <= row < h-y:
                out[i:i+3]=bytes(value)
            elif noise and row < y and col == w//2:
                out[i:i+3]=bytes((200,200,200))
            if bpp==4:out[i+3]=255
    return bytes(out)


def settle(detector, buf, start=0, **kw):
    crop=None
    for i in range(9):crop=detector.process(buf,64,36,kw.get('bpp',3),start+i*.25)
    return crop


class BlackBarTests(unittest.TestCase):
    def test_letterbox_rgb_and_rgb0_ignore_alpha(self):
        for bpp in (3,4):
            self.assertEqual(settle(BlackBarDetector(),frame(bpp=bpp,y=4),bpp=bpp),(0,4,64,32))

    def test_pillarbox_and_combined(self):
        self.assertEqual(settle(BlackBarDetector(),frame(x=8)),(8,0,56,36))
        self.assertEqual(settle(BlackBarDetector(),frame(x=8,y=4)),(8,4,56,32))

    def test_candidate_must_remain_stable(self):
        d=BlackBarDetector()
        for i in range(12):
            crop=d.process(frame(y=4 if i%2 else 6),64,36,3,i*.25)
            self.assertEqual(crop,(0,0,64,36))

    def test_dark_and_black_frames_hold_boundary(self):
        d=BlackBarDetector();settle(d,frame(y=4))
        for v in [(0,0,0),(15,15,15)]:
            self.assertEqual(settle(d,frame(value=v),start=3),(0,4,64,32))
        self.assertEqual(settle(BlackBarDetector(),frame(value=(0,0,0))),(0,0,64,36))

    def test_full_picture_returns_after_short_stability_delay(self):
        d=BlackBarDetector();settle(d,frame(y=4))
        self.assertEqual(d.process(frame(),64,36,3,3),(0,4,64,32))
        self.assertEqual(d.process(frame(),64,36,3,3.5),(0,0,64,36))

    def test_one_sided_overlay_holds_last_boundary(self):
        d=BlackBarDetector();settle(d,frame(y=4))
        buf=bytearray(frame(y=4));buf[0:64*3]=bytes((80,80,80))*64
        self.assertEqual(settle(d,bytes(buf),start=3),(0,4,64,32))

    def test_sparse_subtitle_or_edge_noise(self):
        self.assertEqual(settle(BlackBarDetector(),frame(y=4,noise=True)),(0,4,64,32))

    def test_saturated_blue_is_not_black(self):
        self.assertEqual(settle(BlackBarDetector(),frame(value=(0,0,80))),(0,0,64,36))

    def test_rejects_excessive_crop_and_tiny_bright_object(self):
        self.assertEqual(settle(BlackBarDetector(),frame(x=24,y=12)),(0,0,64,36))

    def test_resize_and_reset_discard_old_crop(self):
        d=BlackBarDetector();settle(d,frame(y=4));d.reset()
        self.assertEqual(d.process(frame(),64,36,3,3),(0,0,64,36))
        settle(d,frame(y=4),start=4)
        self.assertEqual(d.process(frame(32,18),32,18,3,7),(0,0,32,18))

    def test_bad_frame_is_rejected(self):
        d=BlackBarDetector()
        for args in [(b'',64,36,3),(b'',0,36,3),(b'',64,36,2)]:
            with self.assertRaises(ValueError):d.process(*args)

    def test_manual_geometry_and_nonsequential_ids_stay_inside_content(self):
        regions=[(8,(0,29,24,36)),(2,(24,20,52,36)),(13,(63,35,64,36))]
        out=remap_regions(regions,64,36,(8,4,56,32))
        self.assertEqual([i for i,_ in out],[8,2,13])
        for _,(a,b,c,d) in out:
            self.assertTrue(8<=a<c<=56 and 4<=b<d<=32)
        self.assertIs(remap_regions(regions,64,36,(0,0,64,36)),regions)

    def test_normalized_rectangles_are_rounded_only_in_content_grid(self):
        rectangles={'7':[.1,.8,.6,1]}
        original=mapping.pixels(rectangles,64,36)
        self.assertEqual(remap_regions(original,64,36,(8,4,56,32),rectangles),
                         [(7,(13,26,37,32))])

    def test_old_profile_identity_and_setting_validation(self):
        topo=mapping.discover(FakeBridge(),'area');p=mapping.default_profile(topo)
        old=copy.deepcopy(p);old.pop('ignore_black_bars')
        self.assertEqual(mapping.resolve(p,topo),mapping.resolve(old,topo))
        for v in [1,None,'true',{}]:
            p['ignore_black_bars']=v
            with self.assertRaises(ValueError):mapping.validate(p,topo)

    def test_gui_and_cli_source_configuration_loads_saved_detection_setting(self):
        bridge=FakeBridge();topo=mapping.discover(bridge,'area')
        profile=mapping.default_profile(topo);profile['ignore_black_bars']=True
        cfg={'sync_mapping':{mapping.profile_key(topo,'DP-3'):{'profile':profile,'revision':7}}}
        source=sync.ScreenCapture(output='DP-3');source.bind_bridge(bridge)
        with patch('huectl.sync.load_config',return_value=cfg):
            source.configure(bridge.data['entertainment_configuration'][0])
        self.assertTrue(source._ignore_black_bars)
        self.assertEqual(source.mapping_revision,7)

    def test_sampler_applies_crop_and_live_toggle_at_frame_boundary(self):
        topo=mapping.discover(FakeBridge(),'area');p=mapping.default_profile(topo)
        p.update(mode='desk',height=.2,ignore_black_bars=True)
        class Stream:
            bpp=4
            def latest(self):return frame(bpp=4,y=4)
        source=sync.ScreenCapture(mapping_profile=p,topology=topo,saturation=1)
        source.regions=mapping.pixels(mapping.resolve(p,topo)[0],64,36)
        with patch.object(source,'_open',return_value=Stream()), patch('huectl.blackbars.time.monotonic',return_value=0) as now:
            before=source.sample(3)
            for i in range(1,9):now.return_value=i*.25;after=source.sample(3)
            self.assertTrue(all(v==(90,140,200) for v in after))
            self.assertNotEqual(before,after)
            self.assertEqual(source.sampling_status['crop'],[0,4/36,1,32/36])
            p['ignore_black_bars']=False;source.queue_mapping(p,9)
            self.assertTrue(source.sampling_status['enabled'])
            source.sample(3)
            self.assertEqual(source.mapping_revision,9)
            self.assertFalse(source.sampling_status['enabled'])
            self.assertEqual(source.sampling_status['crop'],[0,0,1,1])

if __name__=='__main__':unittest.main()
