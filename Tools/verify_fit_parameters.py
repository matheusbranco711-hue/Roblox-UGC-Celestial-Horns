"""Exercise asymmetric measured targets and independent rotation/scale.
blender -b --python Tools/verify_fit_parameters.py -- /project/path
"""
import bpy
import importlib.util
import json
import sys
from pathlib import Path
from mathutils import Vector
root=Path(sys.argv[sys.argv.index('--')+1]).resolve()
spec=importlib.util.spec_from_file_location('celestial_generator',root/'create_celestial_horns.py')
m=importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
params={
 'LEFT_STAR_TARGET':[-1.02,.08,1.41], 'RIGHT_STAR_TARGET':[.96,-.04,1.52],
 'LEFT_HORN_ROTATION':[3,5,-4], 'RIGHT_HORN_ROTATION':[-2,-4,7],
 'LEFT_HORN_SCALE':[1.08,.95,.93], 'RIGHT_HORN_SCALE':[.94,1.04,1.05],
 'LEFT_STAR_ROTATION':[8,16,12], 'RIGHT_STAR_ROTATION':[-7,11,-6],
 'LEFT_STAR_SCALE':[1.1,.9,1.04], 'RIGHT_STAR_SCALE':[.95,1.1,.92]
}
scratch=root/'work'; scratch.mkdir(exist_ok=True)
cfg=scratch/'fit_stress_parameters.json'; cfg.write_text(json.dumps(params))
m.apply_config(str(cfg))
bpy.ops.wm.read_factory_settings(use_empty=True)
ref=m.collection('REFERENCE_PRESERVE_TEST'); marker=m.empty('REFERENCE_KEEP_ME',(0,0,0),ref)
m.clean_scene()
assert bpy.data.objects.get(marker.name) is marker
col=m.collection('01_EXPORT_Addon'); mat=bpy.data.materials.new('Celestial_Test')
builder=m.MeshBuilder(); fits=[m.SideFit('LEFT'),m.SideFit('RIGHT')]
for fit in fits:
 m.make_horn(builder,fit); m.make_ribbon(builder,fit); m.ornaments(builder,fit)
obj=builder.object('Celestial_Horns_Handle',col,mat)
errors={}
for fit in fits:
 ids=builder.groups[fit.name+'_Tip_Star']
 centroid=sum((obj.data.vertices[i].co for i in ids),Vector())/len(ids)
 target=Vector(params[fit.name+'_STAR_TARGET'])
 tip=obj.data.vertices[builder.groups[fit.name+'_Horn'][-1]].co
 base=obj.data.vertices[builder.groups[fit.name+'_Horn'][-2]].co
 errors[fit.name]={'actual_star_center_error':(centroid-target).length,
                   'actual_horn_tip_error':(tip-target).length,
                   'base_preservation_error':(base-fit.base).length}
 assert max(errors[fit.name].values())<1e-6,errors
report=m.mesh_report(obj)
assert report['triangles']==3800 and report['non_manifold_edges']==0
m.clean_scene()
assert bpy.data.objects.get('REFERENCE_KEEP_ME') is not None
assert bpy.data.objects.get('Celestial_Horns_Handle') is None
result={'passed':True,'parameters_exercised':params,'errors_model_units':errors,
        'preserves_reference_objects':True,'cleans_generated_objects_for_rebuild':True,
        'triangles':report['triangles'],'non_manifold_edges':report['non_manifold_edges'],
        'original_accessory_alignment_in_studio_validated':False}
(root/'fit_parameter_verification.json').write_text(json.dumps(result,indent=2))
print('FIT_PARAMETER_VERIFICATION',json.dumps(result),flush=True)
