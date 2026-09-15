"""Explicit model downloads into private storage, never into source control."""
from dataclasses import dataclass
from pathlib import Path
import hashlib
import json
import shutil
import tempfile
from urllib.request import urlopen, Request
from urllib.parse import urlsplit
import zipfile
from .config import APP_DIR


@dataclass(frozen=True)
class ModelSpec:
    name: str
    url: str
    dimensions: int
    input_size: tuple


MODELS = {
    '2d': ModelSpec('rtmpose-s-body7.onnx',
        'https://download.openmmlab.com/mmpose/v1/projects/rtmposev1/onnx_sdk/rtmpose-s_simcc-body7_pt-body7_420e-256x192-acd4a1ef_20230504.zip',2,(192,256)),
    '3d': ModelSpec('rtmw3d-x-experimental.onnx',
        'https://huggingface.co/Soykaf/RTMW3D-x/resolve/main/onnx/rtmw3d-x_8xb64_cocktail14-384x288-b0a0eab7_20240626.onnx',3,(288,384))}


def cached_model(mode):
    path=APP_DIR/'models'/MODELS[mode].name
    return str(path) if path.is_file() else ''


def validate_model(path,mode):
    import onnxruntime as ort
    options=ort.SessionOptions()
    options.intra_op_num_threads=1
    options.inter_op_num_threads=1
    session=ort.InferenceSession(str(path),sess_options=options,providers=['CPUExecutionProvider'])
    shape=session.get_inputs()[0].shape
    spec=MODELS[mode]
    if len(shape)!=4 or shape[1]!=3 or tuple(shape[-2:])!=spec.input_size[::-1]:
        raise ValueError('model_input_mismatch')
    if len(session.get_outputs())!=spec.dimensions:
        raise ValueError('model_dimension_mismatch')
    return spec.input_size


def _allowed_redirect(url):
    p=urlsplit(url)
    host=p.hostname or ''
    return p.scheme=='https' and (host=='download.openmmlab.com' or host=='huggingface.co' or
        host.endswith('.huggingface.co') or host.endswith('.hf.co') or host.endswith('.xethub.hf.co'))


def download_model(mode,cancel,progress):
    if cancel.is_set(): raise RuntimeError('cancelled')
    spec=MODELS[mode]
    root=APP_DIR/'models'
    root.mkdir(parents=True,exist_ok=True)
    maximum=2*1024**3
    with tempfile.TemporaryDirectory(prefix='download-',dir=root) as folder:
        stage=Path(folder)
        archive=stage/'payload'
        with urlopen(Request(spec.url,headers={'User-Agent':'PoseBridge-Lab/0.1'}),timeout=25) as response:
            if not _allowed_redirect(response.url): raise ValueError('unexpected_download_source')
            total=int(response.headers.get('Content-Length',0)) or None
            if total and (total>maximum or shutil.disk_usage(root).free<total*3):
                raise RuntimeError('insufficient_disk_space')
            received=0
            with archive.open('wb') as output:
                while True:
                    if cancel.is_set(): raise RuntimeError('cancelled')
                    chunk=response.read(256*1024)
                    if not chunk: break
                    received+=len(chunk)
                    if received>maximum: raise ValueError('download_too_large')
                    output.write(chunk)
                    progress({'stage':'downloading','downloaded':received,'total':total})
            if total and received!=total: raise ValueError('truncated_download')
        candidate=stage/'model.onnx'
        if zipfile.is_zipfile(archive):
            with zipfile.ZipFile(archive) as bundle:
                entries=[e for e in bundle.infolist() if e.filename.lower().endswith('.onnx')]
                if len(entries)!=1 or entries[0].file_size>maximum: raise ValueError('invalid_model_archive')
                with bundle.open(entries[0]) as source,candidate.open('wb') as target:
                    while True:
                        if cancel.is_set(): raise RuntimeError('cancelled')
                        block=source.read(256*1024)
                        if not block: break
                        target.write(block)
        else: archive.replace(candidate)
        if cancel.is_set(): raise RuntimeError('cancelled')
        progress({'stage':'verifying'})
        validate_model(candidate,mode)
        if cancel.is_set(): raise RuntimeError('cancelled')
        digest=hashlib.sha256()
        with candidate.open('rb') as source:
            for block in iter(lambda:source.read(1024*1024),b''): digest.update(block)
        destination=root/spec.name
        candidate.replace(destination)
        destination.with_suffix('.source.json').write_text(json.dumps({'source':spec.url,'sha256':digest.hexdigest(),
            'checksum_origin':'locally computed, not upstream signed','mode':mode}),encoding='utf-8')
        return str(destination)
