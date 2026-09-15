import io
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch
import zipfile
from posebridge_lab import models


class Response(io.BytesIO):
    def __init__(self,data,url='https://download.openmmlab.com/model.zip',total=None):
        super().__init__(data);self.url=url;self.headers={'Content-Length':str(len(data) if total is None else total)}


class ModelDownloadTests(unittest.TestCase):
    def bundle(self,names=('nested/model.onnx',)):
        data=io.BytesIO()
        with zipfile.ZipFile(data,'w') as archive:
            for name in names:archive.writestr(name,b'not-a-real-model')
        return data.getvalue()

    def test_validated_download_is_atomic_and_does_not_extract_other_paths(self):
        with tempfile.TemporaryDirectory() as folder,patch.object(models,'APP_DIR',Path(folder)),patch.object(models,'urlopen',return_value=Response(self.bundle(('../../outside.onnx',)))),patch.object(models,'validate_model') as verify:
            path=Path(models.download_model('2d',threading.Event(),lambda _:None))
            self.assertEqual(path.parent,Path(folder)/'models')
            self.assertEqual(path.read_bytes(),b'not-a-real-model')
            verify.assert_called_once()
            self.assertTrue(path.with_suffix('.source.json').exists())
            self.assertEqual(len(list(path.parent.glob('*.onnx'))),1)
            self.assertEqual(list(path.parent.glob('download-*')),[])

    def test_bad_model_keeps_previous_cache_and_cleans_temporary_payload(self):
        with tempfile.TemporaryDirectory() as folder,patch.object(models,'APP_DIR',Path(folder)),patch.object(models,'urlopen',return_value=Response(self.bundle())),patch.object(models,'validate_model',side_effect=ValueError('model_dimension_mismatch')):
            target=Path(folder)/'models'/models.MODELS['2d'].name
            target.parent.mkdir();target.write_bytes(b'previous')
            with self.assertRaises(ValueError):models.download_model('2d',threading.Event(),lambda _:None)
            self.assertEqual(target.read_bytes(),b'previous')
            self.assertEqual(list(target.parent.glob('download-*')),[])

    def test_cancel_truncation_and_unexpected_host_do_not_publish(self):
        for case in ('cancel','truncated','host'):
            with self.subTest(case=case),tempfile.TemporaryDirectory() as folder,patch.object(models,'APP_DIR',Path(folder)):
                cancel=threading.Event()
                if case=='cancel':cancel.set()
                response=Response(b'x',url='https://unexpected.example/file' if case=='host' else 'https://download.openmmlab.com/file',total=10 if case=='truncated' else 1)
                with patch.object(models,'urlopen',return_value=response):
                    with self.assertRaises((ValueError,RuntimeError)):models.download_model('2d',cancel,lambda _:None)
                self.assertFalse(list((Path(folder)/'models').glob('*.onnx')))

    def test_multiple_models_are_rejected(self):
        with tempfile.TemporaryDirectory() as folder,patch.object(models,'APP_DIR',Path(folder)),patch.object(models,'urlopen',return_value=Response(self.bundle(('one.onnx','two.onnx')))):
            with self.assertRaises(ValueError):models.download_model('2d',threading.Event(),lambda _:None)
