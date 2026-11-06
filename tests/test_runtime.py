import sys
import time
import tempfile
from pathlib import Path
import unittest
from unittest.mock import Mock, patch

from huectl import sync, capture, config, mapping
from huectl.webapp import WebSync
from huectl.mapping_api import MappingAPI
from test_mapping import FakeBridge


class RuntimeTests(unittest.TestCase):
    def setUp(self):
        temp=tempfile.TemporaryDirectory();self.addCleanup(temp.cleanup)
        cp=patch.object(config,'CONFIG_PATH',str(Path(temp.name)/'config.json'))
        cp.start();self.addCleanup(cp.stop)
        self.bridge = FakeBridge()
        self.bridge.put = Mock()
        self.cfg = {'bridge_ip':'localhost','app_key':'key','client_key':'client'}
        self.load = patch.object(sync,'load_config',return_value=self.cfg)
        self.load.start();self.addCleanup(self.load.stop)
        self.b = patch.object(sync,'Bridge',return_value=self.bridge)
        self.b.start();self.addCleanup(self.b.stop)
        self.dtls = patch.object(sync,'HueDTLS')
        self.dtls.start();self.addCleanup(self.dtls.stop)

    def test_failed_capture_does_not_activate_bridge_and_cleans_source(self):
        source=Mock()
        source.prepare.side_effect=RuntimeError('no frame')
        with self.assertRaisesRegex(RuntimeError,'no frame'):
            sync.run_stream(source,config_id='area')
        self.bridge.put.assert_not_called();source.close.assert_called_once()

    def test_cancel_before_start_does_not_activate(self):
        source=Mock()
        sync.run_stream(source,config_id='area',should_run=lambda:False)
        self.bridge.put.assert_not_called();source.close.assert_called_once()

    def test_stream_failure_releases_area(self):
        source=Mock();source.sample.side_effect=RuntimeError('capture died')
        with self.assertRaisesRegex(RuntimeError,'capture died'):
            sync.run_stream(source,config_id='area')
        self.assertEqual(self.bridge.put.call_args_list[-1].args,('entertainment_configuration','area',{'action':'stop'}))
        source.close.assert_called_once()

    def test_stale_frame_after_recorder_exit_is_not_reused(self):
        stream=capture.FrameStream([sys.executable,'-c',"import sys;sys.stdout.buffer.write(b'abc');sys.stdout.flush()"],1,1,3).start()
        try:
            stream._proc.wait(timeout=2)
            with self.assertRaises(capture.CaptureError):stream.latest()
        finally:stream.close()

    def test_cancel_missing_frame_returns_promptly(self):
        stream=capture.FrameStream([sys.executable,'-c','import time;time.sleep(20)'],1,1,3).start()
        try:
            stream.cancelled=lambda:True
            start=time.monotonic()
            with self.assertRaisesRegex(capture.CaptureError,'cancelled'):stream.latest()
            self.assertLess(time.monotonic()-start,.2)
        finally:stream.close()

    def test_stderr_flood_cannot_block_recorder(self):
        script="import sys,time\nfor i in range(2000):\n sys.stderr.write('x'*100+'\\n');sys.stderr.flush();sys.stdout.buffer.write(b'abc');sys.stdout.flush()\ntime.sleep(2)"
        stream=capture.FrameStream([sys.executable,'-c',script],1,1,3).start()
        try:
            self.assertEqual(stream.latest(),b'abc')
            time.sleep(.1)
            self.assertEqual(stream.latest(),b'abc')
            self.assertLessEqual(len(stream._stderr),2048)
        finally:stream.close()

    def test_worker_rejects_parallel_start_and_bad_fps(self):
        w=WebSync();w._running=True
        self.assertIn('error',w.start('DP-1',1.6,30,'area'))
        w._running=False
        self.assertIn('error',w.start('DP-1',1.6,True,'area'))

    def test_manual_mapping_preview_does_not_refetch_bridge(self):
        api=MappingAPI()
        with patch('huectl.mapping_api.load_bridge',return_value=self.bridge),patch('huectl.mapping_api.load_config',return_value={}):
            ctx=api.get('area','DP-1')
        # The backend must use its cached topology for interactive geometry work.
        with patch('huectl.mapping_api.load_bridge',side_effect=AssertionError('unexpected network')):
            p=ctx['profile'];p['mode']='desk'
            self.assertEqual(len(api.preview('area','DP-1',p)['rectangles']),3)

    def test_cli_uses_saved_monitor_and_profile(self):
        from io import StringIO
        from contextlib import redirect_stdout
        cfg={**self.cfg,'sync_output':'DP-3','sync_area_id':'area','sync_fps':30}
        with patch.object(sync,'load_config',return_value=cfg), patch.object(sys,'argv',['hue-sync','--show-mapping']):
            out=StringIO()
            with redirect_stdout(out):self.assertEqual(sync.main(),0)
            import json
            self.assertEqual(json.loads(out.getvalue())['output'],'DP-3')


    def test_interprocess_stream_lock_refuses_second_session(self):
        with config.stream_lock():
            with self.assertRaisesRegex(RuntimeError,'already streaming'):
                with config.stream_lock():pass
        with config.stream_lock():pass

    def test_active_area_is_not_stolen(self):
        self.bridge.data['entertainment_configuration'][0]['status']='active'
        with self.assertRaisesRegex(RuntimeError,'in use'):
            sync.run_stream(Mock(),config_id='area')
        self.bridge.put.assert_not_called()


    def test_portal_selection_preserves_non_hyprland_capture(self):
        self.assertEqual(sync.ScreenCapture(output='portal-selection').backend,'portal')


    def test_signal_quit_uses_the_real_tray_icon_once(self):
        from types import SimpleNamespace
        from huectl import webapp
        icon=Mock()
        fake=SimpleNamespace(Icon=Mock(return_value=icon),Menu=Mock(),MenuItem=Mock())
        window=Mock()
        class Event:
            def __iadd__(self, fn):self.fn=fn;return self
        window.events=SimpleNamespace(closing=Event())
        with patch.dict(sys.modules,{'pystray':fake}),patch.object(webapp,'_tray_image'),patch.object(webapp,'web_sync') as worker,patch.object(webapp,'_release_single_instance'):
            webapp._setup_tray(window)
            window._lumen_quit();window._lumen_quit()
            icon.stop.assert_called_once()
            worker.shutdown.assert_called_once()
            window.destroy.assert_called_once()



if __name__=='__main__':unittest.main()
