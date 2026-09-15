"""UI-independent latest-frame analysis. No camera image is written or sent."""
from dataclasses import dataclass,replace
import threading
import time
import cv2
import numpy as np
from .camera import CameraSource
from .pose import PoseEngine,PoseResult
from .stabilizer import Stabilizer,Options


@dataclass(frozen=True)
class PosePacket:
    sequence: int
    received: float
    completed: float
    frame: np.ndarray
    raw_xy: np.ndarray
    xy: np.ndarray
    scores: np.ndarray
    observed: np.ndarray
    native3d: np.ndarray | None
    inference_ms: float
    processing_ms: float
    queue_ms: float
    capture_fps: float
    analysis_fps: float
    skipped: int
    mode: str
    provider: str
    warning: str
    source_info: dict

    def to_dict(self):
        def clean(array):
            if array is None: return None
            a=np.asarray(array)
            return np.where(np.isfinite(a),a,None).tolist()
        return {'schema':'posebridge.pose.v1','sequence':self.sequence,'received_monotonic':self.received,
            'completed_monotonic':self.completed,'mode':self.mode,'provider':self.provider,
            'image_size':[self.frame.shape[1],self.frame.shape[0]],'xy_pixels':clean(self.xy),
            'raw_xy_pixels':clean(self.raw_xy),'scores':clean(self.scores),'observed':self.observed.tolist(),
            'native_3d_unvalidated':clean(self.native3d),
            'coordinates':'image pixels x right, y down; no depth in 2d; native 3d is uncalibrated',
            'inference_ms':self.inference_ms,'processing_ms':self.processing_ms,'queue_ms':self.queue_ms}


class PoseService:
    def __init__(self,config,*,source_factory=CameraSource,engine_factory=PoseEngine,synthetic=False,network_url=''):
        self.config=replace(config).validated()
        self.source_factory,self.engine_factory=source_factory,engine_factory
        self.synthetic,self.network_url=synthetic,network_url
        self.stop_event=threading.Event()
        self.lock=threading.Lock()
        self.packet=None
        self.error=''
        self.state='starting'
        self.source=None
        self.thread=threading.Thread(target=self._run,daemon=True,name='posebridge-analysis')

    def start(self): self.thread.start()
    def stop(self):
        with self.lock:self.stop_event.set()

    def latest(self,after=0):
        with self.lock:
            return self.packet if self.packet is not None and self.packet.sequence>after else None

    def _run(self):
        sequence,skipped,previous,period=0,0,None,0.
        c=self.config
        try:
            cv2.setNumThreads(1)  # avoid OpenCV/ORT oversubscribing the same CPU
            path=c.model_2d if c.mode=='2d' else c.model_3d
            engine=self.engine_factory(c) if path or self.synthetic else None
            if engine is not None:
                self.state='loading_model'
                engine.load()
            if self.stop_event.is_set(): return
            self.source=self.source_factory(c,synthetic=self.synthetic,network_url=self.network_url)
            self.source.start()
            stable=Stabilizer(Options(c.reject,c.flow,c.kalman,c.smooth,c.confidence,c.smooth_hz,c.jitter_px))
            while not self.stop_event.is_set():
                info=self.source.status()
                captured=self.source.latest(sequence)
                if captured is None:
                    self.stop_event.wait(.001)
                    continue
                skipped+=max(0,captured.sequence-sequence-1) if sequence else 0
                sequence=captured.sequence
                started=time.perf_counter()
                frame=captured.image
                factor=min(1.,c.max_edge/max(frame.shape[:2]))
                if factor<1: frame=cv2.resize(frame,(round(frame.shape[1]*factor),round(frame.shape[0]*factor)),interpolation=cv2.INTER_AREA)
                inference_start=time.perf_counter()
                pose=(engine.infer(frame) if engine is not None else
                    PoseResult(np.full((17,2),np.nan,np.float32),np.zeros(17),None,'none','model_missing'))
                inference_ms=(time.perf_counter()-inference_start)*1000
                xy,rejected=stable.update(cv2.cvtColor(frame,cv2.COLOR_BGR2GRAY),pose.xy,pose.scores,captured.received)
                observed=np.isfinite(pose.xy).all(axis=1)&np.isfinite(pose.scores)&(pose.scores>=c.confidence)&~rejected
                observed&=(pose.xy[:,0]>=0)&(pose.xy[:,0]<frame.shape[1])&(pose.xy[:,1]>=0)&(pose.xy[:,1]<frame.shape[0])
                completed=time.perf_counter()
                if previous is not None:
                    dt=completed-previous
                    period=dt if not period else .9*period+.1*dt
                previous=completed
                packet=PosePacket(sequence,captured.received,completed,frame,pose.xy,xy,pose.scores,observed,pose.native3d,
                    inference_ms,(completed-started)*1000,(started-captured.received)*1000,
                    captured.capture_fps,1/period if period else 0,skipped,c.mode,pose.provider,pose.warning,info)
                for array in (frame,pose.xy,xy,pose.scores,observed,pose.native3d):
                    if array is not None:array.setflags(write=False)
                with self.lock:
                    if self.stop_event.is_set(): break
                    self.packet=packet
                self.state='running'
        except Exception as exc:
            self.error=str(exc)
            self.state='error'
        finally:
            if self.source is not None: self.source.close()
            if not self.error: self.state='stopped'


class DemoEngine:
    """Explicit synthetic test fixture, never selected by ordinary camera startup."""
    def __init__(self,config): self.config=config; self.tick=0
    def load(self): pass
    def infer(self,frame):
        self.tick+=1
        normalized=np.float32([[.5,.18],[.47,.165],[.53,.165],[.44,.19],[.56,.19],
            [.37,.32],[.63,.32],[.29,.48],[.71,.48],[.23,.61],[.77,.61],
            [.43,.57],[.57,.57],[.42,.75],[.58,.75],[.40,.93],[.60,.93]])
        normalized[:,0]+=.07*np.sin(self.tick/12)
        normalized[9,1]-=.1*np.sin(self.tick/8)
        xy=normalized*np.float32([frame.shape[1],frame.shape[0]])
        return PoseResult(xy,np.ones(17,np.float32)*.95,None,'synthetic','SYNTHETIC DEMO / not camera inference')
