"""Offline mocked shutdown regression; never connects to Civ V or a service."""
from pathlib import Path
import argparse
import ctypes
import importlib.util
import json
import subprocess
import tempfile
import unittest
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('behavior_exit_test', ROOT/'work/run-behavior-replay.py')
harness = importlib.util.module_from_spec(spec)
spec.loader.exec_module(harness)


class Process:
    def __init__(self, pid, ticks=10):
        self.pid, self.start_ticks, self.live, self.closed = pid, ticks, True, False
    def alive(self):
        return self.live
    def close(self):
        self.closed = True


class Binding:
    def __init__(self, session):
        self.game, self.service = Process(100), Process(200, 20)
        self.guards = [Process(300, 30), Process(400, 40)]
        self.session = session
        self.stamp = harness.session_stamp(session)
        self.verify_count = 0
    def verify(self, *, game_required=True, guards_required=True):
        self.verify_count += 1
        if harness.session_stamp(self.session) != self.stamp:
            raise ValueError('session identity changed')
        if not self.service.alive() or game_required and not self.game.alive():
            raise ValueError('bound process missing')
        if guards_required and any(not p.alive() for p in self.guards):
            raise ValueError('guard lost')
    def proof(self):
        return {'GamePID':100, 'GameStartTicks':10, 'ServicePID':200, 'ServiceStartTicks':20,
                'GuardPIDs':[300,400], 'GuardStartTicks':[30,40], 'SessionPath':str(self.session),
                'SessionFileIdentity':list(self.stamp)}
    def close(self):
        for process in (self.game, self.service, *self.guards):
            process.close()


class Clock:
    def __init__(self):
        self.value = 0
    def now(self):
        self.value += 1
        return self.value


class NormalExitTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='civ5-offline-exit-')
        self.run = Path(self.temp.name)
        self.session = self.run/'fake-session.json'
        self.session.write_text('offline nonsecret session fixture', encoding='utf-8')
        args = argparse.Namespace(run_dir=self.run, session=self.session, start_turn=215, stop_turn=230,
            return_player=0, watch_city='Abernethy', source_mode='observer', view_mode='preserve',
            tactical_sampling='preserve', quit_after_complete=True, game_pid=100, start_ticks=10,
            save_sha='A'*64, command_timeout=10)
        self.replay = harness.BehaviorReplay(args)
        self.replay.progress = Mock()
        self.replay.exit_binding = Binding(self.session)
        self.replay.safe_stop = True
        self.stop = {'turn':230,'autoplay':0,'activePlayer':0,'human':True,'observer':False,'returnPlayerAlive':True}
        self.replay.manifest = {'Status':'completed_stopped_game_open','Stopped':self.stop.copy(),
            'SaveSHA256After':'A'*64,'AnalysisCompletedUTC':'offline','UnitCount':1,'CityCount':1}
        (self.run/'world-after.json').write_text(json.dumps({'expectedTurn':230,'players':[{'units':[[1]*10],'cities':[[1]*9]}]}))
        (self.run/'native-segments').mkdir()
        (self.run/'native-segments'/'fixture.log').write_text('archived offline native evidence')
        for script in ('summarize-stacking-diagnostics.py','analyze-assault-campaign.py','profile-campaign-log.py'):
            (self.run/(script+'.result.json')).write_text(json.dumps({'exitCode':0,'stdout':'','stderr':''}))
        self.replay.call = Mock(return_value=[self.stop.copy()])
        self.quit = Mock(side_effect=self.good_quit)
        self.service = Mock(side_effect=self.good_service)
        self.quit_patch = patch.object(harness, 'control_quit', self.quit)
        self.rpc_patch = patch.object(harness.tuner, 'call_service', self.service)
        self.quit_patch.start();self.rpc_patch.start()
    def tearDown(self):
        self.quit_patch.stop();self.rpc_patch.stop();self.temp.cleanup()
    def good_quit(self, session):
        self.assertEqual(session, self.session)
        self.replay.exit_binding.game.live = False
        return {'acknowledged':True,'result':{'ok':True,'values':['quit requested']}}
    def good_service(self, session, endpoint, job, timeout):
        self.assertEqual((session,endpoint,job,timeout),(self.session,'stop',{'timeout':5},5))
        self.replay.exit_binding.service.live = False
        self.session.unlink()
        return {'ok':True,'stopping':True}
    def failure(self, message):
        with self.assertRaisesRegex(Exception, message):
            self.replay.quit_after_complete()
        proof=json.loads((self.run/'normal-exit.json').read_text())
        self.assertEqual(proof['status'],'failed')
        self.assertFalse(proof['mutationRetried'])
        self.assertFalse(proof['forcedTermination'])
        return proof
    def test_default_has_no_side_effect_or_process_read(self):
        self.replay.args.quit_after_complete = False
        self.replay.safe_stop = False;self.replay.exit_binding = None;self.replay.manifest = {}
        with patch.object(harness,'session_stamp',side_effect=AssertionError('unexpected read')):
            self.assertIsNone(self.replay.quit_after_complete())
        self.quit.assert_not_called();self.service.assert_not_called();self.replay.call.assert_not_called()
        self.assertFalse((self.run/'normal-exit.json').exists())
    def test_normal_exact_exit_and_one_service_stop(self):
        result=self.replay.quit_after_complete()
        self.assertEqual(result['status'],'completed');self.assertTrue(result['gameExitConfirmed'])
        self.assertTrue(result['sessionFileAbsent']);self.assertTrue(result['serviceExitConfirmed'])
        self.assertEqual(self.replay.manifest['Status'],'completed_game_closed_service_stopped')
        self.assertEqual(self.quit.call_count,1);self.assertEqual(self.service.call_count,1)
        self.assertEqual(self.replay.call.call_count,1)
        with self.assertRaisesRegex(ValueError,'already exists'):
            self.replay.quit_after_complete()
        self.assertEqual(self.quit.call_count,1)
    def test_unverified_partial_stop_does_not_quit(self):
        self.replay.safe_stop=False
        self.failure('requires verified stop')
        self.quit.assert_not_called();self.service.assert_not_called()
    def test_wrong_turn_does_not_quit(self):
        self.replay.manifest['Stopped']['turn']=229
        self.failure('requires verified stop');self.quit.assert_not_called()
    def test_empty_actual_census_does_not_quit(self):
        (self.run/'world-after.json').write_text(json.dumps({'expectedTurn':230,'players':[]}))
        self.failure('counts differ');self.quit.assert_not_called()
    def test_missing_archive_does_not_quit(self):
        (self.run/'native-segments'/'fixture.log').unlink()
        self.failure('requires verified stop');self.quit.assert_not_called()
    def test_analyzer_failure_does_not_quit(self):
        (self.run/'profile-campaign-log.py.result.json').write_text(json.dumps({'exitCode':2}))
        self.failure('every offline analyzer');self.quit.assert_not_called()
    def test_live_stop_drift_does_not_quit(self):
        self.replay.call.return_value=[{**self.stop,'turn':231}]
        self.failure('state changed');self.quit.assert_not_called()
    def test_missing_bound_game_before_dispatch_does_not_quit(self):
        self.replay.exit_binding.game.live=False
        self.failure('bound process missing');self.quit.assert_not_called()
    def test_session_replacement_before_dispatch_does_not_quit(self):
        self.session.write_text('replacement session with different metadata')
        self.failure('session identity');self.quit.assert_not_called();self.service.assert_not_called()
    def test_guard_loss_before_stop_prevents_rpc(self):
        self.replay.safe_stop=False;self.replay.exit_binding.guards[0].live=False
        with self.assertRaisesRegex(ValueError,'guard lost'):
            harness.BehaviorReplay.call(self.replay,'InGame','return 1','offline')
        self.service.assert_not_called()
    def test_guard_exit_after_verified_stop_is_expected(self):
        for p in self.replay.exit_binding.guards:p.live=False
        self.assertEqual(self.replay.quit_after_complete()['status'],'completed')
    def test_unknown_quit_no_retry_no_stop(self):
        self.quit.side_effect=None;self.quit.return_value={'acknowledged':False,'result':{'ok':True,'values':[]}}
        proof=self.failure('response unknown')
        self.assertTrue(proof['quitDispatched']);self.assertFalse(proof['quitAcknowledged'])
        self.assertEqual(proof['quitResponse'],self.quit.return_value)
        self.assertEqual(self.quit.call_count,1);self.service.assert_not_called()
    def test_quit_transport_failure_evidence_retained_no_retry(self):
        self.quit.side_effect=OSError('ambiguous disconnected IPC')
        proof=self.failure('ambiguous')
        self.assertTrue(proof['quitDispatched']);self.assertEqual(self.quit.call_count,1)
        self.service.assert_not_called()
    def test_exact_game_exit_timeout_is_bounded_no_force(self):
        self.quit.side_effect=None;self.quit.return_value={'acknowledged':True}
        clock=Clock()
        with patch.object(harness.time,'monotonic',clock.now),patch.object(harness.time,'sleep'):
            proof=self.failure('within30s')
        self.assertTrue(proof['quitAcknowledged']);self.assertFalse(proof['gameExitConfirmed'])
        self.assertLessEqual(clock.value,34);self.service.assert_not_called()
    def test_unknown_stop_no_retry_preserves_closed_game(self):
        self.service.side_effect=None;self.service.return_value={'ok':False,'error':'unknown stop'}
        proof=self.failure('Service stop response unknown')
        self.assertTrue(proof['gameExitConfirmed']);self.assertEqual(self.service.call_count,1)
    def test_service_exit_timeout_no_retry_or_kill(self):
        self.service.side_effect=None;self.service.return_value={'ok':True,'stopping':True}
        clock=Clock()
        with patch.object(harness.time,'monotonic',clock.now),patch.object(harness.time,'sleep'):
            proof=self.failure('after5s')
        self.assertTrue(proof['gameExitConfirmed']);self.assertEqual(self.service.call_count,1)


