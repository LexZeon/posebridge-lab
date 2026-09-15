"""Single-owner camera process, one shared latest frame, bounded shutdown.

Conceptual reference: imutils WebcamVideoStream latest-frame reader (MIT).
This implementation uses independent process ownership and shared memory;
no imutils source is copied. Timestamps mean receipt, NOT sensor exposure.
"""
from dataclasses import dataclass
import multiprocessing as mp
import queue
import time
import numpy as np

CAPACITY = 1920*1080*3


@dataclass(frozen=True)
class CameraFrame:
    sequence: int
    received: float
    image: np.ndarray
    capture_fps: float


def _capture(config, pixels, header, lock, stop, messages, synthetic=False, network_url=''):
    import cv2
    cv2.setNumThreads(1)
    camera = None
    sequence, previous, period = 0, None, 0.
    try:
        if not synthetic:
            api = cv2.CAP_DSHOW if config.camera_backend == 'DSHOW' else cv2.CAP_MSMF
            if network_url:
                from .sources import validate_network_source
                source=validate_network_source(network_url)
                camera=cv2.VideoCapture(source,cv2.CAP_FFMPEG,
                    [cv2.CAP_PROP_OPEN_TIMEOUT_MSEC,5000,cv2.CAP_PROP_READ_TIMEOUT_MSEC,2500])
            else:
                camera = cv2.VideoCapture(config.camera_index, api)
            if not camera.isOpened(): raise RuntimeError('camera_open_failed')
            if not network_url:
                if config.fourcc != 'AUTO': camera.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*config.fourcc))
                camera.set(cv2.CAP_PROP_FRAME_WIDTH,config.width)
                camera.set(cv2.CAP_PROP_FRAME_HEIGHT,config.height)
                camera.set(cv2.CAP_PROP_FPS,config.fps)
            buffer_supported = camera.set(cv2.CAP_PROP_BUFFERSIZE,1)
            messages.put(('opened',{'width':int(camera.get(cv2.CAP_PROP_FRAME_WIDTH)),
                'height':int(camera.get(cv2.CAP_PROP_FRAME_HEIGHT)),
                'fps':camera.get(cv2.CAP_PROP_FPS),'backend':camera.getBackendName(),
                'buffer_request_accepted':bool(buffer_supported)}))
        else:
            messages.put(('opened',{'width':config.width,'height':config.height,'fps':config.fps,'backend':'SYNTHETIC'}))
        shared = np.frombuffer(pixels,dtype=np.uint8)
        while not stop.is_set():
            if synthetic:
                if stop.wait(1/config.fps): break
                frame = np.zeros((config.height,config.width,3),np.uint8)
                cv2.circle(frame,(int(config.width/2+config.width*.15*np.sin(sequence/12)),config.height//2),30,(65,190,230),-1)
            else:
                ok,frame = camera.read()
                if not ok or frame is None: raise RuntimeError('camera_read_failed')
            received = time.perf_counter()
            if previous is not None:
                delta = received-previous
                period = delta if period == 0 else .9*period+.1*delta
            previous = received
            if frame.ndim==2: frame=cv2.cvtColor(frame,cv2.COLOR_GRAY2BGR)
            if frame.shape[2]==4: frame=cv2.cvtColor(frame,cv2.COLOR_BGRA2BGR)
            if frame.size>CAPACITY:
                factor=min(1920/frame.shape[1],1080/frame.shape[0])
                frame=cv2.resize(frame,(round(frame.shape[1]*factor),round(frame.shape[0]*factor)))
            sequence += 1
            # Skip publication if a reader owns the slot; never queue stale images.
            if lock.acquire(timeout=.003):
                try:
                    shared[:frame.size] = frame.reshape(-1)
                    header[:] = (sequence,received,frame.shape[0],frame.shape[1],1/period if period>0 else 0.)
                finally: lock.release()
    except Exception as exc:
        messages.put(('error',str(exc)))
    finally:
        if camera is not None: camera.release()


class CameraSource:
    def __init__(self,config,*,synthetic=False,network_url=''):
        self.context=mp.get_context('spawn')
        self.pixels=self.context.RawArray('B',CAPACITY)
        self.header=self.context.RawArray('d',5)
        self.lock=self.context.Lock()
        self.stop_event=self.context.Event()
        self.messages=self.context.Queue()
        self.process=self.context.Process(target=_capture,args=(config,self.pixels,self.header,self.lock,self.stop_event,self.messages,synthetic,network_url),daemon=True)
        self.started=0.
        self.info={}

    def start(self):
        self.started=time.perf_counter()
        self.process.start()

    def latest(self,after=0):
        if not self.lock.acquire(timeout=.005): return None
        try:
            seq,stamp,h,w,fps=self.header[:]
            if seq<=after: return None
            h,w=int(h),int(w)
            image=np.frombuffer(self.pixels,dtype=np.uint8,count=h*w*3).reshape(h,w,3).copy()
            return CameraFrame(int(seq),stamp,image,fps)
        finally: self.lock.release()

    def status(self):
        while True:
            try: kind,value=self.messages.get_nowait()
            except queue.Empty: break
            if kind=='error': raise RuntimeError(value)
            self.info=value
        if self.started and not self.process.is_alive() and not self.stop_event.is_set():
            raise RuntimeError('camera_process_ended')
        if self.started and self.header[0]==0 and time.perf_counter()-self.started>10:
            raise RuntimeError('camera_open_timeout')
        if self.header[0] and time.perf_counter()-self.header[1]>3:
            raise RuntimeError('camera_stalled')
        return dict(self.info)

    def close(self):
        self.stop_event.set()
        if self.process.pid:
            self.process.join(.4)
            if self.process.is_alive():
                self.process.terminate()
                self.process.join(1.)
        self.messages.close()
