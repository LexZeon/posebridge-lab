from dataclasses import replace
import json
from pathlib import Path
import tempfile
import threading
import time
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import numpy as np
from posebridge_lab.config import AppConfig
from posebridge_lab import config
from posebridge_lab.camera import CameraSource,CameraFrame
from posebridge_lab.pipeline import PoseService,DemoEngine
from posebridge_lab.sources import validate_network_source
from posebridge_lab.render import mannequin_points,skeleton_image


class SettingsTests(unittest.TestCase):
    def test_round_trip_and_defaults_are_isolated_and_validated(self):
        with tempfile.TemporaryDirectory() as folder,patch.object(config,'APP_DIR',Path(folder)),patch.object(config,'CONFIG_PATH',Path(folder)/'settings.json'):
            chosen=AppConfig(mode='3d',gpu_enabled=True,gpu_backend='directml',fps=90,max_edge=960,confidence=.55,flow=True,smooth_hz=19,jitter_px=5)
            chosen.save()
            self.assertEqual(AppConfig.load(),chosen)
            AppConfig().save();self.assertEqual(AppConfig.load(),AppConfig())
            self.assertEqual(list(Path(folder).glob('*.tmp')),[])
        c=AppConfig(fps=float('nan'),confidence='bad',gpu_enabled='false',width=99999,mode='x').validated()
        self.assertEqual(c.fps,60);self.assertEqual(c.confidence,.35);self.assertFalse(c.gpu_enabled)
        self.assertEqual(c.width,1920);self.assertEqual(c.mode,'2d')

    def test_network_rejects_files_and_keeps_credentials_out_of_saved_settings(self):
        for url in ('file:///private','camera.mp4','http:///missing','\\\\server\\share'):
            with self.assertRaises(ValueError):validate_network_source(url)
        self.assertEqual(validate_network_source('rtsp://host:554/live'),'rtsp://host:554/live')
        self.assertNotIn('url',AppConfig.__dataclass_fields__)


class CaptureTests(unittest.TestCase):
    def test_one_slot_skips_backlog_owns_pixels_and_stops_process(self):
        source=CameraSource(AppConfig(width=320,height=240,fps=90),synthetic=True)
        try:
            source.start();deadline=time.perf_counter()+8
            first=None
            while time.perf_counter()<deadline:
                first=source.latest()
                if first:break
                time.sleep(.02)
            self.assertIsNotNone(first)
            unchanged=first.image.copy()
            time.sleep(.16)
            latest=source.latest(first.sequence)
            self.assertGreater(latest.sequence,first.sequence+1)
            np.testing.assert_array_equal(first.image,unchanged)
            self.assertEqual(latest.image.shape,(240,320,3))
        finally:source.close()
        self.assertFalse(source.process.is_alive())

    def test_read_wait_cannot_lock_the_ui_forever(self):
        source=CameraSource(AppConfig(),synthetic=True)
        source.lock.acquire()
        started=time.perf_counter()
        try:self.assertIsNone(source.latest())
        finally:source.lock.release();source.close()
        self.assertLess(time.perf_counter()-started,.15)


class FixtureSource:
    def __init__(self,c,**kwargs):self.seq=0;self.closed=False;self.origin=time.perf_counter()
    def start(self):pass
    def status(self):return {'backend':'FIXTURE','width':320,'height':240}
    def latest(self,after):
        self.seq+=1
        return CameraFrame(self.seq,time.perf_counter(),np.zeros((240,320,3),np.uint8),60)
    def close(self):self.closed=True


class PipelineTests(unittest.TestCase):
    def packet(self):
        service=PoseService(AppConfig(),source_factory=FixtureSource,engine_factory=DemoEngine,synthetic=True)
        service.start();deadline=time.perf_counter()+3
        while service.latest() is None and time.perf_counter()<deadline:time.sleep(.01)
        service.stop();service.thread.join(2)
        self.assertFalse(service.thread.is_alive());self.assertEqual(service.error,'')
        self.assertTrue(service.source.closed)
        return service.latest()

    def test_schema_contains_no_images_no_fake_2d_depth_and_finite_json(self):
        packet=self.packet();data=packet.to_dict()
        self.assertEqual(data['schema'],'posebridge.pose.v1')
        self.assertIsNone(data['native_3d_unvalidated'])
        self.assertNotIn('image',data)
        self.assertEqual(len(data['xy_pixels']),17)
        json.dumps(data,allow_nan=False)
        missing=replace(packet,xy=np.full((17,2),np.nan),scores=np.full(17,np.nan))
        self.assertIsNone(missing.to_dict()['xy_pixels'][0][0])
        json.dumps(missing.to_dict(),allow_nan=False)

    def test_avatar_and_mirror_do_not_modify_analysis_and_missing_torso_hides(self):
        packet=self.packet();original=packet.xy.copy()
        model=mannequin_points(packet)
        self.assertTrue(np.all(model[:,2]==0))
        mirrored=mannequin_points(packet,True)
        np.testing.assert_allclose(model[:,0],-mirrored[:,0])
        skeleton_image(packet,mirror=True,show_ids=True)
        np.testing.assert_array_equal(packet.xy,original)
        self.assertIsNone(mannequin_points(replace(packet,xy=np.full((17,2),np.nan))))

    def test_stop_during_inference_does_not_publish_late_result(self):
        entered=threading.Event();release=threading.Event()
        class Slow(DemoEngine):
            def infer(self,frame):entered.set();release.wait(2);return super().infer(frame)
        service=PoseService(AppConfig(),source_factory=FixtureSource,engine_factory=Slow,synthetic=True)
        service.start();self.assertTrue(entered.wait(2))
        service.stop();release.set();service.thread.join(2)
        self.assertIsNone(service.latest());self.assertTrue(service.source.closed)

    def test_missing_model_is_explicit_camera_only_without_generated_joints(self):
        service=PoseService(AppConfig(),source_factory=FixtureSource)
        service.start();deadline=time.perf_counter()+2
        while service.latest() is None and time.perf_counter()<deadline:time.sleep(.01)
        service.stop();service.thread.join(2)
        packet=service.latest()
        self.assertEqual(packet.warning,'model_missing');self.assertFalse(packet.observed.any())
        self.assertFalse(np.isfinite(packet.xy).any())


class UiTests(unittest.TestCase):
    def test_bilingual_restore_paths_avatar_and_close_do_not_write_personal_config(self):
        from posebridge_lab.app import PoseBridgeApp
        for language in ('zh','en'):
            with self.subTest(language=language),patch.object(AppConfig,'save') as save:
                app=PoseBridgeApp(AppConfig(language=language),persist=False)
                try:
                    app.update_idletasks()
                    app.vars['mode'].set('3d');app.mode_changed()
                    self.assertIn('3D',app.notice.get())
                    app.vars['fps'].set(90);app.vars['flow'].set(True)
                    app.restore()
                    self.assertEqual(app.vars['fps'].get(),60)
                    self.assertEqual(app.vars['mode'].get(),'2d')
                    self.assertFalse(app.vars['flow'].get())
                    app.open_avatar();self.assertTrue(app.avatar.winfo_exists())
                    app.close();app._finish_close()
                    save.assert_not_called()
                finally:
                    try:app.destroy()
                    except Exception:pass
