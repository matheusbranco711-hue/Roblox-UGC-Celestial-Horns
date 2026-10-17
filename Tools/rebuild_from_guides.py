"""Run in Blender's Text Editor after moving LEFT/RIGHT_ORIGINAL_STAR_TARGET.
Updates the JSON with measured guide positions, rebuilds and exports the addon.
Use only after importing the original and aligning HatAttachment at (0,0,0).
"""
import bpy
import json
import runpy
import sys
from pathlib import Path
root = Path(bpy.path.abspath('//')).resolve()
assert (root/'create_celestial_horns.py').exists(), 'Save the blend inside the project folder first'
path = root/'fit_parameters.json'
cfg = json.loads(path.read_text(encoding='utf-8'))
for side in ('LEFT','RIGHT'):
    guide = bpy.data.objects.get(side+'_ORIGINAL_STAR_TARGET')
    assert guide, 'Missing target guide '+side
    cfg[side+'_STAR_TARGET'] = list(guide.matrix_world.translation)
path.write_text(json.dumps(cfg,indent=2),encoding='utf-8')
sys.argv = ['blender','--','--output',str(root),'--config',str(path),'--no-render']
runpy.run_path(str(root/'create_celestial_horns.py'),run_name='__main__')
