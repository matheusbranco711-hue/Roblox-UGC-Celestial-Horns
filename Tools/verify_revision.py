"""Check visible spiral volume, actual materials and unchanged star targets."""
import bpy
import importlib.util
import json
import math
import sys
from pathlib import Path
from mathutils import Vector
import numpy as np
root=Path(sys.argv[sys.argv.index('--')+1]).resolve()
spec=importlib.util.spec_from_file_location('celestial_generator',root/'create_celestial_horns.py')
m=importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
m.apply_config(str(root/'fit_parameters.json'))
bpy.ops.wm.open_mainfile(filepath=str(root/'Celestial_Horns_Addon.blend'))
obj=bpy.data.objects['Celestial_Horns_Handle']; me=obj.data
fit=m.SideFit('RIGHT')
def group(name):
 g=obj.vertex_groups[name]
 return [v for v in me.vertices if any(e.group==g.index for e in v.groups)]
verts=group('RIGHT_Horn'); n=m.RADIAL_SEGMENTS; steps=m.HORN_SEGMENTS
base=verts[-2].co; tip=verts[-1].co
center_deviation=[]; ratios=[]
for k in range(steps+1):
 row=[v.co for v in verts[k*n:(k+1)*n]]
 centroid=sum(row,Vector())/n; t=k/steps
 straight=base.lerp(tip,t)
 center_deviation.append(Vector((centroid.x-straight.x,centroid.y-straight.y,0)).length)
 if .12<t<.91:
  ratios.append((max(v.x for v in row)-min(v.x for v in row))/(2*m.envelope(t)))
body_contrast=max(ratios)/min(ratios)
assert max(center_deviation)>.08,center_deviation
assert body_contrast>1.20,body_contrast
ribbon=group('RIGHT_Gold_Helix'); angles=[]
for k in range(m.RIBBON_SEGMENTS+1):
 t=.035+.935*k/m.RIBBON_SEGMENTS
 c=sum((v.co for v in ribbon[k*6:(k+1)*6]),Vector())/6
 offset=c-fit.point(m.center(t),t)
 angles.append(math.atan2(offset.y,offset.x))
turns=abs(float(np.unwrap(angles)[-1]-np.unwrap(angles)[0]))/(2*math.pi)
assert turns>2.2,turns
manifest=json.loads((root/'fit_manifest.json').read_text())
previous=root/'work/revision2/before_fit_manifest.json'
if previous.exists():
 old=json.loads(previous.read_text())
else:
 # Delivered v1 centers, preserved here to keep this check reproducible.
 old={'stars':{'LEFT':{'star_center_blender':[-.9000000357627869,0,1.350000023841858]},
               'RIGHT':{'star_center_blender':[.9000000357627869,0,1.350000023841858]}}}
errors={side:(Vector(manifest['stars'][side]['star_center_blender'])-Vector(old['stars'][side]['star_center_blender'])).length for side in ('LEFT','RIGHT')}
assert max(errors.values())<1e-6,errors
auth=bpy.data.objects['Celestial_Horns_EDITABLE']
materials=json.loads((root/'material_report.json').read_text())
assert len(auth.data.materials)==3 and materials['all_three_materials_used']
result={'revision':2,'passed':True,'max_body_centerline_deviation':max(center_deviation),
 'normalized_front_width_variation_ratio':body_contrast,'measured_gold_spiral_turns':turns,
 'star_center_change_from_v1':errors,'star_targets_preserved':True,
 'three_editable_materials_used':True,'triangles':len(me.loop_triangles),
 'roblox_studio_alignment_validated':False}
me.calc_loop_triangles(); result['triangles']=len(me.loop_triangles)
(root/'revision_verification.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
print('REVISION_VERIFICATION',json.dumps(result),flush=True)
