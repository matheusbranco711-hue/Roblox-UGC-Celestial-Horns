"""Celestial Horns — real, reproducible Roblox rigid accessory.
Blender 4.3+: blender -b --python create_celestial_horns.py -- --output .
Coordinates: X right, +Y front, Z up; one modeling unit = one target stud.
The original Diwali Sparkler Headband is not included or modified.
"""
import argparse
import json
import math
import os
import re
import struct
import zlib
import sys
from pathlib import Path
import bpy
import bmesh
import numpy as np
from mathutils import Vector, Matrix, Euler
from mathutils.bvhtree import BVHTree

# -------------------- ART / FIT PARAMETERS (target studs) --------------------
HORN_HEIGHT = 1.48
HORN_SPACING = 1.32
HORN_CURVATURE = 0.24
SPIRAL_TURNS = 2.65
SPIRAL_PHASE = -3.55
HORN_SWEEP = 0.13
SPIRAL_SWAY = 0.055
BODY_FLUTE = 0.24
RIBBON_WIDTH = 0.175
STAR_SCALE = 0.18
BASE_RADIUS = 0.29
BASE_Z = -0.13
HEAD_POSITION_OFFSET = (0.0, 0.0, 0.0)
LEFT_TIP_OFFSET = (0.0, 0.0, 0.0)
RIGHT_TIP_OFFSET = (0.0, 0.0, 0.0)
LEFT_HORN_ROTATION = (0.0, 0.0, 0.0)  # Euler degrees XYZ
RIGHT_HORN_ROTATION = (0.0, 0.0, 0.0)
LEFT_HORN_SCALE = (1.0, 1.0, 1.0)
RIGHT_HORN_SCALE = (1.0, 1.0, 1.0)
LEFT_POSITION_OFFSET = (0.0, 0.0, 0.0)
RIGHT_POSITION_OFFSET = (0.0, 0.0, 0.0)
LEFT_STAR_ROTATION = (0.0, 0.0, 0.0)
RIGHT_STAR_ROTATION = (0.0, 0.0, 0.0)
LEFT_STAR_SCALE = (1.0, 1.0, 1.0)
RIGHT_STAR_SCALE = (1.0, 1.0, 1.0)
LEFT_STAR_OFFSET = (0.0, 0.0, 0.0)  # relative to target; 0 keeps exact center
RIGHT_STAR_OFFSET = (0.0, 0.0, 0.0)
# Set these to measured ORIGINAL star centers in Blender coordinates, relative
# to HatAttachment. None uses the reference-image estimate. In target mode the
# horn tip is smoothly warped to the target after independent horn transforms.
LEFT_STAR_TARGET = None
RIGHT_STAR_TARGET = None
# 0..1: where deformation toward the tip target starts along each horn.
TIP_WARP_START = 0.0
RADIAL_SEGMENTS = 12
HORN_SEGMENTS = 34
RIBBON_SEGMENTS = 56
ALBEDO_SIZE = 1024
PBR_SIZE = 256
MAX_TRIANGLES = 4000  # verified creator-docs avatar/rigid-accessories/specifications
RENDER_SIZE = 1200
RENDER_SAMPLES = 128
ORIGINAL_ASSET_ID = 81550816889926

UV_REGIONS = {
    'purple': (0.025, 0.035, 0.475, 0.965),
    'gold': (0.525, 0.035, 0.735, 0.965),
    'star': (0.785, 0.06, 0.965, 0.94),
}

def arguments():
    p = argparse.ArgumentParser()
    p.add_argument('--output', default=str(Path(__file__).resolve().parent))
    p.add_argument('--config', help='Optional JSON overrides, e.g. fit_parameters.json')
    p.add_argument('--no-render', action='store_true')
    p.add_argument('--views', nargs='+', choices=['front','back','side','three_quarter'], default=['front','back','side','three_quarter'])
    p.add_argument('--render-size', type=int, default=RENDER_SIZE)
    p.add_argument('--samples', type=int, default=RENDER_SAMPLES)
    a = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
    return p.parse_args(a)


def apply_config(path):
    if not path:
        return
    data = json.loads(Path(path).read_text(encoding='utf-8'))
    for k, v in data.items():
        if k.isupper() and k in globals() and not k.startswith('UV_'):
            globals()[k] = v
        elif not k.startswith('_'):
            raise ValueError(f'Unknown parameter: {k}')
    for k in ('HORN_HEIGHT', 'HORN_SPACING', 'BASE_RADIUS', 'STAR_SCALE'):
        if globals()[k] <= 0:
            raise ValueError(f'{k} must be positive')
    if RADIAL_SEGMENTS < 8 or HORN_SEGMENTS < 8 or RIBBON_SEGMENTS < 24:
        raise ValueError('Mesh sampling is too low')


def clean_scene():
    # Preserve any imported original/reference objects outside our collections.
    managed={'01_EXPORT_Addon','02_FIT_Guides_NOT_EXPORTED','03_PRESENTATION_NOT_EXPORTED','00_EDITABLE_Three_Materials'}
    for col in list(bpy.data.collections):
        if col.name in managed:
            for obj in list(col.all_objects):
                bpy.data.objects.remove(obj,do_unlink=True)
            bpy.data.collections.remove(col)
    defaults={'Cube','Camera','Light'}
    if set(o.name for o in bpy.context.scene.objects).issubset(defaults):
        for obj in list(bpy.context.scene.objects):
            bpy.data.objects.remove(obj,do_unlink=True)
    for db in (bpy.data.meshes,bpy.data.curves,bpy.data.materials,bpy.data.images,bpy.data.cameras,bpy.data.lights):
        for item in list(db):
            if item.users==0 and item.name.startswith(('Celestial','Stage_','Presentation_')):
                db.remove(item)


