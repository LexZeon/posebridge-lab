"""Frame-aligned overlays and a simple solid mannequin, with no invented depth."""
import math
import cv2
import numpy as np
from .stabilizer import EDGES


def skeleton_image(packet,*,overlay=False,mirror=False,show_ids=False):
    image=packet.frame.copy() if overlay else np.full_like(packet.frame,(30,25,22))
    points=packet.xy
    for a,b in EDGES:
        if np.isfinite(points[[a,b]]).all():
            fresh=packet.observed[a] and packet.observed[b]
            color=(110,225,95) if fresh else (130,140,170)
            cv2.line(image,tuple(np.round(points[a]).astype(int)),tuple(np.round(points[b]).astype(int)),color,2,cv2.LINE_AA)
    for i,p in enumerate(points):
        if np.isfinite(p).all():
            location=tuple(np.round(p).astype(int))
            cv2.circle(image,location,4,(70,205,250) if packet.observed[i] else (120,130,160),-1,cv2.LINE_AA)
    if mirror: image=cv2.flip(image,1)
    if show_ids:
        for i,p in enumerate(points):
            if np.isfinite(p).all():
                x=round(image.shape[1]-1-p[0]) if mirror else round(p[0])
                cv2.putText(image,str(i),(x+5,round(p[1])),cv2.FONT_HERSHEY_SIMPLEX,.4,(245,245,245),1,cv2.LINE_AA)
    return image


def mannequin_points(packet,mirror=False):
    points=np.asarray(packet.xy,float).copy()
    if not np.isfinite(points[[5,6,11,12]]).all(): return None
    root=points[[11,12]].mean(axis=0)
    shoulder=points[[5,6]].mean(axis=0)
    scale=max(15.,np.linalg.norm(root-shoulder))
    xyz=np.column_stack(((points[:,0]-root[0])/scale,-(points[:,1]-root[1])/scale,np.zeros(17)))
    if packet.mode=='3d' and packet.native3d is not None:
        # Upstream native XY and Z use different scales. Only an explicitly
        # uncalibrated relative-depth view is offered; no metre conversion.
        z=np.asarray(packet.native3d)[:,2]
        if np.isfinite(z[[11,12]]).all(): xyz[:,2]=(z-z[[11,12]].mean())/2.1744869
    if mirror: xyz[:,0]*=-1
    return xyz


def draw_mannequin(canvas,packet,*,yaw=18,mirror=True):
    canvas.delete('all')
    width,height=max(100,canvas.winfo_width()),max(100,canvas.winfo_height())
    canvas.create_rectangle(0,0,width,height,fill='#101b24',outline='')
    for i in range(-5,6):
        canvas.create_line(width/2+i*70,height*.8,width/2+i*140,height,fill='#243748')
    xyz=mannequin_points(packet,mirror)
    if xyz is None:
        canvas.create_text(width/2,height/2,text='等待可靠躯干 / Waiting for torso',fill='#cbd7df',font=('Segoe UI',13))
        return
    angle=math.radians(yaw)
    x=xyz[:,0]*math.cos(angle)+xyz[:,2]*math.sin(angle)
    depth=-xyz[:,0]*math.sin(angle)+xyz[:,2]*math.cos(angle)
    size=min(width*.23,height*.23)
    screen=np.column_stack((width/2+x*size,height*.52-xyz[:,1]*size-depth*size*.08))
    if np.isfinite(screen[[0,5,6]]).all():
        neck=screen[[5,6]].mean(axis=0)
        canvas.create_line(*screen[0],*neck,fill='#667888' if not packet.observed[[0,5,6]].all() else '#52abc1',width=size*.20,capstyle='round')
    primitives=[]
    if np.isfinite(screen[[5,6,12,11]]).all():
        primitives.append((float(depth[[5,6,11,12]].mean()),'torso',(5,6,12,11)))
    for a,b in EDGES:
        if (a,b) in ((5,6),(5,11),(6,12),(11,12)): continue
        if np.isfinite(screen[[a,b]]).all(): primitives.append((float((depth[a]+depth[b])/2),'limb',(a,b)))
    if np.isfinite(screen[0]).all(): primitives.append((float(depth[0]),'head',(0,)))
    for _,kind,ids in sorted(primitives,key=lambda p:p[0]):
        held=not all(packet.observed[i] for i in ids)
        color='#667888' if held else '#52abc1'
        if kind=='torso':
            canvas.create_polygon(*screen[list(ids)].reshape(-1),fill=color,outline='#a6d5e0',width=2)
        elif kind=='head':
            px,py=screen[0]; r=size*.24
            canvas.create_oval(px-r,py-r*1.15,px+r,py+r*1.15,fill='#c7d4dd' if not held else '#687681',outline='#e4edf2',width=2)
            canvas.create_line(px-r*.45,py,px+r*.45,py,fill='#263e52',width=3)
        else:
            a,b=ids
            radius=size*(.14 if min(ids)>=11 else .105)
            canvas.create_line(*screen[a],*screen[b],fill='#244c63',width=radius*2+4,capstyle='round')
            canvas.create_line(*screen[a],*screen[b],fill=color,width=radius*2,capstyle='round')
            for point in screen[list(ids)]:
                px,py=point
                canvas.create_oval(px-radius*.65,py-radius*.65,px+radius*.65,py+radius*.65,fill='#afd4dd' if not held else '#8494a1',outline='')
    canvas.create_text(14,14,anchor='nw',text=f'Pose #{packet.sequence} | '+('2D: depth unmeasured' if packet.mode=='2d' else '3D: uncalibrated experimental'),fill='#bfdae3',font=('Segoe UI',10))
