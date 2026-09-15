"""Private, atomic preferences. Tests must set POSEBRIDGE_HOME before imports."""
from dataclasses import dataclass, asdict, fields
from pathlib import Path
import json
import math
import os
import uuid

APP_DIR = Path(os.environ.get('POSEBRIDGE_HOME', Path(os.environ.get('LOCALAPPDATA', Path.home())) / 'PoseBridgeLab'))
CONFIG_PATH = APP_DIR / 'settings.json'


@dataclass
class AppConfig:
    language: str = 'zh'
    camera_index: int = 0
    camera_backend: str = 'DSHOW'
    width: int = 640
    height: int = 480
    fps: int = 60
    fourcc: str = 'MJPG'
    mode: str = '2d'
    model_2d: str = ''
    model_3d: str = ''
    gpu_enabled: bool = False
    gpu_backend: str = 'cuda'
    cpu_threads: int = 4
    max_edge: int = 640
    confidence: float = .35
    reject: bool = True
    flow: bool = False
    kalman: bool = False
    smooth: bool = True
    smooth_hz: float = 12.
    jitter_px: float = 3.
    mirror: bool = True
    show_ids: bool = False
    overlay: bool = True

    @property
    def extra(self):
        return {'rtm_pose_gpu_backend': self.gpu_backend}

    def validated(self):
        default = AppConfig()
        result = asdict(self)
        for key, choices in {'language': ('zh','en'), 'camera_backend': ('DSHOW','MSMF'),
                             'fourcc': ('MJPG','YUY2','AUTO'), 'mode': ('2d','3d'),
                             'gpu_backend': ('cuda','directml')}.items():
            if result[key] not in choices:
                result[key] = getattr(default, key)
        limits = {'camera_index': (0,15), 'width': (160,1920), 'height': (120,1080),
                  'fps': (5,120), 'cpu_threads': (1,16), 'max_edge': (320,1280),
                  'confidence': (.1,.95), 'smooth_hz': (2,30), 'jitter_px': (0,12)}
        for key, (low, high) in limits.items():
            value = result[key]
            if isinstance(value, bool) or not isinstance(value, (int,float)) or not math.isfinite(value):
                value = getattr(default, key)
            value = max(low, min(high, value))
            result[key] = int(value) if isinstance(getattr(default,key),int) else float(value)
        for field in fields(self):
            original = getattr(default,field.name)
            if isinstance(original,bool) and not isinstance(result[field.name],bool):
                result[field.name] = original
        for key in ('model_2d','model_3d'):
            if not isinstance(result[key],str): result[key] = ''
        return AppConfig(**result)

    @classmethod
    def load(cls):
        try:
            data = json.loads(CONFIG_PATH.read_text(encoding='utf-8'))
            if not isinstance(data,dict): return cls()
            return cls(**{f.name:data[f.name] for f in fields(cls) if f.name in data}).validated()
        except (OSError, ValueError, TypeError):
            return cls()

    def save(self):
        APP_DIR.mkdir(parents=True,exist_ok=True)
        pending = APP_DIR / ('settings-'+uuid.uuid4().hex+'.tmp')
        try:
            pending.write_text(json.dumps(asdict(self.validated()),ensure_ascii=False,indent=2),encoding='utf-8')
            pending.replace(CONFIG_PATH)
        finally:
            pending.unlink(missing_ok=True)