def collection(name):
    c = bpy.data.collections.new(name)
    bpy.context.scene.collection.children.link(c)
    return c


def move_to(obj, col):
    for c in list(obj.users_collection):
        c.objects.unlink(obj)
    col.objects.link(obj)


def uv(region, u, v):
    x0, y0, x1, y1 = UV_REGIONS[region]
    return (x0 + (x1-x0)*u, y0 + (y1-y0)*v)


def save_image(name, rgba, directory, noncolor=False, gray=False):
    h, w = rgba.shape[:2]
    im = bpy.data.images.new(name, width=w, height=h, alpha=False, float_buffer=False)
    im.colorspace_settings.name = 'Non-Color' if noncolor else 'sRGB'
    im.pixels.foreach_set(np.asarray(rgba, dtype=np.float32).ravel())
    im.filepath_raw = str(directory / (name+'.png'))
    im.file_format = 'PNG'
    scene = bpy.context.scene
    scene.render.image_settings.color_mode = 'BW' if gray else 'RGB'
    scene.render.image_settings.color_depth = '8'
    im.save()
    if gray:
        # PNG grayscale color type 0, 8 bits: no external image dependency.
        pixels=np.rint(np.clip(rgba[::-1,:,0],0,1)*255).astype(np.uint8)
        raw=b''.join(b'\x00'+row.tobytes() for row in pixels)
        def chunk(tag,body):
            return struct.pack('>I',len(body))+tag+body+struct.pack('>I',zlib.crc32(tag+body)&0xffffffff)
        png=b'\x89PNG\r\n\x1a\n'+chunk(b'IHDR',struct.pack('>IIBBBBB',w,h,8,0,0,0,0))+chunk(b'IDAT',zlib.compress(raw,9))+chunk(b'IEND',b'')
        Path(im.filepath_raw).write_bytes(png)
        im.source='FILE'
        im.reload()
    return im


def atlas_pixels(n):
    y, x = np.mgrid[0:n, 0:n].astype(np.float32)/(n-1)
    rgba = np.ones((n, n, 4), dtype=np.float32)
    rgba[..., :3] = (0.08, 0.016, 0.14)
    metal = np.full((n,n), 0.48, dtype=np.float32)
    rough = np.full((n,n), 0.23, dtype=np.float32)
    emiss = np.zeros((n,n), dtype=np.float32)
    # Extend each patch into a guard band for mipmap filtering.
    purple = x < .5
    pu = np.clip((x-.025)/.45, 0, 1)
    pv = np.clip((y-.035)/.93, 0, 1)
    drift = .5+.5*np.sin(2*math.pi*(pu*2.0 - pv*1.1))
    sheen = (.5+.5*np.sin(2*math.pi*(pu*3 + pv*.8)))**3
    for c, base in enumerate((.18, .024, .34)):
        rgba[..., c][purple] = (base + drift*(.105,.012,.14)[c] + sheen*(.035,.008,.04)[c])[purple]
    # Tiny painted celestial dust: static color detail, not fake particles.
    rng = np.random.default_rng(711)
    for _ in range(37):
        cx, cy = rng.uniform(.045,.455), rng.uniform(.07,.94)
        rr = rng.uniform(.0012,.0027)
        dist = ((x-cx)/rr)**2 + ((y-cy)/(rr*.50))**2
        mask = (dist < 1) & purple
        rgba[mask,:3] = (.78,.42,.08)
        metal[mask] = .82
    gold = (x >= .5) & (x < .76)
    gu = np.clip((x-.525)/.21,0,1)
    # Narrow warm edges and subtly brighter center, kept mild for PBR lighting.
    edge = np.abs(gu-.5)*2
    for c, base in enumerate((.93,.57,.16)):
        rgba[...,c][gold] = (base + (1-edge)*(.055,.09,.045)[c])[gold]
    metal[gold] = .92
    rough[gold] = .195
    stars = x >= .76
    su, sv = (x-.875)/.09, (y-.5)/.44
    radial = np.clip(np.sqrt(su*su+sv*sv),0,1)
    core = (1-radial)**1.6
    for c, base in enumerate((1.0,.64,.17)):
        rgba[...,c][stars] = (base+core*(0,.29,.50)[c])[stars]
    metal[stars] = .72
    rough[stars] = .21
    emiss[stars] = (.06+.94*core)[stars]
    return rgba, metal, rough, emiss


def make_textures(out):
    texdir = out/'Textures'
    texdir.mkdir(exist_ok=True)
    color, _, _, _ = atlas_pixels(ALBEDO_SIZE)
    albedo = save_image('Celestial_ColorMap',color,texdir)
    _, metal, rough, emiss = atlas_pixels(PBR_SIZE)
    ims = {'color':albedo}
    for name, arr, key in [('Celestial_MetalnessMap',metal,'metal'),
                           ('Celestial_RoughnessMap',rough,'rough'),
                           ('Celestial_EmissiveMask',emiss,'emiss')]:
        rgba = np.ones((PBR_SIZE,PBR_SIZE,4),dtype=np.float32)
        rgba[...,:3] = arr[...,None]
        ims[key] = save_image(name,rgba,texdir,True,True)
    normal = np.ones((PBR_SIZE,PBR_SIZE,4),dtype=np.float32)
    normal[...,:3] = (.5,.5,1.0)  # deliberate neutral OpenGL tangent normal
    ims['normal'] = save_image('Celestial_NormalMap',normal,texdir,True)
    return ims


