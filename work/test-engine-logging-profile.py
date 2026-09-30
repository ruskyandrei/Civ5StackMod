"""Actual helper parse/apply/restore regressions using isolated temporary files.

Never reads or writes the user's Civ configuration and never queries/controls the
game. Process guards use supplied fixture inventories. No DLL or native compile.
"""
from pathlib import Path
import importlib.util,json,tempfile,unittest
root=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('engine_logging_profile',root/'work/engine-logging-profile.py')
helper=importlib.util.module_from_spec(spec);spec.loader.exec_module(helper)
BASE=b'; local fixture\r\n[Debug]\r\nLoggingEnabled = 1\r\nMessageLog = 1\r\nAILog = 1\r\nAIPerfLog = 1 ; timings\r\nBuilderAILog = 1\r\nUnrelatedSecret = do-not-print-this\r\n'
OFF=BASE.replace(b'AILog = 1',b'AILog = 0').replace(b'AIPerfLog = 1',b'AIPerfLog = 0')
ALLOW=lambda:helper.require_game_off(['python.exe','powershell.exe','chrome.exe'])

class ProfileTests(unittest.TestCase):
    def test_exact_roundtrip_encodings_and_styles(self):
        styles=[BASE,BASE.replace(b'\r\n',b'\n').rstrip(b'\n'),BASE.replace(b'AILog = 1',b'ailOG\t=\t1# preserved')]
        for raw in styles:
            native,before,after=helper.native_only_bytes(raw)
            self.assertEqual({name:after[name] for name in helper.LEGACY},{name:0 for name in helper.LEGACY})
            for name in ('LoggingEnabled','MessageLog'):self.assertEqual(before[name],after[name])
            self.assertEqual(len(raw),len(native));self.assertEqual(sum(a!=b for a,b in zip(raw,native)),3)
        text=BASE.decode('ascii')+'OtherUnicode = 漢字\r\n'
        for bom,encoding in ((b'\xef\xbb\xbf','utf-8'),(b'\xff\xfe','utf-16-le'),(b'\xfe\xff','utf-16-be')):
            raw=bom+text.encode(encoding);native,before,after=helper.native_only_bytes(raw)
            expected=text.replace('AILog = 1','AILog = 0').replace('AIPerfLog = 1','AIPerfLog = 0')
            self.assertEqual(native,bom+expected.encode(encoding));self.assertEqual(before['MessageLog'],after['MessageLog'])
        raw=BASE+b'OtherANSI = \x80\xff\r\n';self.assertTrue(helper.native_only_bytes(raw)[0].endswith(b'OtherANSI = \x80\xff\r\n'))
    def test_strict_keys_reject_duplicates_missing_and_invalid(self):
        bad=[BASE+b'AILog=0\n',BASE+b'ailog = 1\n',BASE.replace(b'AILog = 1\r',b'OtherLog = 1\r'),BASE.replace(b'AILog = 1\r',b'AILog = 2\r'),BASE.replace(b'AILog = 1\r',b'AILog = 10\r'),BASE.replace(b'AILog = 1\r',b'AILog = 1 0\r'),BASE.replace(b'AILog = 1\r',b'AILog = true\r'),b'\xff\xfe'+b'x',BASE+b'\x00']
        for raw in bad:
            with self.subTest(raw=raw[-20:]),self.assertRaises(helper.ProfileError):helper.native_only_bytes(raw)
    def test_comments_do_not_create_keys(self):
        raw=b'; AILog = 0\r\n# BuilderAILog = 0\r\nOtherAILog = 0\r\n'+BASE
        native,before,after=helper.native_only_bytes(raw);self.assertEqual(before['AILog'],1);self.assertTrue(native.startswith(raw[:raw.index(BASE)]))
    def test_process_guard_and_bridge(self):
        ALLOW();helper.require_game_off(['CivilizationVI.exe','TunerServicePython.exe'])
        for name in ('CivilizationV.exe','CivilizationV_DX11.exe','CivilizationV_DX9.exe','Civilization5.exe','CivilizationV_Tablet.exe','FireTuner.exe','firetuner2.exe'):
            with self.subTest(name=name),self.assertRaises(helper.ProfileError):helper.require_game_off([name])
    def test_byte_exact_backup_apply_restore_and_idempotence(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory=Path(temporary);config=directory/'config.ini';config.write_bytes(BASE);run=directory/'run'
            result=helper.apply_native_only(config,run,ALLOW)
            self.assertEqual(config.read_bytes(),OFF);self.assertEqual((run/helper.BACKUP_NAME).read_bytes(),BASE)
            self.assertEqual(result['baseline']['sha256'],helper.sha256(BASE));self.assertEqual(result['applied']['sha256'],helper.sha256(OFF))
            self.assertNotIn('do-not-print-this',json.dumps(result));self.assertEqual(result['changed_keys'],list(helper.LEGACY))
            restored=helper.restore(config,run,ALLOW);self.assertEqual(config.read_bytes(),BASE);self.assertEqual(restored['status'],'restored')
            self.assertEqual(helper.restore(config,run,ALLOW)['status'],'restored');self.assertEqual(config.read_bytes(),BASE)
    def test_live_game_guard_has_no_config_or_backup_write(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory=Path(temporary);config=directory/'config.ini';config.write_bytes(BASE);run=directory/'run'
            with self.assertRaises(helper.ProfileError):helper.apply_native_only(config,run,lambda:helper.require_game_off(['CivilizationV_DX11.exe']))
            self.assertEqual(config.read_bytes(),BASE);self.assertFalse(run.exists())
    def test_second_guard_refuses_game_start_between_backup_and_write(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory=Path(temporary);config=directory/'config.ini';config.write_bytes(BASE);run=directory/'run';calls=[0]
            def guard():
                calls[0]+=1;helper.require_game_off([] if calls[0]==1 else ['CivilizationV.exe'])
            with self.assertRaises(helper.ProfileError):helper.apply_native_only(config,run,guard)
            self.assertEqual(config.read_bytes(),BASE);self.assertEqual((run/helper.BACKUP_NAME).read_bytes(),BASE)
    def test_restore_concurrent_user_edits_refused(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory=Path(temporary);config=directory/'config.ini';config.write_bytes(BASE);run=directory/'run'
            helper.apply_native_only(config,run,ALLOW);changed=config.read_bytes()+b'UserNewOption=1\n';config.write_bytes(changed)
            with self.assertRaises(helper.ProfileError):helper.restore(config,run,ALLOW)
            self.assertEqual(config.read_bytes(),changed);self.assertEqual((run/helper.BACKUP_NAME).read_bytes(),BASE)
    def test_backup_tamper_and_wrong_target_refused(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory=Path(temporary);config=directory/'config.ini';config.write_bytes(BASE);run=directory/'run'
            helper.apply_native_only(config,run,ALLOW);other=directory/'other.ini';other.write_bytes(OFF)
            with self.assertRaises(helper.ProfileError):helper.restore(other,run,ALLOW)
            self.assertEqual(other.read_bytes(),OFF);(run/helper.BACKUP_NAME).write_bytes(BASE+b'Changed=1\n')
            with self.assertRaises(helper.ProfileError):helper.restore(config,run,ALLOW)
            self.assertEqual(config.read_bytes(),OFF)
    def test_nonfresh_and_already_native_profiles_refused(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory=Path(temporary);config=directory/'config.ini';config.write_bytes(BASE);run=directory/'run';run.mkdir();(run/'user.txt').write_text('owned')
            with self.assertRaises(helper.ProfileError):helper.apply_native_only(config,run,ALLOW)
            self.assertEqual(config.read_bytes(),BASE);config.write_bytes(OFF)
            with self.assertRaises(helper.ProfileError):helper.apply_native_only(config,directory/'fresh',ALLOW)
            self.assertEqual(config.read_bytes(),OFF);self.assertFalse((directory/'fresh').exists())
    def test_atomic_prewrite_hash_check_preserves_concurrent_edit(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory=Path(temporary);config=directory/'config.ini';config.write_bytes(BASE);changed=BASE+b'UserEdit=1\n';config.write_bytes(changed)
            with self.assertRaises(helper.ProfileError):helper.atomic_write(config,OFF,helper.sha256(BASE))
            self.assertEqual(config.read_bytes(),changed);self.assertEqual(list(directory.glob('*.tmp')),[])
    def test_restore_game_guard_refuses_write(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory=Path(temporary);config=directory/'config.ini';config.write_bytes(BASE);run=directory/'run';helper.apply_native_only(config,run,ALLOW)
            with self.assertRaises(helper.ProfileError):helper.restore(config,run,lambda:helper.require_game_off(['FireTuner.exe']))
            self.assertEqual(config.read_bytes(),OFF)

if __name__=='__main__':unittest.main(verbosity=1)
