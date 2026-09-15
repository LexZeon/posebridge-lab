"""Synthetic-only visual inspection harness; never opens the camera or saves config."""
import argparse
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'src'),str(ROOT/'.runtime-deps')]


def main():
    from posebridge_lab.app import PoseBridgeApp
    from posebridge_lab.config import AppConfig
    parser=argparse.ArgumentParser()
    parser.add_argument('--language',choices=('zh','en'),default='zh')
    parser.add_argument('--tab',type=int,choices=(0,1,2),default=2)
    parser.add_argument('--avatar',action='store_true')
    parser.add_argument('--seconds',type=int,default=90)
    args=parser.parse_args()
    app=PoseBridgeApp(AppConfig(language=args.language),persist=False,demo=True)
    app.geometry('1260x850+30+30')
    app.settings_tabs.select(args.tab)
    errors=[]
    app.report_callback_exception=lambda *error:errors.append(error)
    if args.avatar:
        def open_avatar():
            app.open_avatar();app.avatar.geometry('650x760+350+60')
        app.after(1800,open_avatar)
    app.after(args.seconds*1000,app.close)
    app.mainloop()
    if errors:raise RuntimeError(errors)
    if app.service and app.service.error:raise RuntimeError(app.service.error)
    if app.last_sequence<10:raise RuntimeError('Demo produced too few frames')
    print('Synthetic UI/worker check passed; no camera or preference writes.')


if __name__=='__main__':
    import multiprocessing
    multiprocessing.freeze_support()
    main()