def make_material(ims):
    # A single real PBR material on the shipping MeshPart; masks separate gold,
    # amethyst enamel and faceted stars without extra Roblox material slots.
    mat = bpy.data.materials.new('Celestial_PBR_Atlas')
    mat.use_nodes = True
    mat.diffuse_color = (.8,.8,.8,1)
    nodes, links = mat.node_tree.nodes, mat.node_tree.links
    nodes.clear()
    out = nodes.new('ShaderNodeOutputMaterial'); out.location=(630,160)
    bs = nodes.new('ShaderNodeBsdfPrincipled'); bs.location=(300,160)
    bs.inputs['Coat Weight'].default_value=.32
    bs.inputs['Coat Roughness'].default_value=.19
    links.new(bs.outputs['BSDF'],out.inputs['Surface'])
    for key, slot, y in [('color','Base Color',450),('metal','Metallic',180),
                          ('rough','Roughness',-70),('emiss','Emission Strength',-330)]:
        n=nodes.new('ShaderNodeTexImage'); n.image=ims[key]; n.location=(-400,y)
        n.label='Roblox '+key; n.interpolation='Linear'
        if key=='emiss':
            mul=nodes.new('ShaderNodeMath'); mul.operation='MULTIPLY'; mul.inputs[1].default_value=1.4
            mul.location=(-100,-300)
            links.new(n.outputs['Color'],mul.inputs[0]); links.new(mul.outputs[0],bs.inputs[slot])
        else:
            links.new(n.outputs['Color'],bs.inputs[slot])
    bs.inputs['Emission Color'].default_value=(1,.57,.13,1)
    n=nodes.new('ShaderNodeTexImage'); n.image=ims['normal']; n.location=(-400,-570)
    nm=nodes.new('ShaderNodeNormalMap'); nm.location=(-90,-530)
    links.new(n.outputs['Color'],nm.inputs['Color']); links.new(nm.outputs['Normal'],bs.inputs['Normal'])
    return mat


class MeshBuilder:
    def __init__(self):
        self.verts=[]; self.faces=[]; self.uvs=[]; self.smooth=[]; self.groups={}; self.vertex_normals={}
    def part(self, name, vertices, faces, uvs, smooth=False):
        start=len(self.verts)
        self.verts.extend(tuple(v) for v in vertices)
        self.faces.extend(tuple(start+i for i in f) for f in faces)
        self.uvs.extend(uvs)
        self.smooth.extend([smooth]*len(faces))
        self.groups[name]=list(range(start,len(self.verts)))
    def object(self,name,col,mat):
        me=bpy.data.meshes.new(name+'_Mesh'); me.from_pydata(self.verts,[],self.faces); me.update()
        obj=bpy.data.objects.new(name,me); col.objects.link(obj)
        me.materials.append(mat)
        layer=me.uv_layers.new(name='UVMap')
        for poly, coords, smooth in zip(me.polygons,self.uvs,self.smooth):
            poly.use_smooth=smooth
            for li, xy in zip(poly.loop_indices,coords): layer.data[li].uv=xy
        bm=bmesh.new(); bm.from_mesh(me)
        bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces)); bm.to_mesh(me); bm.free(); me.update()
        if self.vertex_normals:
            custom=[n.vector.copy() for n in me.corner_normals]
            for poly in me.polygons:
                known=[i in self.vertex_normals for i in poly.vertices]
                for li in poly.loop_indices:
                    vi=me.loops[li].vertex_index
                    if all(known): custom[li]=self.vertex_normals[vi]
                    elif any(known): custom[li]=poly.normal.copy()
            me.normals_split_custom_set(custom)
        for label,ids in self.groups.items():
            g=obj.vertex_groups.new(name=label); g.add(ids,1.0,'REPLACE')
        return obj


def smoothstep(x):
    x=max(0.0,min(1.0,x))
    return x*x*(3-2*x)


def spiral_phase(t):
    return SPIRAL_PHASE+2*math.pi*SPIRAL_TURNS*t


def center(t):
    # S-shaped sweep + an actual broad corkscrew in the purple volume.
    # Parallel rings keep the loft closed even with a strong silhouette.
    t=max(0.0,min(1.0,t))
    e=max(0.0,math.sin(math.pi*t))**1.15
    ph=spiral_phase(t)
    return Vector((HORN_CURVATURE*t + HORN_SWEEP*math.sin(math.pi*t)**2
                   + SPIRAL_SWAY*e*math.cos(ph),
                   SPIRAL_SWAY*.60*e*math.sin(ph), HORN_HEIGHT*t))


def frame(t):
    return Vector((1,0,0)),Vector((0,1,0)),Vector((0,0,1))


def envelope(t):
    t=max(0.0,min(1.0,t))
    # A rounded, narrow foot opens into the sculpted first whorl.
    foot=.40+.60*smoothstep(t/.16)
    return (.0045+BASE_RADIUS*(1-t)**.76)*foot


def surface(t,phi):
    t=max(0.0,min(1.0,t)); r=envelope(t); ph=spiral_phase(t)
    # Twisted asymmetric teardrop section. The purple body itself coils;
    # the gold follows its crest rather than decorating a round cone.
    a=1.0+BODY_FLUTE
    b=1.0-BODY_FLUTE*.58
    x=r*(a*math.cos(phi)+.10*math.cos(2*phi))
    y=r*b*math.sin(phi)
    return center(t)+Vector((x*math.cos(ph)-y*math.sin(ph),
                            x*math.sin(ph)+y*math.cos(ph),0))


