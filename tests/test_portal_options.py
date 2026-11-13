import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock,patch
from huectl import portal,config,capture


class PortalTests(unittest.TestCase):
    def session(self,remember=True,kind=2):
        s=portal.PortalSession.__new__(portal.PortalSession)
        s.source_type=kind;s.remember=remember;s.token_key='portal-window'
        s.source_size=None;s.source_serial=None;s._token='unit';s.handle=None
        s.conn=Mock();reply=Mock();reply.unpack.return_value=(0,)
        fdlist=Mock();fdlist.get.return_value=9
        s.conn.call_with_unix_fd_list_sync.return_value=(reply,fdlist)
        results=[{'session_handle':'/session/unit'}, {},
                 {'restore_token':'new-token','streams':[(4,{'size':(800,600),'pipewire-serial':12345,'source_type':2})]}]
        s._request=Mock(side_effect=results)
        return s
    def test_response_before_method_reply_is_not_lost(self):
        s=self.session();s.cancelled=lambda:False;s.timeout_ms=100
        def call(*args):
            callback=s.conn.signal_subscribe.call_args.args[-1]
            params=Mock();params.unpack.return_value=(0,{'session_handle':'/session/test'})
            callback(s.conn,'sender','/request/legacy','interface','Response',params)
            return '/request/legacy'
        s._request=portal.PortalSession._request.__get__(s)
        s._call=Mock(side_effect=call)
        self.assertEqual(s._request('CreateSession','(a{sv})',({},)),{'session_handle':'/session/test'})
        s.conn.signal_unsubscribe.assert_called_once()

    def test_request_cancellation_closes_object(self):
        s=self.session();s.cancelled=lambda:True;s.timeout_ms=100
        s._request=portal.PortalSession._request.__get__(s)
        s._call=Mock(return_value='/request/test')
        with self.assertRaisesRegex(capture.CaptureError,'cancelled'):
            s._request('Start','(a{sv})',({},))
        self.assertEqual(s.conn.call_sync.call_args.args[3],'Close')

    def test_source_type_hidden_cursor_and_rotated_token(self):
        s=self.session()
        with patch.object(portal,'capabilities',return_value={'types':3,'version':6,'cursors':3}), \
             patch.object(portal,'take_restore_token',return_value='old-token') as take, \
             patch.object(portal,'store_restore_token') as store,patch.object(portal.os,'dup',return_value=10):
            self.assertEqual(s.start(),(4,10))
        opts=s._request.call_args_list[1].args[2][1]
        self.assertEqual(opts['types'].unpack(),2);self.assertEqual(opts['cursor_mode'].unpack(),1)
        self.assertEqual(opts['restore_token'].unpack(),'old-token')
        take.assert_called_once_with('portal-window');store.assert_called_once_with('portal-window','new-token')
        self.assertEqual(s.source_size,[800,600]);self.assertEqual(s.source_serial,'12345')
    def test_window_request_rejects_a_returned_monitor(self):
        s=self.session(False)
        s._request.side_effect=[{'session_handle':'/session/unit'},{},{'streams':[(4,{'source_type':1})]}]
        with patch.object(portal,'capabilities',return_value={'types':3,'version':6,'cursors':0}):
            with self.assertRaisesRegex(capture.CaptureError,'select a window'):s.start()
        s.conn.call_with_unix_fd_list_sync.assert_not_called()

    def test_no_persistence_options_on_old_portal_or_opt_out(self):
        for version,remember in [(3,True),(6,False)]:
            s=self.session(remember)
            with patch.object(portal,'capabilities',return_value={'types':3,'version':version,'cursors':0}), \
                 patch.object(portal,'take_restore_token') as take,patch.object(portal,'store_restore_token') as store, \
                 patch.object(portal.os,'dup',return_value=10):s.start()
            opts=s._request.call_args_list[1].args[2][1]
            self.assertNotIn('restore_token',opts);self.assertNotIn('persist_mode',opts)
            take.assert_not_called();store.assert_not_called()
    def test_unsupported_window_does_not_open_picker(self):
        s=self.session()
        with patch.object(portal,'capabilities',return_value={'types':1,'version':6,'cursors':1}):
            with self.assertRaisesRegex(capture.CaptureError,'does not support'):s.start()
        s._request.assert_not_called()
    def test_tokens_are_single_use_and_stored_only_while_opted_in(self):
        with tempfile.TemporaryDirectory() as tmp,patch.object(config,'CONFIG_PATH',str(Path(tmp)/'config.json')):
            config.save_config({'sync_portal_remember':True})
            portal.store_restore_token('portal-window','test-token')
            self.assertEqual(portal.take_restore_token('portal-window'),'test-token')
            self.assertIsNone(portal.take_restore_token('portal-window'))
            config.save_config({'sync_portal_remember':False})
            portal.store_restore_token('portal-window','new-token')
            self.assertIsNone(portal.take_restore_token('portal-window'))
    def test_portal_session_closed_after_cancel(self):
        session=Mock();session.start.side_effect=capture.CaptureError('capture cancelled')
        with patch.object(portal.shutil,'which',return_value='/bin/gst'),patch.object(portal,'PortalSession',return_value=session),patch.object(portal,'load_config',return_value={}):
            with self.assertRaisesRegex(capture.CaptureError,'cancelled'):portal.open_portal_stream('portal-window')
        session.close.assert_called_once()

class PortalPipelineTests(unittest.TestCase):
    def test_window_stream_uses_serial_target_and_requested_quality(self):
        session=Mock();session.start.return_value=(4,9);session.source_serial='12345';session.source_size=[800,600]
        stream=Mock()
        with patch.object(portal.shutil,'which',return_value='/bin/gst'),patch.object(portal,'load_config',return_value={}), \
             patch.object(portal,'PortalSession',return_value=session) as constructor,patch.object(portal,'_PortalStream',return_value=stream) as factory:
            self.assertIs(portal.open_portal_stream('portal-window',width=128,height=72),stream)
        self.assertEqual(constructor.call_args.kwargs['source_type'],2)
        cmd=factory.call_args.args[0]
        self.assertIn('target-object=12345',cmd)
        self.assertIn('video/x-raw,format=RGB,width=128,height=72',cmd)
        self.assertEqual(stream.backend,'portal-window');stream.latest.assert_called_once()
