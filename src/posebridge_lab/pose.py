"""Use upstream RTMPose preprocessing/decoding with an isolated ORT session.

Adapted architecture from LexZeon/osr-screen-tcode's pose_backends.py and
directml_pose.py (Apache-2.0); adds CPU thread control and explicit 3D output.
"""
from dataclasses import dataclass
from pathlib import Path
import numpy as np
from .models import MODELS


@dataclass(frozen=True)
class PoseResult:
    xy: np.ndarray
    scores: np.ndarray
    native3d: np.ndarray | None
    provider: str
    warning: str = ''


def create_model(model_type,path,size,device,threads):
    if device=='directml':
        from .directml_pose import create_directml_pose
        return create_directml_pose(model_type,path,size)
    import onnxruntime as ort
    from rtmlib.tools.base import BaseTool
    from .gpu_runtime import directml_session_options,preload_cuda_runtime,PROVIDERS
    if device=='cuda': preload_cuda_runtime()
    options=directml_session_options(ort) if device=='directml' else ort.SessionOptions()
    options.intra_op_num_threads=threads
    options.inter_op_num_threads=1
    options.log_severity_level=3
    provider=PROVIDERS.get(device,'CPUExecutionProvider')
    providers=[provider] if device=='cpu' else [provider,'CPUExecutionProvider']

    class SessionTool(BaseTool):
        def __init__(self,onnx_model,model_input_size,mean,std,backend,device):
            self.session=ort.InferenceSession(onnx_model,sess_options=options,providers=providers)
            if provider not in self.session.get_providers(): raise RuntimeError('GPU provider fell back to CPU')
            shape=self.session.get_inputs()[0].shape
            if len(shape)!=4 or tuple(shape[-2:])!=size[::-1]: raise ValueError('model_input_mismatch')
            self.onnx_model,self.model_input_size=onnx_model,model_input_size
            self.mean,self.std=mean,std
            self.backend,self.device=backend,device
    class AdaptedPose(model_type,SessionTool): pass
    return AdaptedPose(path,model_input_size=size,backend='onnxruntime',device=device)


class PoseEngine:
    def __init__(self,config):
        self.config=config
        self.device=config.gpu_backend if config.gpu_enabled else 'cpu'
        self.warning=''
        self.model=None

    def load(self):
        from rtmlib import RTMPose,RTMPose3d
        path=self.config.model_2d if self.config.mode=='2d' else self.config.model_3d
        if not path or not Path(path).is_file(): raise ValueError('model_missing')
        model_type=RTMPose if self.config.mode=='2d' else RTMPose3d
        def build(device): return create_model(model_type,path,MODELS[self.config.mode].input_size,device,self.config.cpu_threads)
        try: self.model=build(self.device)
        except Exception as exc:
            if self.device=='cpu': raise
            self.warning='GPU unavailable; CPU fallback: '+str(exc)
            self.device='cpu'
            self.model=build('cpu')
        if len(self.model.session.get_outputs())!=MODELS[self.config.mode].dimensions:
            raise ValueError('model_dimension_mismatch')
        shape=self.model.session.get_inputs()[0].shape
        if len(shape)!=4 or tuple(shape[-2:])!=MODELS[self.config.mode].input_size[::-1]:
            raise ValueError('model_input_mismatch')

    def infer(self,frame):
        if self.model is None: self.load()
        try: result=self.model(frame)
        except Exception as exc:
            if self.device=='cpu': raise
            # Drop this run's GPU model once. The frame is inferred once on CPU.
            self.warning='GPU inference failed; CPU fallback: '+str(exc)
            self.device='cpu'
            self.config.gpu_enabled=False
            self.load()
            result=self.model(frame)
        if self.config.mode=='2d': xy,scores=result; native=None
        else: native,scores,_,xy=result
        xy=np.asarray(xy,dtype=np.float32)
        scores=np.asarray(scores,dtype=np.float32)
        if xy.ndim!=3 or scores.ndim!=2 or len(xy)!=len(scores) or xy.shape[1]<17:
            raise ValueError('unsupported_pose_shape')
        means=np.mean(np.where(np.isfinite(scores[:,:17]),scores[:,:17],0),axis=1)
        index=int(np.argmax(means)) if len(means) else 0
        if not len(means):
            return PoseResult(np.full((17,2),np.nan,np.float32),np.zeros(17),None,self.device,self.warning)
        return PoseResult(xy[index,:17,:2].copy(),scores[index,:17].copy(),
            None if native is None else np.asarray(native[index,:17],np.float32).copy(),self.device,self.warning)
