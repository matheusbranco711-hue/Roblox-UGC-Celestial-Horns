"""Meaningful round-trip checks. Run with Blender 4.3+ in a fresh process:
blender -b --python Tools/verify_exports.py -- /path/to/project
"""
import bpy
import bmesh
import json
import sys
from pathlib import Path
from mathutils.kdtree import KDTree
root=Path(sys.argv[sys.argv.index('--')+1]).resolve()
results={'blender':bpy.app.version_string,'formats':{},'roblox_studio_tested':False}
for ext in ('blend','fbx','obj'):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.context.scene.unit_settings.system='METRIC'
    bpy.context.scene.unit_settings.scale_length=.01
    path=root/('Celestial_Horns_Addon.'+ext)
    assert path.exists() and path.stat().st_size>1000, str(path)
    if ext=='blend':
        bpy.ops.wm.open_mainfile(filepath=str(path))
        meshes=[bpy.data.objects['Celestial_Horns_Handle']]
    elif ext=='fbx':
        bpy.ops.import_scene.fbx(filepath=str(path))
        meshes=[o for o in bpy.context.scene.objects if o.type=='MESH']
    else:
        bpy.ops.wm.obj_import(filepath=str(path),forward_axis='NEGATIVE_Z',up_axis='Y')
        meshes=[o for o in bpy.context.scene.objects if o.type=='MESH']
    bpy.context.view_layer.update()
    assert len(meshes)==1, (ext,'expected exactly one shipping mesh')
    obj=meshes[0]; me=obj.data; me.calc_loop_triangles()
    bm=bmesh.new(); bm.from_mesh(me)
    bad=sum(not e.is_manifold for e in bm.edges)
    degenerate=sum(f.calc_area()<1e-12 for f in bm.faces)
    vol=bm.calc_volume(signed=True); bm.free()
    world=[obj.matrix_world@v.co for v in me.vertices]
    world_dimensions=[max(v[i] for v in world)-min(v[i] for v in world) for i in range(3)]
    report={'mesh_objects':1,'triangles':len(me.loop_triangles),'materials':len(me.materials),
            'uv_sets':len(me.uv_layers),'non_manifold_edges':bad,'zero_area_faces':degenerate,
            'signed_volume':vol,'dimensions_world_blender_units':world_dimensions}
    assert report['triangles']==3800,(ext,report)
    assert bad==0 and degenerate==0 and vol>0,(ext,report)
    assert len(me.materials)==1 and len(me.uv_layers)==1,(ext,report)
    assert all(0<=d.uv.x<=1 and 0<=d.uv.y<=1 for d in me.uv_layers.active.data)
    if ext=='blend':
        base_dimensions=world_dimensions
        base_kd=KDTree(len(world))
        for i,co in enumerate(world): base_kd.insert(co,i)
        base_kd.balance()
        kd=KDTree(len(me.vertices))
        for i,v in enumerate(me.vertices): kd.insert(v.co,i)
        kd.balance()
        worst=max(kd.find((-v.co.x,v.co.y,v.co.z))[2] for v in me.vertices)
        report['front_mirror_max_error']=worst
        assert worst<1e-5,report
        assert len([im for im in bpy.data.images if im.packed_file])==5
        for side in ('LEFT','RIGHT'):
            group=obj.vertex_groups[side+'_Tip_Star']
            verts=[v.co for v in me.vertices if any(g.group==group.index for g in v.groups)]
            from mathutils import Vector
            centroid=sum(verts,Vector())/len(verts)
            target=bpy.data.objects[side+'_ORIGINAL_STAR_TARGET'].location
            assert (centroid-target).length<1e-6,(side,centroid,target)
    else:
        assert max(abs(a-b) for a,b in zip(world_dimensions,base_dimensions))<1e-5,(ext,world_dimensions,base_dimensions)
        report['roundtrip_vertex_max_error']=max(base_kd.find(v)[2] for v in world)
        assert report['roundtrip_vertex_max_error']<1e-5,report
    results['formats'][ext]=report
for name in ('01_Front','02_Back','03_Side','04_Three_Quarter'):
    p=root/'Renders'/(name+'.png')
    assert p.exists() and p.stat().st_size>10000,p
results['render_files_present']=4
results['passed']=True
(root/'verification_report.json').write_text(json.dumps(results,indent=2),encoding='utf-8')
print('ROUNDTRIP_VERIFICATION',json.dumps(results),flush=True)
