"""Explicit local camera check. Prints aggregate timing only; records no frames."""
import argparse
from pathlib import Path
import sys
import time
import numpy as np

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'src'),str(ROOT/'.runtime-deps')]


def main():
    from posebridge_lab.config import AppConfig
    from posebridge_lab.models import cached_model
    from posebridge_lab.pipeline import PoseService
    parser=argparse.ArgumentParser()
    parser.add_argument('--camera',type=int,default=0)
    parser.add_argument('--backend',choices=('DSHOW','MSMF'),default='DSHOW')
    parser.add_argument('--seconds',type=float,default=5)
    parser.add_argument('--gpu',choices=('cpu','cuda','directml'),default='cpu')
    args=parser.parse_args()
    from posebridge_lab.gpu_runtime import activate_local_runtime
    if args.gpu!='cpu':
        import os
        os.environ['POSEBRIDGE_GPU_BACKEND']=args.gpu
        activate_local_runtime()
    config=AppConfig(camera_index=args.camera,camera_backend=args.backend,model_2d=cached_model('2d'),
        gpu_enabled=args.gpu!='cpu',gpu_backend=args.gpu if args.gpu!='cpu' else 'cuda')
    if not config.model_2d:raise RuntimeError('Download a 2D model in the app first')
    service=PoseService(config)
    first=None;seq=0;rows=[];deadline=time.perf_counter()+20+args.seconds
    try:
        service.start()
        while time.perf_counter()<deadline:
            if service.error:raise RuntimeError(service.error)
            packet=service.latest(seq)
            if packet:
                seq=packet.sequence
                first=first or time.perf_counter()
                rows.append((packet.inference_ms,packet.processing_ms,packet.queue_ms,(time.perf_counter()-packet.received)*1000))
                if time.perf_counter()-first>=args.seconds:break
            time.sleep(.002)
        if len(rows)<10:raise RuntimeError(f'Insufficient frames: {len(rows)}')
        print({'updates':len(rows),'provider':packet.provider,'warning':packet.warning,
            'source':packet.source_info,'capture_fps_last':round(packet.capture_fps,1),
            'analysis_fps_last':round(packet.analysis_fps,1),'skipped':packet.skipped,
            'observed_joints_last':int(packet.observed.sum()),
            'timing_columns':['inference','processing','queue','receipt_to_consumer'],
            'median_ms':np.median(rows,axis=0).round(2).tolist(),
            'p95_ms':np.percentile(rows,95,axis=0).round(2).tolist()},flush=True)
    finally:
        service.stop();service.thread.join(3)
    if service.thread.is_alive():raise RuntimeError('Stop did not complete in 3 seconds')
    print('Stopped cleanly; no images, joint coordinates or preferences saved.',flush=True)


if __name__=='__main__':
    import multiprocessing
    multiprocessing.freeze_support()
    main()
