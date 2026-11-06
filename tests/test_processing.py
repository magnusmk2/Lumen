import math
import tempfile
import unittest
from unittest.mock import patch
from pathlib import Path

from huectl import processing, capture, sync, config
from huectl.webapp import WebSync, _PreviewCapture


class ColorTests(unittest.TestCase):
    def test_identity_matches_original_colour_math(self):
        p=processing.ColorProcessor()
        colors=[(r,g,b) for r in (0,3,50,255) for g in (0,127,255) for b in (0,17,255)]
        self.assertEqual(p.process(colors),[capture.punch(c,1.6,1) for c in colors])

    def test_gamma_and_brightness(self):
        p=processing.ColorProcessor({'saturation':1,'gamma':2,'brightness':.5})
        self.assertEqual(p.process([(128,128,128)]),[(32,32,32)])
        for gamma in (.1,1,5):
            self.assertEqual(processing.ColorProcessor({'gamma':gamma}).process([(0,0,0)]),[(0,0,0)])

    def test_smoothing_time_constant_and_fps_invariance(self):
        outputs=[]
        for fps in (20,30,50):
            p=processing.ColorProcessor({'saturation':1,'response_ms':1000})
            p.process([(0,0,0)],now=0)
            for i in range(1,fps+1):out=p.process([(255,255,255)],now=i/fps)
            outputs.append(out)
        self.assertEqual(outputs,[[(161,161,161)]]*3)

    def test_zero_response_exact_bypass(self):
        p=processing.ColorProcessor({'saturation':1,'response_ms':0})
        p.process([(0,0,0)],now=0)
        self.assertEqual(p.process([(255,0,0)],now=0),[(255,0,0)])

    def test_bounded_monotonic_step_and_dark_fade(self):
        p=processing.ColorProcessor({'saturation':1,'response_ms':200})
        p.process([(0,0,0)],now=0);previous=0
        for i in range(1,20):
            value=p.process([(255,0,0)],now=i*.05)[0][0]
            self.assertTrue(previous<=value<=255);previous=value
        self.assertEqual(p.process([(0,0,0)],now=20),[(0,0,0)])

    def test_parameter_change_resets_history_but_same_options_do_not(self):
        p=processing.ColorProcessor({'saturation':1,'response_ms':1000})
        p.process([(0,0,0)],now=0);p.configure(p.options)
        self.assertEqual(p.process([(255,0,0)],now=1),[(161,0,0)])
        p.configure(dict(p.options,brightness=0))
        self.assertEqual(p.process([(255,0,0)],now=1),[(0,0,0)])

    def test_reset_channel_count_and_irregular_clock(self):
        p=processing.ColorProcessor({'saturation':1,'response_ms':1000})
        p.process([(0,0,0)],now=2)
        self.assertEqual(p.process([(255,0,0)],now=1),[(0,0,0)])
        self.assertEqual(p.process([(255,0,0),(0,255,0)],now=3),[(255,0,0),(0,255,0)])
        p.reset();self.assertEqual(p.process([(0,0,255)],now=4),[(0,0,255)])

    def test_validation_rejects_invalid_without_clamping_silently(self):
        for name in processing.DEFAULTS:
            for value in (True,None,'1',float('inf'),float('nan'),-1):
                with self.assertRaises(ValueError):processing.validate({name:value})
        for p in ({'brightness':1.01},{'gamma':5.1},{'response_ms':2001},{'saturation':4.1},{'unknown':1},[]):
            with self.assertRaises(ValueError):processing.validate(p)

    def test_old_config_defaults_and_partial_patch(self):
        self.assertEqual(processing.from_config({}),processing.DEFAULTS)
        opts=processing.validate({'gamma':2},dict(processing.DEFAULTS,response_ms=300))
        self.assertEqual(opts['response_ms'],300)
        self.assertEqual(processing.from_config(processing.config_patch(opts)),opts)

    def test_sampler_swaps_options_once_and_preview_is_processed_output(self):
        class Stream:
            bpp=3
            def latest(self):return bytes((200,100,50))
        source=_PreviewCapture(regions=[(0,(0,0,1,1))],width=1,height=1,saturation=1)
        with patch.object(source,'_open',return_value=Stream()):
            self.assertEqual(source.sample(1),[(200,100,50)])
            opts=processing.validate({'saturation':1,'brightness':.5})
            source.queue_processing(opts);opts['brightness']=0
            self.assertEqual(source.sample(1),[(100,50,25)])
            self.assertEqual(source.last_colors,[(100,50,25)])

    def test_gui_save_failure_does_not_queue_or_change_desired_options(self):
        worker=WebSync();worker._running=True;worker._processing=dict(processing.DEFAULTS)
        source=sync.ScreenCapture();worker._source=source
        with patch('huectl.webapp.save_config',side_effect=OSError('disk full')):
            with self.assertRaises(OSError):worker.update_processing({'brightness':.2})
        self.assertEqual(worker._processing,processing.DEFAULTS)
        self.assertIsNone(source._pending_processing)

    def test_cli_loads_saved_controls_and_explicit_flags_override_them(self):
        from test_mapping import FakeBridge
        cfg={'bridge_ip':'localhost','app_key':'key','client_key':'client','sync_area_id':'area',
             'sync_output':'DP-3','sync_brightness':.6,'sync_gamma':1.5,'sync_response_ms':300}
        for flags, expected in [([], (.6,1.5,300)),
                               (['--brightness','.8','--gamma','2','--response-ms','100'],(.8,2,100))]:
            with patch('sys.argv',['hue-sync']+flags), patch.object(sync,'load_config',return_value=cfg), \
                 patch.object(sync,'Bridge',return_value=FakeBridge()), patch.object(sync,'ScreenCapture') as source, \
                 patch.object(sync,'run_stream'):
                self.assertEqual(sync.main(),0)
                actual=source.call_args.kwargs
                self.assertEqual(tuple(actual[k] for k in ('brightness','gamma','response_ms')),expected)

    def test_persistence_and_partial_live_patches(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(config,'CONFIG_PATH',str(Path(tmp)/'config.json')):
            worker=WebSync();worker._running=True;worker._source=sync.ScreenCapture()
            worker.update_processing({'response_ms':300})
            result=worker.update_processing({'gamma':1.5})
            self.assertEqual(result['processing']['response_ms'],300)
            self.assertEqual(processing.from_config(config.load_config()),result['processing'])
            self.assertEqual(worker._source._pending_processing,result['processing'])