def surface_derivatives(t,phi):
    e=.0001; tl=max(0,t-e); th=min(1,t+e)
    dt=(surface(th,phi)-surface(tl,phi))/max(1e-9,th-tl)
    dp=(surface(t,phi+e)-surface(t,phi-e))/(2*e)
    return dt,dp


def surface_normal(t,phi):
    dt,dp=surface_derivatives(t,phi)
    return dp.cross(dt).normalized()


def surface_at_angle(t,theta):
    # Intersect a radial direction with the noncircular rotating section.
    beta=theta-spiral_phase(t)
    direction=Vector((math.cos(beta),math.sin(beta)))
    a=1+BODY_FLUTE; b=1-BODY_FLUTE*.58
    phi=math.atan2(math.sin(beta)/b,math.cos(beta)/a)
    for _ in range(10):
        x=a*math.cos(phi)+.10*math.cos(2*phi); y=b*math.sin(phi)
        dx=-a*math.sin(phi)-.20*math.sin(2*phi); dy=b*math.cos(phi)
        value=x*direction.y-y*direction.x
        derivative=dx*direction.y-dy*direction.x
        if abs(derivative)>1e-9: phi-=value/derivative
    return surface(t,phi),surface_normal(t,phi)


class SideFit:
    def __init__(self,side):
        self.name=side
        self.sign=-1 if side=='LEFT' else 1
        self.rot=Euler(tuple(math.radians(v) for v in globals()[side+'_HORN_ROTATION']),'XYZ').to_matrix()
        self.scale=Vector(globals()[side+'_HORN_SCALE'])
        self.base=Vector((self.sign*HORN_SPACING/2,0,BASE_Z))+Vector(HEAD_POSITION_OFFSET)+Vector(globals()[side+'_POSITION_OFFSET'])
        self.tip_offset=Vector(globals()[side+'_TIP_OFFSET'])
        raw=self.raw(center(1))
        target=globals()[side+'_STAR_TARGET']
        self.target=Vector(target) if target is not None else raw+self.tip_offset
        self.delta=self.target-raw
    def raw(self,p):
        q=Vector((p.x*self.sign,p.y,p.z))
        return self.base+self.rot@Vector((q.x*self.scale.x,-q.y*self.scale.y,q.z*self.scale.z))
    def point(self,p,t):
        w=max(0,min(1,(t-TIP_WARP_START)/max(1e-6,1-TIP_WARP_START)))
        w=w*w*(3-2*w)
        return self.raw(p)+self.delta*w
    def star_center(self):
        return self.target+Vector(globals()[self.name+'_STAR_OFFSET'])


def make_horn(builder,fit):
    v=[]; f=[]; uvf=[]; n=RADIAL_SEGMENTS; steps=HORN_SEGMENTS
    for k in range(steps+1):
        t=k/steps
        for j in range(n):
            v.append(fit.point(surface_at_angle(t,2*math.pi*j/n)[0],t))
    for k in range(steps):
        for j in range(n):
            f.append((k*n+j,k*n+(j+1)%n,(k+1)*n+(j+1)%n,(k+1)*n+j))
            patch='gold' if k<2 else 'purple'
            uvf.append([uv(patch,j/n,k/steps),uv(patch,(j+1)/n,k/steps),
                        uv(patch,(j+1)/n,(k+1)/steps),uv(patch,j/n,(k+1)/steps)])
    for k,rev in [(0,True),(steps,False)]:
        idx=len(v); v.append(fit.point(center(k/steps),k/steps))
        for j in range(n):
            face=(idx,k*n+(j+1)%n,k*n+j) if rev else (idx,k*n+j,k*n+(j+1)%n)
            f.append(face)
            patch='gold' if k==0 else 'purple'
            uvf.append([uv(patch,.5 if vi==idx else .5+.42*math.cos(2*math.pi*(vi%n)/n),
                          .5 if vi==idx else .5+.42*math.sin(2*math.pi*(vi%n)/n)) for vi in face])
    start=len(builder.verts)
    builder.part(fit.name+'_Horn',v,f,uvf,True)
    # Analytic corner normals smooth the sculpted enamel without adding triangles.
    eps=.0001
    for k in range(steps+1):
        t=k/steps; tl=max(0,t-eps); th=min(1,t+eps)
        for j in range(n):
            angle=2*math.pi*j/n
            pt0=fit.point(surface_at_angle(tl,angle)[0],tl)
            pt1=fit.point(surface_at_angle(th,angle)[0],th)
            pa0=fit.point(surface_at_angle(t,angle-eps)[0],t)
            pa1=fit.point(surface_at_angle(t,angle+eps)[0],t)
            normal=(pa1-pa0).cross(pt1-pt0).normalized()
            radial=Vector(v[k*n+j])-fit.point(center(t),t)
            if normal.dot(radial)<0: normal=-normal
            builder.vertex_normals[start+k*n+j]=normal



