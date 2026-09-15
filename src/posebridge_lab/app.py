"""Windows developer workbench. Tk is touched only by the UI thread."""
from dataclasses import asdict,replace
import json
import queue
import threading
import time
from pathlib import Path
import tkinter as tk
from tkinter import ttk,filedialog,messagebox
import cv2
import numpy as np
from PIL import Image,ImageTk
from . import APP_NAME,__version__
from .config import AppConfig
from .models import cached_model,download_model
from .pipeline import PoseService,DemoEngine
from .render import skeleton_image,draw_mannequin

JOINTS=('nose','left eye','right eye','left ear','right ear','left shoulder','right shoulder',
        'left elbow','right elbow','left wrist','right wrist','left hip','right hip',
        'left knee','right knee','left ankle','right ankle')
JOINTS_ZH=('鼻','左眼','右眼','左耳','右耳','左肩','右肩','左肘','右肘','左腕','右腕','左胯','右胯','左膝','右膝','左踝','右踝')


class PoseBridgeApp(tk.Tk):
    def __init__(self,config=None,*,persist=False,demo=False):
        super().__init__()
        self.config_value=(config or AppConfig.load()).validated()
        self.persist,self.demo=persist,demo
        self.language=self.config_value.language
        self.title(f'{APP_NAME} {__version__}'+(' — SYNTHETIC DEMO' if demo else ''))
        self.geometry('1260x850')
        self.minsize(1000,700)
        self.protocol('WM_DELETE_WINDOW',self.close)
        self.service=None
        self.last_packet=None
        self.last_sequence=0
        self.events=queue.Queue()
        self.job=None
        self.cancel_job=threading.Event()
        self.closing=False
        self.avatar=None
        self.arrival_ages=[]
        self.callbacks=[]
        self.vars={}
        for key,value in asdict(self.config_value).items():
            kind=tk.BooleanVar if isinstance(value,bool) else tk.IntVar if isinstance(value,int) else tk.DoubleVar if isinstance(value,float) else tk.StringVar
            self.vars[key]=kind(self,value=value)
        for mode in ('2d','3d'):
            key='model_'+mode
            if not self.vars[key].get() and not demo: self.vars[key].set(cached_model(mode))
        self.url=tk.StringVar(self)
        self.source_type=tk.StringVar(self,value='Camera')
        self.source_choice=tk.StringVar(self)
        self.model_path=tk.StringVar(self)
        self.mode_choice=tk.StringVar(self)
        self.sources=[]
        self.status=tk.StringVar(self,value=self.t('就绪：先检测输入来源','Ready: detect input sources'))
        self.progress_text=tk.StringVar(self,value='')
        self.metrics=tk.StringVar(self,value='—')
        self.notice=tk.StringVar(self,value='')
        self._build()
        self.mode_changed()
        self.poll_id=self.after(16,self.poll)
        if demo: self.after(250,self.start)

    def t(self,zh,en): return zh if self.language=='zh' else en

    def _build(self):
        style=ttk.Style(self)
        style.theme_use('clam')
        style.configure('.',font=('Segoe UI',10))
        style.configure('Title.TLabel',font=('Segoe UI',18,'bold'))
        style.configure('Run.TButton',font=('Segoe UI',11,'bold'),padding=8)
        header=ttk.Frame(self,padding=(14,10));header.pack(fill='x')
        ttk.Label(header,text=APP_NAME,style='Title.TLabel').pack(side='left')
        ttk.Label(header,text=self.t('摄像头姿态开发工作台','Camera pose developer workbench'),padding=(20,0)).pack(side='left')
        language=ttk.Combobox(header,values=('中文','English'),state='readonly',width=9)
        language.set('中文' if self.language=='zh' else 'English');language.pack(side='right')
        language.bind('<<ComboboxSelected>>',lambda e:self.switch_language('zh' if language.get()=='中文' else 'en'))
        body=ttk.Panedwindow(self,orient='horizontal');body.pack(fill='both',expand=True,padx=12,pady=(0,8))
        side=ttk.Frame(body,width=350,padding=8);body.add(side,weight=0)
        right=ttk.Frame(body,padding=(8,0));body.add(right,weight=1)
        tabs=ttk.Notebook(side);tabs.pack(fill='both',expand=True)
        self.settings_tabs=tabs
        source=ttk.Frame(tabs,padding=10);model=ttk.Frame(tabs,padding=10);tuning=ttk.Frame(tabs,padding=10)
        for frame,title in ((source,self.t('输入来源','Input')),(model,self.t('模型 / GPU','Model / GPU')),(tuning,self.t('效果优化','Tuning'))): tabs.add(frame,text=title)
        for frame in (source,model,tuning): frame.columnconfigure(1,weight=1)
        self.combo(source,0,self.t('输入类型','Input type'),self.source_type,('Camera','Network'))
        self.source_box=ttk.Combobox(source,textvariable=self.source_choice,state='readonly',width=32)
        self.source_box.grid(row=1,column=0,columnspan=2,sticky='ew',pady=5)
        self.source_box.bind('<<ComboboxSelected>>',self.source_selected)
        ttk.Button(source,text=self.t('检测输入来源','Detect sources'),command=self.scan_sources).grid(row=2,column=0,columnspan=2,sticky='ew',pady=4)
        self.combo(source,3,self.t('采集接口','Capture backend'),self.vars['camera_backend'],('DSHOW','MSMF'))
        self.source_box.bind('<Button-1>',lambda e:None,add=True)
        self.entry(source,4,self.t('摄像头编号','Camera index'),self.vars['camera_index'])
        dimensions=ttk.Frame(source);dimensions.grid(row=5,column=0,columnspan=2,sticky='ew',pady=6)
        ttk.Label(dimensions,text=self.t('申请尺寸','Requested size')).pack(side='left')
        ttk.Spinbox(dimensions,from_=160,to=1920,textvariable=self.vars['width'],width=6).pack(side='left',padx=(12,3))
        ttk.Label(dimensions,text='×').pack(side='left')
        ttk.Spinbox(dimensions,from_=120,to=1080,textvariable=self.vars['height'],width=6).pack(side='left',padx=3)
        self.slider(source,6,self.t('申请 FPS','Requested FPS'),'fps',5,120)
        self.combo(source,8,self.t('像素格式','Pixel format'),self.vars['fourcc'],('MJPG','YUY2','AUTO'))
        ttk.Separator(source).grid(row=9,column=0,columnspan=2,sticky='ew',pady=12)
        ttk.Label(source,text=self.t('无线 / 手机网络画面地址','Wireless / phone stream URL')).grid(row=10,column=0,columnspan=2,sticky='w')
        ttk.Entry(source,textvariable=self.url,width=30).grid(row=11,column=0,columnspan=2,sticky='ew',pady=5)
        ttk.Label(source,text=self.t('支持 RTSP / HTTP(S) 视频流。地址仅本次会话使用。\n系统已连接的手机 / 虚拟摄像头会列在上方。\n蓝牙配对本身不等于视频接口。','RTSP / HTTP(S) streams; URL is session-only.\nSystem-connected phone / virtual webcams appear above.\nBluetooth pairing alone is not a video interface.'),wraplength=300,foreground='#555').grid(row=12,column=0,columnspan=2,sticky='w',pady=6)
        ttk.Button(source,text=self.t('手机摄像头接入说明','Phone camera guide'),command=self.phone_help).grid(row=13,column=0,columnspan=2,sticky='ew')
        ttk.Label(source,text=self.t('申请值不一定等于实际值；右侧显示实测帧率。','Requested format may differ; measured FPS appears on the right.'),wraplength=300,foreground='#555').grid(row=14,column=0,columnspan=2,pady=14)
        mode_box=self.combo(model,0,self.t('分析方式','Analysis'),self.mode_choice,('RTM Pose 2D',self.t('RTM Pose 3D（实验）','RTM Pose 3D (experimental)')))
        def select_mode(event):
            self.vars['model_'+self.vars['mode'].get()].set(self.model_path.get().strip())
            self.vars['mode'].set('3d' if '3D' in self.mode_choice.get() else '2d')
            self.mode_changed()
        mode_box.bind('<<ComboboxSelected>>',select_mode)
        ttk.Label(model,textvariable=self.notice,wraplength=300,foreground='#8a5200').grid(row=1,column=0,columnspan=2,sticky='w',pady=8)
        ttk.Entry(model,textvariable=self.model_path,width=30).grid(row=2,column=0,columnspan=2,sticky='ew')
        ttk.Button(model,text=self.t('选择 ONNX 模型','Choose ONNX model'),command=self.choose_model).grid(row=3,column=0,sticky='ew',pady=5)
        ttk.Button(model,text=self.t('下载 / 检测模型','Download / detect'),command=self.fetch_model).grid(row=3,column=1,sticky='ew',padx=(5,0))
        ttk.Label(model,text='OpenMMLab RTMPose / rtmlib\n2D: RTMPose-s, 192 × 256\n3D: RTMW3D-x, 288 × 384',foreground='#555').grid(row=4,column=0,columnspan=2,sticky='w',pady=8)
        ttk.Separator(model).grid(row=5,column=0,columnspan=2,sticky='ew',pady=10)
        ttk.Checkbutton(model,text=self.t('启用 GPU 加速','Enable GPU acceleration'),variable=self.vars['gpu_enabled']).grid(row=6,column=0,columnspan=2,sticky='w')
        self.combo(model,7,self.t('GPU 引擎','GPU engine'),self.vars['gpu_backend'],('cuda','directml'))
        ttk.Button(model,text=self.t('一键配置 GPU','Set up GPU'),command=lambda:self.gpu_task(True)).grid(row=8,column=0,sticky='ew',pady=6)
        ttk.Button(model,text=self.t('检测 GPU','Check GPU'),command=lambda:self.gpu_task(False)).grid(row=8,column=1,sticky='ew',padx=(5,0))
        ttk.Label(model,text=self.t('CUDA：NVIDIA；DirectML：Windows GPU。\n安装在本软件私有目录，完成后重启软件。\n系统显卡驱动需事先可用。','CUDA: NVIDIA; DirectML: Windows GPUs.\nPrivate runtime install; restart afterward.\nA working graphics driver is required.'),wraplength=300,foreground='#555').grid(row=9,column=0,columnspan=2,sticky='w',pady=6)
        self.slider(model,10,self.t('CPU 推理线程','CPU inference threads'),'cpu_threads',1,16)
        preset=ttk.Frame(tuning);preset.grid(row=0,column=0,columnspan=2,sticky='ew',pady=5)
        for title,name in ((self.t('低延迟','Low latency'),'fast'),(self.t('稳定','Stable'),'stable'),(self.t('原始','Raw'),'raw')):
            ttk.Button(preset,text=title,command=lambda n=name:self.preset(n)).pack(side='left',expand=True,fill='x')
        self.slider(tuning,1,self.t('处理最长边','Processing long edge'),'max_edge',320,1280)
        self.slider(tuning,3,self.t('关键点置信门槛','Keypoint threshold'),'confidence',.1,.95)
        for row,key,zh,en in ((5,'reject','异常过滤','Outlier rejection'),(6,'flow','光流辅助','Optical-flow assist'),(7,'kalman','卡尔曼融合','Kalman fusion'),(8,'smooth','微抖平滑','Micro-jitter smoothing')):
            ttk.Checkbutton(tuning,text=self.t(zh,en),variable=self.vars[key]).grid(row=row,column=0,columnspan=2,sticky='w',pady=5)
        self.slider(tuning,9,self.t('平滑响应 Hz（越高越灵敏）','Smoothing Hz (higher = faster)'),'smooth_hz',2,30)
        self.slider(tuning,11,self.t('微抖范围 / 像素','Micro-jitter radius / px'),'jitter_px',0,12)
        for row,key,zh,en in ((13,'mirror','镜像显示（不修改数据）','Mirror display (data unchanged)'),(14,'show_ids','显示关键点编号','Show joint IDs'),(15,'overlay','骨架叠加原画面','Overlay on image')):
            ttk.Checkbutton(tuning,text=self.t(zh,en),variable=self.vars[key]).grid(row=row,column=0,columnspan=2,sticky='w',pady=5)
        ttk.Label(tuning,text=self.t('分析参数在下次开始时生效。\n镜像 / 编号 / 叠加立即作用于显示。','Analysis settings apply on next start.\nDisplay options apply immediately.'),wraplength=300,foreground='#555').grid(row=16,column=0,columnspan=2,pady=10)
        ttk.Button(side,text=self.t('开始摄像头分析','Start camera analysis'),style='Run.TButton',command=self.start).pack(fill='x',pady=(10,3))
        actions=ttk.Frame(side);actions.pack(fill='x')
        ttk.Button(actions,text=self.t('停止','Stop'),command=self.stop).pack(side='left',expand=True,fill='x')
        ttk.Button(actions,text=self.t('人物模型预览','Avatar preview'),command=self.open_avatar).pack(side='left',expand=True,fill='x',padx=(5,0))
        actions=ttk.Frame(side);actions.pack(fill='x',pady=(6,0))
        ttk.Button(actions,text=self.t('恢复默认','Restore defaults'),command=self.restore).pack(side='left',expand=True,fill='x')
        ttk.Button(actions,text=self.t('保存设置','Save settings'),command=self.save).pack(side='left',expand=True,fill='x',padx=(5,0))
        ttk.Label(right,textvariable=self.status,font=('Segoe UI',11,'bold'),wraplength=750).pack(fill='x',pady=6)
        ttk.Label(right,textvariable=self.metrics,wraplength=760,justify='left').pack(fill='x',pady=(0,8))
        self.view_tabs=ttk.Notebook(right);self.view_tabs.pack(fill='both',expand=True)
        preview=ttk.Frame(self.view_tabs);data=ttk.Frame(self.view_tabs);help_tab=ttk.Frame(self.view_tabs,padding=15)
        self.view_tabs.add(preview,text=self.t('分析预览','Analysis preview'));self.view_tabs.add(data,text=self.t('关键点数据','Joint data'));self.view_tabs.add(help_tab,text=self.t('说明 / 来源','About / Sources'))
        preview.rowconfigure(1,weight=1)
        for col in (0,1): preview.columnconfigure(col,weight=1,uniform='image')
        self.image_labels=[]
        for col,label in enumerate((self.t('原画面 · 与骨架同帧','Source · same frame as pose'),self.t('分析结果 · 绿为观测 / 灰为暂保持','Pose · green observed / grey held'))):
            ttk.Label(preview,text=label,anchor='center').grid(row=0,column=col,sticky='ew',pady=7)
            widget=tk.Label(preview,bg='#17232d',fg='#aebcc6',text=self.t('等待摄像头','Waiting for camera'))
            widget.grid(row=1,column=col,sticky='nsew',padx=3,pady=(0,3));self.image_labels.append(widget)
        self.tree=ttk.Treeview(data,columns=('joint','x','y','score','state'),show='headings')
        for key,title,width in (('joint',self.t('关键点','Joint'),150),('x','X',85),('y','Y',85),('score',self.t('置信度','Score'),85),('state',self.t('状态','State'),110)):
            self.tree.heading(key,text=title);self.tree.column(key,width=width,anchor='center')
        self.tree.pack(fill='both',expand=True)
        for i in range(17): self.tree.insert('', 'end',iid=str(i),values=(f'{i} {JOINTS_ZH[i] if self.language=="zh" else JOINTS[i]}','—','—','—','—'))
        ttk.Button(data,text=self.t('导出当前姿态 JSON（不含图像）','Export current pose JSON (no image)'),command=self.export_packet).pack(fill='x',pady=6)
        explanation=self.t('仅做摄像头视觉分析；当前为单人全画面 RTMPose。\n请让一个人的全身尽量在画面中。未接入多人检测器。\n\n“收到帧→显示”从软件收到图像后计时，\n不包含摄像头曝光、硬件缓冲和屏幕刷新。\n\n开源使用 / 借鉴：\n• OpenMMLab MMPose / Tau-J rtmlib：Pose 推理\n• OpenCV：DirectShow / MSMF / 网络视频采集\n• cv2_enumerate_cameras：系统摄像头枚举\n• LexZeon/osr-screen-tcode test.22：稳定与 GPU 管理\n• imutils WebcamVideoStream：只保留最新帧的设计参考\n\n人物模型是可视化调试模型，2D 没有真实深度。\n未完成游戏角色重定向、IK 或接触约束。\n详见 README、THIRD_PARTY_NOTICES 和 docs。',
            'Camera vision only; single-person full-frame RTMPose.\nKeep one full body in frame. No multi-person detector.\n\nReceipt-to-UI age starts after software receives a frame;\nit excludes exposure, driver buffering and screen scan-out.\n\nOpen-source use / references:\n• OpenMMLab MMPose / Tau-J rtmlib: pose inference\n• OpenCV: DirectShow / MSMF / network capture\n• cv2_enumerate_cameras: system source enumeration\n• LexZeon/osr-screen-tcode test.22: filters and GPU tools\n• imutils WebcamVideoStream: latest-frame design reference\n\nThe mannequin is a debug visualization; 2D has no measured depth.\nGame retargeting, IK and contact constraints are future work.\nSee README, THIRD_PARTY_NOTICES and docs.')
        ttk.Label(help_tab,text=explanation,wraplength=720,justify='left').pack(anchor='nw')
        footer=ttk.Frame(self,padding=(12,4));footer.pack(fill='x')
        ttk.Label(footer,textvariable=self.progress_text,wraplength=960).pack(side='left',fill='x',expand=True)
        self.progress=ttk.Progressbar(footer,length=180);self.progress.pack(side='left',padx=8)
        ttk.Button(footer,text=self.t('取消下载 / 检测','Cancel task'),command=self.cancel_job.set).pack(side='right')

    def combo(self,parent,row,label,var,values):
        ttk.Label(parent,text=label).grid(row=row,column=0,sticky='w',pady=5)
        box=ttk.Combobox(parent,textvariable=var,values=values,state='readonly',width=14)
        box.grid(row=row,column=1,sticky='ew',pady=5)
        return box

    def entry(self,parent,row,label,var):
        ttk.Label(parent,text=label).grid(row=row,column=0,sticky='w',pady=5)
        ttk.Entry(parent,textvariable=var,width=12).grid(row=row,column=1,sticky='ew',pady=5)

    def slider(self,parent,row,label,key,low,high):
        value=tk.StringVar(self)
        def update(*_):
            try: value.set(f'{self.vars[key].get():.2f}'.rstrip('0').rstrip('.') if isinstance(self.vars[key],tk.DoubleVar) else str(self.vars[key].get()))
            except tk.TclError: value.set('—')
        self.vars[key].trace_add('write',update);update()
        ttk.Label(parent,text=label).grid(row=row,column=0,sticky='w',pady=(7,0))
        ttk.Label(parent,textvariable=value,anchor='e').grid(row=row,column=1,sticky='e')
        def change(v): self.vars[key].set(round(float(v)) if isinstance(self.vars[key],tk.IntVar) else round(float(v),2))
        ttk.Scale(parent,from_=low,to=high,variable=self.vars[key],command=change).grid(row=row+1,column=0,columnspan=2,sticky='ew',pady=(2,7))

    def read_config(self):
        self.vars['model_'+self.vars['mode'].get()].set(self.model_path.get().strip())
        return AppConfig(**{key:value.get() for key,value in self.vars.items()}).validated()

    def mode_changed(self):
        mode=self.vars['mode'].get()
        self.mode_choice.set('RTM Pose 2D' if mode=='2d' else self.t('RTM Pose 3D（实验）','RTM Pose 3D (experimental)'))
        self.model_path.set(self.vars['model_'+mode].get())
        self.notice.set(self.t('RTM Pose 2D：推荐，沿用原项目模型。','RTM Pose 2D: recommended, same model as OSR.') if mode=='2d' else
            self.t('RTM Pose 3D / RTMW3D：实验选项，尚未调试。模型较大。','RTM Pose 3D / RTMW3D: unvalidated experiment. Large model.'))

    def choose_model(self):
        path=filedialog.askopenfilename(parent=self,filetypes=[('ONNX model','*.onnx')])
        if path:
            self.model_path.set(path);self.vars['model_'+self.vars['mode'].get()].set(path)

    def save(self):
        try:
            config=self.read_config()
            if self.persist: config.save()
            self.config_value=config
            self.status.set(self.t('设置已保存；分析参数下次开始生效','Settings saved; analysis parameters apply on next start'))
        except (tk.TclError,ValueError,OSError) as exc: self.show_error(str(exc))

    def restore(self):
        self.stop()
        default=AppConfig(language=self.language)
        for key,value in asdict(default).items(): self.vars[key].set(value)
        for mode in ('2d','3d'): self.vars['model_'+mode].set(cached_model(mode))
        self.url.set('');self.source_type.set('Camera');self.source_choice.set('')
        self.mode_changed();self.save()
        self.status.set(self.t('默认设置已恢复（模型缓存保留）','Defaults restored (downloaded models retained)'))

    def preset(self,name):
        for key,value in zip(('reject','flow','kalman','smooth'),{'fast':(True,False,False,True),'stable':(True,True,True,True),'raw':(False,False,False,False)}[name]): self.vars[key].set(value)
        self.vars['smooth_hz'].set(12 if name=='fast' else 8)

    def switch_language(self,language):
        if language==self.language:return
        if self.service and self.service.thread.is_alive():
            self.status.set(self.t('请先停止，再切换界面语言','Stop before changing the interface language'));return
        self.config_value=self.read_config();self.config_value.language=language
        self.language=language;self.vars['language'].set(language)
        if self.persist:self.config_value.save()
        if self.avatar is not None and self.avatar.winfo_exists():self.avatar.destroy()
        for widget in self.winfo_children():widget.destroy()
        self._build();self.mode_changed()

    def run_job(self,work,done):
        if (self.job and self.job.is_alive()) or (self.service and self.service.thread.is_alive()):
            self.status.set(self.t('请先停止当前分析或等待后台任务结束','Stop analysis or wait for the current background task'));return
        self.cancel_job=threading.Event()
        cancel=self.cancel_job
        self.progress.configure(mode='indeterminate');self.progress.start(20)
        def progress(value): self.events.put(('progress',value))
        def run():
            try: self.events.put(('done',(done,work(cancel,progress))))
            except Exception as exc:self.events.put(('job_error',str(exc)))
        self.job=threading.Thread(target=run,daemon=True,name='posebridge-setup');self.job.start()

    def fetch_model(self):
        mode=self.vars['mode'].get()
        def completed(path):
            self.vars['model_'+mode].set(path)
            if self.vars['mode'].get()==mode:self.model_path.set(path)
            self.progress_text.set(self.t('模型就绪','Model ready'))
            self.save()
        self.run_job(lambda cancel,progress:cached_model(mode) or download_model(mode,cancel,progress),completed)

    def gpu_task(self,install):
        from .gpu_runtime import install_runtime,probe_gpu
        backend=self.vars['gpu_backend'].get()
        def work(cancel,progress):
            progress({'stage':'checking'})
            result=probe_gpu(cancel,backend=backend)
            if install and not result.get('ready'):
                if backend=='cuda' and not result.get('nvidia'):raise RuntimeError('no_nvidia')
                result=install_runtime(cancel,progress,backend=backend)
            return result
        def done(result):
            ready=result.get('ready',False)
            self.progress_text.set((backend.upper()+': ')+self.t('检测可用；启用后请重启软件','Ready; enable and restart the app') if ready else self.t('GPU 未就绪：','GPU not ready: ')+result.get('reason','unknown'))
            if ready and install:
                self.vars['gpu_backend'].set(backend)
                self.vars['gpu_enabled'].set(True);self.save()
        self.run_job(work,done)

    def scan_sources(self):
        from .sources import enumerate_sources
        backend=self.vars['camera_backend'].get()
        def done(sources):
            self.sources=sources
            self.source_box['values']=[f'{s["index"]}: {s["name"]} ({s["backend"]})' for s in sources]
            if sources:
                self.source_box.current(0);self.source_selected()
            self.progress_text.set(self.t(f'发现 {len(sources)} 个视频来源',f'Found {len(sources)} video sources'))
        self.run_job(lambda cancel,progress:enumerate_sources(backend),done)

    def source_selected(self,event=None):
        index=self.source_box.current()
        if 0<=index<len(self.sources):
            self.vars['camera_index'].set(self.sources[index]['index'])
            self.vars['camera_backend'].set(self.sources[index]['backend'])

    def phone_help(self):
        messagebox.showinfo(APP_NAME,self.t('手机先通过 Windows 连接手机摄像头功能，或可信的手机摄像头应用，成为系统视频来源，然后点“检测输入来源”。\n\n若手机应用提供 RTSP / HTTP 视频地址，选择 Network 并输入该地址。一般通过 Wi-Fi / USB 传输画面，蓝牙配对本身不提供通用视频流。无线画面的额外延迟取决于手机应用、编码和网络。',
            'First connect the phone as a Windows camera (Phone Link / a trusted virtual-webcam application), then Detect sources.\n\nFor an RTSP / HTTP camera stream, select Network and enter its URL. Video normally travels over Wi-Fi / USB; Bluetooth pairing alone does not provide a generic video stream. Wireless latency depends on the phone app, encoding and network.'),parent=self)

    def start(self):
        if self.closing:return
        if self.service and self.service.thread.is_alive():
            self.status.set(self.t('当前任务尚未结束，请稍候','Current task is still finishing'));return
        if self.job and self.job.is_alive():
            self.status.set(self.t('请等待模型 / GPU 任务结束','Wait for the model / GPU task'));return
        try:
            config=self.read_config()
            network=self.url.get().strip() if self.source_type.get()=='Network' else ''
            if self.source_type.get()=='Network':
                from .sources import validate_network_source
                validate_network_source(network)
            if config.gpu_enabled:
                from .gpu_runtime import runtime_needs_restart
                if runtime_needs_restart(config.gpu_backend):raise ValueError('gpu_restart_required')
            if self.persist:config.save()
            self.service=PoseService(config,synthetic=self.demo,network_url=network,
                **({'engine_factory':DemoEngine} if self.demo else {}))
            self.last_packet=None;self.last_sequence=0;self.arrival_ages=[]
            self.service.start()
            self.status.set(self.t('正在加载模型 / 打开摄像头…','Loading model / opening camera…'))
        except Exception as exc:self.show_error(str(exc))

    def stop(self):
        if self.service:self.service.stop()
        self.last_packet=None
        self.status.set(self.t('已请求停止，正在释放摄像头','Stopping and releasing the camera'))
        for widget in self.image_labels:widget.configure(image='',text=self.t('已停止','Stopped'))
        if self.avatar is not None and self.avatar.winfo_exists():self.avatar_canvas.delete('all')

    def open_avatar(self):
        if self.avatar is not None and self.avatar.winfo_exists():self.avatar.lift();return
        self.avatar=tk.Toplevel(self);self.avatar.title(self.t('人物模型预览 · PoseBridge Lab','Avatar preview · PoseBridge Lab')+(' — SYNTHETIC DEMO' if self.demo else ''));self.avatar.geometry('650x760')
        ttk.Label(self.avatar,text=self.t('当前 Pose 驱动基础人物；2D 深度未测量 / 3D 尚未调试','Current pose drives a basic mannequin; 2D depth unmeasured / 3D unvalidated'),wraplength=600).pack(padx=12,pady=8)
        self.yaw=tk.DoubleVar(self.avatar,value=18)
        ttk.Scale(self.avatar,from_=-65,to=65,variable=self.yaw).pack(fill='x',padx=20)
        self.avatar_canvas=tk.Canvas(self.avatar,bg='#101b24',highlightthickness=0);self.avatar_canvas.pack(fill='both',expand=True,padx=8,pady=8)

    def export_packet(self):
        if self.last_packet is None or time.perf_counter()-self.last_packet.received>.5:
            self.status.set(self.t('没有新鲜姿态可导出','No fresh pose available'));return
        data=self.last_packet.to_dict()
        path=filedialog.asksaveasfilename(parent=self,defaultextension='.json',filetypes=[('Pose JSON','*.json')])
        if path:Path(path).write_text(json.dumps(data,ensure_ascii=False,allow_nan=False,indent=2),encoding='utf-8')

    def show_error(self,error):
        messages={
            'model_missing':('尚未选择模型；下载或选择 ONNX 后开始。','Choose or download an ONNX model first.'),
            'model_input_mismatch':('模型输入尺寸不匹配，请用对应的 2D / 3D 模型。','Model input size mismatch; choose the matching 2D / 3D model.'),
            'model_dimension_mismatch':('模型输出维度不匹配。','Model output dimension mismatch.'),
            'camera_open_failed':('无法打开摄像头：请检查来源、系统权限和其他程序占用；可尝试另一采集接口。','Cannot open camera: check source, system permissions, other apps, or try the other backend.'),
            'camera_open_timeout':('摄像头打开超时，已结束采集进程。可尝试另一接口。','Camera open timed out; capture process stopped. Try another backend.'),
            'camera_read_failed':('摄像头读取失败或已断开。','Camera read failed or disconnected.'),
            'camera_stalled':('摄像头超过 3 秒未返回新图像。','No new camera image for over 3 seconds.'),
            'gpu_restart_required':('GPU 引擎已变化，请关闭并重新运行 Start.cmd。','GPU runtime changed; close and relaunch Start.cmd.'),
            'no_nvidia':('未检测到 NVIDIA GPU；可选择 DirectML。','No NVIDIA GPU detected; consider DirectML.'),
            'cancelled':('任务已取消。','Task cancelled.'),
        }
        text=self.t(*messages[error]) if error in messages else error
        self.status.set(text)
        if not self.closing:messagebox.showerror(APP_NAME,text,parent=self)

    def poll(self):
        if self.closing:self._finish_close();return
        for _ in range(12):
            try:kind,data=self.events.get_nowait()
            except queue.Empty:break
            if kind=='progress':
                stage=data.get('stage','')
                labels={'checking':('检测 GPU','Checking GPU'),'resolving':('解析运行库','Resolving runtime'),
                    'preparing':('准备下载','Preparing'),'downloading':('正在下载','Downloading'),
                    'installing':('安装私有运行库','Installing private runtime'),'verifying':('验证模型 / 引擎','Verifying model / runtime')}
                label=self.t(*labels[stage]) if stage in labels else stage
                if data.get('total'):
                    self.progress.stop();self.progress.configure(mode='determinate',value=data.get('downloaded',0)/data['total']*100)
                self.progress_text.set(label+(f' {data["downloaded"]/1024**2:.1f} MB' if 'downloaded' in data else ''))
            else:
                self.progress.stop();self.progress.configure(mode='determinate',value=0)
                if kind=='done':callback,value=data;callback(value)
                else:self.show_error(data)
        service=self.service
        if service is not None:
            if service.error:
                error=service.error;service.error='';self.stop();self.show_error(error)
            if not service.stop_event.is_set():
                packet=service.latest(self.last_sequence)
                if packet is not None:self.display_packet(packet)
            if self.last_packet is not None and time.perf_counter()-self.last_packet.received>.5:
                self.last_packet=None
                self.status.set(self.t('画面已过期，等待新帧','Frame stale; waiting for a new frame'))
                for widget in self.image_labels:widget.configure(image='',text=self.t('等待新帧','Waiting for fresh frame'))
                if self.avatar is not None and self.avatar.winfo_exists():self.avatar_canvas.delete('all')
        if self.last_packet is not None and self.avatar is not None and self.avatar.winfo_exists():
            draw_mannequin(self.avatar_canvas,self.last_packet,yaw=self.yaw.get(),mirror=self.vars['mirror'].get())
        self.poll_id=self.after(16,self.poll)

    def display_packet(self,packet):
        self.last_sequence=packet.sequence;self.last_packet=packet
        age=(time.perf_counter()-packet.received)*1000
        self.arrival_ages.append(age);self.arrival_ages=self.arrival_ages[-300:]
        median,p95=np.percentile(self.arrival_ages,[50,95])
        self.status.set(('SYNTHETIC DEMO | ' if self.demo else '')+self.t('分析中','Analyzing')+f' · {packet.mode.upper()} · {packet.provider} · '+self.t(f'有效点 {int(packet.observed.sum())}/17',f'Observed {int(packet.observed.sum())}/17'))
        info=packet.source_info
        self.metrics.set(self.t('采集','Capture')+f' {packet.capture_fps:.1f} FPS | '+self.t('分析','Analysis')+f' {packet.analysis_fps:.1f} FPS | '+self.t('推理','Inference')+f' {packet.inference_ms:.1f} ms\n'+
            self.t('排队','Queue')+f' {packet.queue_ms:.1f} ms | '+self.t('帧龄（UI 接收）','Receipt→UI')+f' {age:.1f} ms (p50 {median:.1f} / p95 {p95:.1f}) | '+self.t('跳过旧帧','Skipped')+f' {packet.skipped}\n'+
            f'{info.get("backend","")} {info.get("width",0)}×{info.get("height",0)} | '+self.t('不含曝光 / 驱动缓冲 / 屏幕刷新','Excludes exposure / driver buffer / scan-out')+(('\n'+packet.warning) if packet.warning else ''))
        mirror=self.vars['mirror'].get()
        left=cv2.flip(packet.frame,1) if mirror else packet.frame
        right=skeleton_image(packet,overlay=self.vars['overlay'].get(),mirror=mirror,show_ids=self.vars['show_ids'].get())
        for widget,frame in zip(self.image_labels,(left,right)):
            pil=Image.fromarray(cv2.cvtColor(frame,cv2.COLOR_BGR2RGB))
            pil.thumbnail((max(50,widget.winfo_width()-6),max(50,widget.winfo_height()-6)),Image.Resampling.BILINEAR)
            widget.photo=ImageTk.PhotoImage(pil)
            widget.configure(image=widget.photo,text='')
        for i,p in enumerate(packet.xy):
            valid=np.isfinite(p).all()
            state=self.t('观测','Observed') if packet.observed[i] else self.t('暂保持','Held') if valid else self.t('缺失','Missing')
            self.tree.item(str(i),values=(f'{i} {JOINTS_ZH[i] if self.language=="zh" else JOINTS[i]}',f'{p[0]:.1f}' if valid else '—',f'{p[1]:.1f}' if valid else '—',f'{packet.scores[i]:.2f}',state))

    def close(self):
        if self.closing:return
        if self.persist:
            try:self.read_config().save()
            except (OSError,ValueError,tk.TclError):pass
        self.closing=True;self.close_started=time.perf_counter()
        self.cancel_job.set();self.stop()

    def _finish_close(self):
        alive=(self.service and self.service.thread.is_alive()) or (self.job and self.job.is_alive())
        if alive and time.perf_counter()-self.close_started<30:
            self.poll_id=self.after(50,self._finish_close)
        else:self.destroy()


def main():
    import argparse
    import tempfile
    parser=argparse.ArgumentParser(description='PoseBridge Lab camera pose workbench')
    parser.add_argument('--language',choices=('zh','en'))
    parser.add_argument('--smoke',action='store_true')
    parser.add_argument('--demo',action='store_true',help='Synthetic preview; never opens a camera')
    args=parser.parse_args()
    config=AppConfig() if args.smoke or args.demo else AppConfig.load()
    if args.language:config.language=args.language
    app=PoseBridgeApp(config,persist=not(args.smoke or args.demo),demo=args.demo)
    errors=[]
    if args.smoke:
        app.report_callback_exception=lambda *details:errors.append(details)
        app.after(1400,app.close)
    app.mainloop()
    if errors:raise RuntimeError(f'UI callback errors: {errors}')