class IdentityAndControlTests(unittest.TestCase):
    def kernel(self, missing=False, name='CivilizationV_DX11.exe', ticks=1234):
        kernel=Mock()
        kernel.OpenProcess.return_value=0 if missing else 123
        kernel.WaitForSingleObject.return_value=258
        def times(handle,created,exit_,system,user):
            created._obj.dwLowDateTime=ticks;created._obj.dwHighDateTime=0
            return True
        def image(handle,flags,buffer,size):
            buffer.value='C:\\offline\\'+name
            return True
        kernel.GetProcessTimes.side_effect=times;kernel.QueryFullProcessImageNameW.side_effect=image
        return kernel
    def test_actual_handle_rejects_start_time_mismatch(self):
        kernel=self.kernel()
        with patch.object(harness.ctypes,'WinDLL',return_value=kernel):
            with self.assertRaisesRegex(ValueError,'PID/start/image'):
                harness.ExactExitProcess(100,504911232000001235,('civilizationv_dx11',))
        kernel.CloseHandle.assert_called_once_with(123)
    def test_actual_handle_rejects_wrong_image_and_missing_pid(self):
        for kernel in (self.kernel(name='other.exe'),self.kernel(missing=True)):
            with patch.object(harness.ctypes,'WinDLL',return_value=kernel):
                with self.assertRaises((ValueError,OSError)):
                    harness.ExactExitProcess(100,504911232000001234,('civilizationv_dx11',))
    def test_actual_handle_pins_creation_and_detects_original_exit(self):
        kernel=self.kernel()
        with patch.object(harness.ctypes,'WinDLL',return_value=kernel):
            process=harness.ExactExitProcess(100,504911232000001234,('civilizationv_dx11',))
            self.assertTrue(process.alive());kernel.WaitForSingleObject.return_value=0
            self.assertFalse(process.alive());process.close();process.close()
        kernel.CloseHandle.assert_called_once_with(123)
        kernel.OpenProcess.assert_called_once_with(0x100000|0x1000,False,100)
    def test_control_cli_exact_acknowledgement_only(self):
        for code,stdout,expected in ((0,'{"ok":true,"values":["quit requested"]}',True),
                (0,'{"ok":true,"values":[]}',False),(1,'{"ok":true,"values":["quit requested"]}',False),
                (0,'partial',False),(0,'[]',False)):
            with patch.object(harness.subprocess,'run',return_value=subprocess.CompletedProcess([],code,stdout,'')) as run:
                result=harness.control_quit(Path('offline-session'))
            self.assertIs(result['acknowledged'],expected)
            self.assertEqual(run.call_count,1)
            self.assertEqual(run.call_args.kwargs['timeout'],30)
            self.assertEqual(run.call_args.args[0][-1],'quit')
    def test_control_cli_timeout_never_retries_preserves_partial_output(self):
        with patch.object(harness.subprocess,'run',side_effect=subprocess.TimeoutExpired('offline',30,output=b'partial')) as run:
            result=harness.control_quit(Path('offline-session'))
        self.assertFalse(result['acknowledged']);self.assertTrue(result['timedOut'])
        self.assertEqual(result['stdout'],'partial');self.assertEqual(run.call_count,1)
    def test_binding_rejects_missing_or_aliased_service(self):
        args=argparse.Namespace(session=Path(__file__),game_pid=100,start_ticks=10)
        with patch.object(harness,'ExactExitProcess',side_effect=AssertionError('should reject before opening')):
            for watcher in ({},{'Service':100},{'Service':300},{'Service':True}):
                with self.assertRaisesRegex(ValueError,'Service PID'):
                    harness.NormalExitBinding(args,watcher,[300,400])
    def test_binding_rejects_wrong_or_missing_session_pid_before_process_open(self):
        with tempfile.TemporaryDirectory() as directory:
            session=Path(directory)/'offline.json'
            args=argparse.Namespace(session=session,game_pid=100,start_ticks=10)
            with patch.object(harness,'ExactExitProcess',side_effect=AssertionError('must reject before process open')):
                for value in ({'pid':999},{'pid':True},{'pid':0},{},[]):
                    session.write_text(json.dumps(value))
                    with self.assertRaisesRegex(ValueError,'session'):
                        harness.NormalExitBinding(args,{'Service':200},[300,400])
    def test_binding_whitelists_pid_and_rejects_changed_pid_without_credentials_in_proof(self):
        with tempfile.TemporaryDirectory() as directory:
            session=Path(directory)/'offline.json'
            session.write_text(json.dumps({'pid':200,'token':'NONSECRET_OFFLINE_SENTINEL','port':11111}))
            args=argparse.Namespace(session=session,game_pid=100,start_ticks=10)
            def process(pid,expected_ticks=None,names=()):return Process(pid,expected_ticks if expected_ticks is not None else pid)
            with patch.object(harness,'ExactExitProcess',side_effect=process):
                binding=harness.NormalExitBinding(args,{'Service':200},[300,400])
            self.assertNotIn('NONSECRET_OFFLINE_SENTINEL',json.dumps(binding.proof()))
            self.assertEqual(binding.proof()['ServicePID'],200)
            session.write_text(json.dumps({'pid':201,'token':'NONSECRET_OFFLINE_SENTINEL','port':11111}))
            with patch.object(harness,'session_stamp',return_value=binding.stamp):
                with self.assertRaisesRegex(ValueError,'session PID changed'):
                    binding.verify()
            binding.close()


if __name__=='__main__':
    unittest.main(verbosity=2)