def make_ribbon(builder,fit):
    v=[]; f=[]; uvf=[]; steps=RIBBON_SEGMENTS
    # Six-sided arched foil, fitted over the sculpted purple crest.
    cross=[(-1,.45),(0,1),(1,.45),(1,0),(0,0),(-1,0)]
    ids=builder.groups[fit.name+'_Horn']; first=ids[0]; last=ids[-1]
    polygons=[tuple(i-first for i in face) for face in builder.faces if all(first<=i<=last for i in face)]
    skin=BVHTree.FromPolygons([Vector(builder.verts[i]) for i in ids],polygons)
    for k in range(steps+1):
        t=.035+.935*k/steps
        dt,dp=surface_derivatives(t,0); tangent=dt.normalized()
        across=dp-tangent*dp.dot(tangent)
        width=RIBBON_WIDTH*(.47+.53*(1-t)**.50)
        # Soft, pointed terminations rather than chopped ends.
        width*=.35+.65*smoothstep(min(k,steps-k)/2.0)
        halfphi=width/(2*max(.02,across.length))
        halfphi=min(halfphi,.70)
        for w,d in cross:
            phi=w*halfphi
            tt=t-dp.dot(tangent)/max(1e-5,dt.length)*phi
            tt=max(.001,min(.997,tt))
            normal=surface_normal(tt,phi)
            theory=fit.point(surface(tt,phi),tt)
            origin=fit.point(center(tt),tt)
            outward=(theory-origin).normalized()
            start=origin+outward*max(2.0,(theory-origin).length*4)
            hit,_,_,_=skin.ray_cast(start,-outward,(start-origin).length*1.1)
            assert hit is not None, 'Gold ribbon could not reach horn skin'
            skin_radius=max((hit-origin).length,(theory-origin).length)
            v.append(origin+outward*(skin_radius+.004+.026*d))
    # u follows the actual cross-section, including two narrow polished bevels.
    us=[.02,.50,.98,.92,.50,.08]
    for k in range(steps):
        for j in range(6):
            j1=(j+1)%6
            f.append((k*6+j,k*6+j1,(k+1)*6+j1,(k+1)*6+j))
            uvf.append([uv('gold',us[j],k/steps),uv('gold',us[j1],k/steps),
                        uv('gold',us[j1],(k+1)/steps),uv('gold',us[j],(k+1)/steps)])
    for k in (0,steps):
        a=k*6
        for j in range(1,5):
            f.append((a,a+j,a+j+1))
            uvf.append([uv('gold',.5,.5),uv('gold',.1+.15*j,.2),uv('gold',.1+.15*(j+1),.8)])
    builder.part(fit.name+'_Gold_Helix',v,f,uvf,True)


def add_star(builder,name,pos,radius_,depth,rotation=None,scale=(1,1,1),patch='star',beveled=False):
    rot=rotation or Matrix.Identity(3); sc=Vector(scale)
    ring=[]; ringuv=[]
    for j in range(10):
        a=math.pi/2+j*math.pi/5; rr=1 if j%2==0 else .445
        ring.append(Vector((math.cos(a)*radius_*rr,0,math.sin(a)*radius_*rr)))
        ringuv.append((.5+.48*math.cos(a)*rr,.5+.48*math.sin(a)*rr))
    if beveled:
        local=list(ring); xy=list(ringuv)
        for sign in (1,-1):
            for p,q in zip(ring,ringuv):
                local.append(Vector((p.x*.82,sign*depth*.64,p.z*.82)))
                xy.append((.5+(q[0]-.5)*.82,.5+(q[1]-.5)*.82))
        local.extend([Vector((0,depth,0)),Vector((0,-depth,0))]); xy.extend([(.5,.5)]*2)
        f=[]
        for j in range(10):
            j1=(j+1)%10
            f.extend([(j,j1,10+j1,10+j),(j,20+j,20+j1,j1),
                      (30,10+j,10+j1),(31,20+j1,20+j)])
    else:
        local=ring+[Vector((0,-depth,0)),Vector((0,depth,0))]; xy=ringuv+[(.5,.5)]*2
        f=[]
        for j in range(10): f.extend([(10,j,(j+1)%10),(11,(j+1)%10,j)])
    v=[Vector(pos)+rot@Vector((p.x*sc.x,p.y*sc.y,p.z*sc.z)) for p in local]
    uvf=[[uv(patch,*xy[i]) for i in face] for face in f]
    builder.part(name,v,f,uvf,False)


def add_link(builder,name,pos,rotate=0.0,tilt=0.0):
    # Six by four closed oval link. Alternate planes create interlinked chains.
    v=[]; f=[]; uvf=[]; rot=Euler((tilt,0,0),'XYZ').to_matrix() @ Euler((0,0,rotate),'XYZ').to_matrix()
    for i in range(6):
        a=2*math.pi*i/6
        p=Vector((.025*math.cos(a),0,.065*math.sin(a)))
        radial=Vector((math.cos(a),0,math.sin(a))).normalized()
        for j in range(4):
            b=2*math.pi*j/4
            q=p+.006*(radial*math.cos(b)+Vector((0,1,0))*math.sin(b))
            v.append(Vector(pos)+rot@q)
    for i in range(6):
        for j in range(4):
            f.append((i*4+j,i*4+(j+1)%4,((i+1)%6)*4+(j+1)%4,((i+1)%6)*4+j))
            uvf.append([uv('gold',j/4,i/6),uv('gold',(j+1)/4,i/6),uv('gold',(j+1)/4,(i+1)/6),uv('gold',j/4,(i+1)/6)])
    builder.part(name,v,f,uvf,True)


