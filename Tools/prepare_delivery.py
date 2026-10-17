"""Refresh small Studio helper constants and compose the actual render sheet.
Run after the Blender build. Requires Pillow only for the contact sheet.
"""
import json
import re
from pathlib import Path
root=Path(__file__).resolve().parent.parent
manifest=json.loads((root/'fit_manifest.json').read_text())
p=root/'Studio/prepare_import.luau'
s=p.read_text()
s=re.sub(r'local targetSize = Vector3.new\([^\n]+', 'local targetSize = Vector3.new('+', '.join(f'{x:.9f}' for x in manifest['target_size_studs'])+')',s)
s=re.sub(r'local geometryCenter = Vector3.new\([^\n]+', 'local geometryCenter = Vector3.new('+', '.join(f'{x:.9f}' for x in manifest['handle_geometry_center_roblox'])+')',s)
p.write_text(s)
from PIL import Image,ImageDraw,ImageFont
fontpath='/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'
try:
    title=ImageFont.truetype(fontpath,42); sub=ImageFont.truetype(fontpath,19); label=ImageFont.truetype(fontpath,22)
except OSError:
    title=sub=label=ImageFont.load_default()
w=1600; h=1800
canvas=Image.new('RGB',(w,h),(15,13,23)); d=ImageDraw.Draw(canvas)
d.text((64,34),'CELESTIAL HORNS',font=title,fill=(248,222,166))
d.text((65,94),'ROBLOX UGC ADDON  /  AMETHYST & GOLD',font=sub,fill=(161,147,181))
for i,(filename,caption) in enumerate([('01_Front','FRENTE'),('02_Back','TRÁS'),('03_Side','LADO'),('04_Three_Quarter','PERSPECTIVA 3/4')]):
    x=40+(i%2)*780; y=150+(i//2)*790
    im=Image.open(root/'Renders'/(filename+'.png')).convert('RGB').resize((740,740),Image.Resampling.LANCZOS)
    canvas.paste(im,(x,y)); d.rounded_rectangle((x,y,x+740,y+740),radius=6,outline=(99,77,49),width=2)
    d.text((x+20,y+748),caption,font=label,fill=(234,210,161))
d.text((60,1740),'3.800 triângulos  |  1 malha  |  PBR  |  encaixe com a tiara original pendente no Studio',font=sub,fill=(155,145,169))
canvas.save(root/'Renders/00_Presentation.jpg',quality=93)
print('Delivery constants and render sheet refreshed')