def ornaments(builder,fit):
    # Sparse jewelry between the broad helical bands.
    for i,(t,th,sz) in enumerate([(.30,-1.62,.043),(.68,-1.47,.035)]):
        p,normal=surface_at_angle(t,th)
        rot=fit.rot @ Euler((0,0,-.10 if fit.sign>0 else .10),'XYZ').to_matrix()
        add_star(builder,f'{fit.name}_Inlay_{i+1}',fit.point(p+normal*.004,t),sz,.013,rot,patch='gold')
    for ci,(t,th,count,sz) in enumerate([(.50,-.40,4,.079),(.25,-2.0,3,.061)]):
        p,normal=surface_at_angle(t,th)
        anchor=fit.point(p+normal*.004,t)
        drift=.04 if ci==0 else .15
        step=.105
        tilt=math.atan2(drift/(count-1),step)
        for j in range(count):
            q=anchor+Vector((0,drift*j/(count-1),-step*j))
            add_link(builder,f'{fit.name}_Chain_{ci+1}_Link_{j+1}',q,math.pi/2*(j%2),tilt)
        pendant=anchor+Vector((0,drift,-step*(count-1)-.060-sz*.72))
        add_star(builder,f'{fit.name}_Pendant_{ci+1}',pendant,sz,.027)
    rot=Euler(tuple(math.radians(v) for v in globals()[fit.name+'_STAR_ROTATION']),'XYZ').to_matrix()
    add_star(builder,fit.name+'_Tip_Star',fit.star_center(),STAR_SCALE,.058,
             rot,globals()[fit.name+'_STAR_SCALE'],beveled=True)


def empty(name,pos,col,size=.12,kind='PLAIN_AXES'):
    ob=bpy.data.objects.new(name,None); col.objects.link(ob); ob.location=pos
    ob.empty_display_type=kind; ob.empty_display_size=size; ob.hide_render=True
    return ob


def material_simple(name,color,metal=0,rough=.5):
    mat=bpy.data.materials.new(name); mat.use_nodes=True
    p=mat.node_tree.nodes.get('Principled BSDF')
    p.inputs['Base Color'].default_value=(*color,1)
    p.inputs['Metallic'].default_value=metal; p.inputs['Roughness'].default_value=rough
    return mat


def stage(col,size,samples):
    sc=bpy.context.scene
    sc.unit_settings.system='METRIC'
    sc.unit_settings.scale_length=.01
    # Official FBX units workflow: 1 modeling unit = 1 cm in FBX; Studio target
    # dimensions are explicitly reapplied from fit_manifest if importer differs.
    sc.render.engine='CYCLES'; sc.cycles.device='CPU'; sc.cycles.samples=samples
    sc.cycles.use_denoising=bool(getattr(bpy.app.build_options,'openimagedenoise',False))
    sc.render.resolution_x=size; sc.render.resolution_y=size; sc.render.resolution_percentage=100
    sc.render.image_settings.file_format='PNG'; sc.render.image_settings.color_mode='RGBA'
    sc.render.film_transparent=False
    sc.view_settings.view_transform='AgX'; sc.view_settings.look='AgX - Medium High Contrast'
    sc.world.use_nodes=True
    sc.world.node_tree.nodes['Background'].inputs[0].default_value=(.035,.018,.05,1)
    sc.world.node_tree.nodes['Background'].inputs[1].default_value=.40
    floor=material_simple('Stage_Obsidian',(.015,.011,.025),.25,.32)
    bpy.ops.mesh.primitive_plane_add(size=200,location=(0,0,-.58))
    plane=bpy.context.object; plane.name='STAGE_Not_Exported'; move_to(plane,col); plane.data.materials.append(floor)
    def light(name,loc,power,color,scale,target=(0,0,.6)):
        data=bpy.data.lights.new(name,'AREA'); data.energy=power; data.color=color; data.shape='DISK'; data.size=scale
        o=bpy.data.objects.new(name,data); col.objects.link(o); o.location=loc
        o.rotation_euler=(Vector(target)-o.location).to_track_quat('-Z','Y').to_euler()
    light('Key_Softbox',(-3,4,5),450,(1,.86,.66),4)
    light('Front_Silk',(2,4,2),240,(.73,.79,1),3)
    light('Magenta_Rim',(-2,-2,3),420,(.68,.16,1),2)
    light('Gold_Rim',(3,-2,4),500,(1,.64,.23),2)
    light('Top_Strip',(0,.5,5),200,(1,1,1),2)
    data=bpy.data.cameras.new('Presentation_Camera')
    camera=bpy.data.objects.new('Presentation_Camera',data); col.objects.link(camera)
    data.type='ORTHO'; data.ortho_scale=2.90; data.lens=52; sc.camera=camera
    # A small camera glare is presentation only; geometry is also rendered unlit
    # with the same exported atlas, not replaced by an image generation result.
    sc.use_nodes=True
    ns=sc.node_tree.nodes; ns.clear(); rl=ns.new('CompositorNodeRLayers')
    glare=ns.new('CompositorNodeGlare'); glare.glare_type='FOG_GLOW'; glare.quality='HIGH'; glare.threshold=2.0
    glare.mix=-.96
    co=ns.new('CompositorNodeComposite'); sc.node_tree.links.new(rl.outputs['Image'],glare.inputs['Image']); sc.node_tree.links.new(glare.outputs['Image'],co.inputs['Image'])
    return camera


def camera_view(cam,loc,look=(0,0,.65),scale=2.90):
    cam.location=loc; cam.rotation_euler=(Vector(look)-cam.location).to_track_quat('-Z','Y').to_euler()
    cam.data.ortho_scale=scale


def mesh_report(obj):
    me=obj.data; me.calc_loop_triangles()
    bm=bmesh.new(); bm.from_mesh(me)
    bad=sum(not e.is_manifold for e in bm.edges)
    loose=sum(not v.link_faces for v in bm.verts)
    degenerate=sum(f.calc_area()<1e-12 for f in bm.faces)
    # All disconnected components are closed surfaces in one rigid MeshPart.
    pending=set(bm.verts); components=[]
    while pending:
        seed=pending.pop(); visit={seed}; stack=[seed]
        while stack:
            x=stack.pop()
            for e in x.link_edges:
                y=e.other_vert(x)
                if y in pending:
                    pending.remove(y); visit.add(y); stack.append(y)
        components.append(len(visit))
    vol=bm.calc_volume(signed=True); bm.free()
    coords=[obj.matrix_world@v.co for v in me.vertices]
    lo=[min(v[i] for v in coords) for i in range(3)]
    hi=[max(v[i] for v in coords) for i in range(3)]
    bounds_roblox={'min':[lo[0],lo[2],-hi[1]],'max':[hi[0],hi[2],-lo[1]]}
    layer=me.uv_layers.active
    uvok=all(0<=d.uv.x<=1 and 0<=d.uv.y<=1 for d in layer.data)
    classic=all(lo[i]>=-lim-1e-6 and hi[i]<=lim+1e-6 for i,lim in enumerate((1.5,1.5,2.0)))
    normal=all(lo[i]>=-lim-1e-6 and hi[i]<=lim+1e-6 for i,lim in enumerate((.935,.935,1.25)))
    return {'vertices':len(me.vertices),'polygons':len(me.polygons),'triangles':len(me.loop_triangles),
            'triangle_budget':MAX_TRIANGLES,'triangle_budget_pass':len(me.loop_triangles)<=MAX_TRIANGLES,
            'non_manifold_edges':bad,'loose_vertices':loose,'zero_area_faces':degenerate,
            'closed_surface_components':len(components),'signed_volume':vol,
            'single_mesh':True,'material_slots':len(me.materials),'uv_sets':len(me.uv_layers),'uv_in_0_1':uvok,
            'bounds_blender':{'min':lo,'max':hi},'bounds_roblox':bounds_roblox,
            'target_size_studs':[hi[0]-lo[0],hi[2]-lo[2],hi[1]-lo[1]],
            'classic_hat_centered_bounds_pass':classic,'normal_hat_centered_bounds_pass':normal,
            'alignment_in_roblox_studio_validated':False,'ugc_publication_validated':False}


def export(obj,out):
    bpy.ops.object.select_all(action='DESELECT'); obj.hide_set(False); obj.select_set(True); bpy.context.view_layer.objects.active=obj
    bpy.ops.export_scene.fbx(filepath=str(out/'Celestial_Horns_Addon.fbx'),use_selection=True,
        object_types={'MESH'},global_scale=1.0,apply_unit_scale=True,apply_scale_options='FBX_SCALE_UNITS',
        axis_forward='-Z',axis_up='Y',use_mesh_modifiers=True,mesh_smooth_type='FACE',
        bake_anim=False,add_leaf_bones=False,path_mode='COPY',embed_textures=True)
    bpy.ops.wm.obj_export(filepath=str(out/'Celestial_Horns_Addon.obj'),export_selected_objects=True,
        forward_axis='NEGATIVE_Z',up_axis='Y',global_scale=1.0,export_materials=True,
        export_uv=True,export_normals=True,export_triangulated_mesh=True,path_mode='RELATIVE')
    # Make the readable OBJ/MTL portable even when the output directory moves.
    for mtl in out.glob('*.mtl'):
        body=mtl.read_text(encoding='utf-8')
        for line in body.splitlines():
            if line.startswith(('map_','norm ')) and 'Celestial_' in line:
                filename=line.replace('\\','/').split('/')[-1]
                body=body.replace(line,line.split(' ')[0]+' Textures/'+filename)
        mtl.write_text(body,encoding='utf-8')


def make_editable_copy(export_obj,atlas,col):
    obj=export_obj.copy(); obj.data=export_obj.data.copy()
    obj.name='Celestial_Horns_EDITABLE'; col.objects.link(obj)
    obj.data.materials.clear()
    for name,color in [('Celestial_Amethyst_Enamel',(.28,.025,.50,1)),
                       ('Celestial_Polished_Gold',(.95,.61,.14,1)),
                       ('Celestial_Luminous_Stars',(1,.79,.32,1))]:
        mat=atlas.copy(); mat.name=name; mat.diffuse_color=color
        obj.data.materials.append(mat)
    uvdata=obj.data.uv_layers.active.data
    counts=[0,0,0]
    for face in obj.data.polygons:
        u=sum(uvdata[i].uv.x for i in face.loop_indices)/len(face.loop_indices)
        slot=0 if u<.50 else 1 if u<.76 else 2
        face.material_index=slot; counts[slot]+=1
    assert min(counts)>0
    return obj,{'editable_object':obj.name,'material_slots':3,
        'face_counts':{m.name:n for m,n in zip(obj.data.materials,counts)},
        'export_object':export_obj.name,'export_material_slots':1,
        'same_geometry_as_export':True,'viewport_default':'Material Preview',
        'all_three_materials_used':True}


def configure_viewport():
    for screen in bpy.data.screens:
        for area in screen.areas:
            if area.type=='VIEW_3D':
                space=area.spaces.active
                space.shading.type='MATERIAL'
                space.shading.color_type='MATERIAL'
                if space.region_3d: space.region_3d.view_perspective='CAMERA'


def main():
    args=arguments(); apply_config(args.config)
    out=Path(args.output).resolve(); out.mkdir(parents=True,exist_ok=True); (out/'Renders').mkdir(exist_ok=True)
    clean_scene()
    editcol=collection('00_EDITABLE_Three_Materials'); assetcol=collection('01_EXPORT_Addon'); guides=collection('02_FIT_Guides_NOT_EXPORTED'); pres=collection('03_PRESENTATION_NOT_EXPORTED')
    ims=make_textures(out); mat=make_material(ims)
    builder=MeshBuilder(); fits=[SideFit('LEFT'),SideFit('RIGHT')]
    for fit in fits:
        make_horn(builder,fit); make_ribbon(builder,fit); ornaments(builder,fit)
    obj=builder.object('Celestial_Horns_Handle',assetcol,mat)
    obj['AccessoryType']='Hat'; obj['BodyScale']='Classic'; obj['AttachmentName']='HatAttachment'
    obj['OriginalAccessoryId']=str(ORIGINAL_ASSET_ID)
    obj['FitStatus']='UNVALIDATED: test with original accessory in Roblox Studio'
    obj['CoordinateNote']='Blender X right, +Y front, Z up; export X right, Y up, -Z front'
    obj['TargetUnits']='one modeling unit = one target stud; apply fit_manifest Size in Studio'
    empty('HatAttachment_GUIDE_ONLY',(0,0,0),guides,.16)
    manifest={'original_asset_id':ORIGINAL_ASSET_ID,'body_scale':'Classic','accessory_type':'Hat',
        'attachment':'HatAttachment','attachment_relative_origin_blender':[0,0,0],
        'export_axis_mapping':'Roblox (X,Y,Z) = Blender (X,Z,-Y)',
        'fit_validated_in_studio':False,'stars':{}}
    for fit in fits:
        empty(fit.name+'_ORIGINAL_STAR_TARGET',fit.target,guides,.10,'SPHERE')
        empty(fit.name+'_HORN_BASE',fit.base,guides,.08)
        p=fit.star_center()
        manifest['stars'][fit.name]={'target_blender':list(fit.target),'star_center_blender':list(p),
            'star_center_roblox':[p.x,p.z,-p.y],
            'source':'measured original target' if globals()[fit.name+'_STAR_TARGET'] is not None else 'image estimate; not measured',
            'center_target_error_model_units':float((p-fit.target).length)}
    report=mesh_report(obj)
    assert report['triangle_budget_pass'],f"{report['triangles']} exceeds {MAX_TRIANGLES}"
    assert report['non_manifold_edges']==0 and report['zero_area_faces']==0 and report['loose_vertices']==0
    assert report['uv_in_0_1'] and report['material_slots']==1
    manifest['target_size_studs']=report['target_size_studs']
    manifest['handle_geometry_center_roblox']=[sum(report['bounds_roblox'][k][i] for k in ('min','max'))/2 for i in range(3)]
    (out/'fit_manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
    helper=out/'Studio/prepare_import.luau'
    if helper.exists():
        body=helper.read_text(encoding='utf-8')
        body=re.sub(r'local targetSize = Vector3.new\([^\n]+', 'local targetSize = Vector3.new('+', '.join(f'{v:.9f}' for v in manifest['target_size_studs'])+')',body)
        body=re.sub(r'local geometryCenter = Vector3.new\([^\n]+', 'local geometryCenter = Vector3.new('+', '.join(f'{v:.9f}' for v in manifest['handle_geometry_center_roblox'])+')',body)
        helper.write_text(body,encoding='utf-8')
    (out/'quality_report.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    editable,mat_report=make_editable_copy(obj,mat,editcol)
    (out/'material_report.json').write_text(json.dumps(mat_report,indent=2),encoding='utf-8')
    cam=stage(pres,args.render_size,args.samples)
    export(obj,out)
    obj.hide_render=True; obj.hide_set(True)
    guides.hide_viewport=True
    configure_viewport()
    for image in ims.values():
        image.filepath='//Textures/'+Path(image.filepath).name
        image.pack()
    camera_view(cam,(-3.5,6,2.35))
    bpy.ops.wm.save_as_mainfile(filepath=str(out/'Celestial_Horns_Addon.blend'))
    print('CELESTIAL_GEOMETRY_REPORT',json.dumps(report),flush=True)
    if not args.no_render:
        for key,name,loc,look,scale in [
            ('front','01_Front',(0,7,.65),(0,0,.65),2.9),
            ('back','02_Back',(0,-7,.65),(0,0,.65),2.9),
            ('side','03_Side',(7,0,.65),(0,0,.65),2.6),
            ('three_quarter','04_Three_Quarter',(-3.5,6,2.35),(0,0,.65),2.9)]:
            if key not in args.views: continue
            camera_view(cam,loc,look,scale)
            bpy.context.scene.render.filepath=str(out/'Renders'/(name+'.png'))
            bpy.ops.render.render(write_still=True)
            print('CELESTIAL_RENDER_SAVED',name,flush=True)
    camera_view(cam,(-3.5,6,2.35))
    bpy.ops.object.select_all(action='DESELECT'); editable.select_set(True); bpy.context.view_layer.objects.active=editable
    bpy.ops.wm.save_as_mainfile(filepath=str(out/'Celestial_Horns_Addon.blend'))
    print('CELESTIAL_COMPLETE',str(out),flush=True)

if __name__=='__main__':
    main()
