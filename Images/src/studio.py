"""Shared Blender studio for the README renders of these Voron mods.

Imported by render_overview.py in this folder; the same file sits in each mod's
Images/src folder so every repo can rebuild its own pictures. It sets up one look
for all of them: a flat light background, soft contact shadows, orthographic
three-quarter camera (so parts of different sizes compare fairly), the mod parts
in green and Voron's originals in grey.

Rendered with Eevee, so it runs on whatever GPU Blender can open (it falls back to
software OpenGL if there is none). Tested with Blender 5.2.
"""
import math
import struct
from pathlib import Path

import bpy
import numpy as np
from mathutils import Matrix, Vector

BACKGROUND = '#f6f8fa'
MOD_GREEN = '#3fb950'
VORON_GREY = '#9ea4aa'
# Light strengths, tuned so a level face of a part renders close to its own colour.
SKY = 0.28
SHADOW_FLOOR = 0.5    # brightness of the floor in the deepest shadow, as a share of the background
LIGHTS = (  # name, strength, (azimuth, elevation) in degrees, softness in degrees
    ('key', 2.1, (-70, 45), 6),
    ('fill', 0.55, (55, 35), 30),
    ('rim', 0.7, (165, 40), 20),
)
UNIT = 0.01    # parts are laid out in mm, then shrunk to metres-ish so Eevee's shadows behave
REC = np.dtype([('n', '<3f4'), ('v', '<9f4'), ('a', '<u2')])


def linear(hex_colour):
    """sRGB hex to Blender's linear RGBA."""
    c = [int(hex_colour.lstrip('#')[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    return tuple(x / 12.92 if x <= 0.04045 else ((x + 0.055) / 1.055) ** 2.4 for x in c) + (1.0,)


def reset():
    bpy.ops.wm.read_factory_settings(use_empty=True)


def load_stl(path, name=None):
    """Read a binary STL into a welded mesh object with smooth shading on curves."""
    b = Path(path).read_bytes()
    n = struct.unpack('<I', b[80:84])[0]
    if len(b) < 84 + 50 * n:
        raise SystemExit(f'{path} is not a binary STL')
    v = np.frombuffer(b[84:84 + n * 50], dtype=REC)['v'].reshape(-1, 3).astype(np.float64)
    verts, idx = np.unique(np.round(v, 4), axis=0, return_inverse=True)
    faces = idx.reshape(-1, 3)
    faces = faces[(faces[:, 0] != faces[:, 1]) & (faces[:, 1] != faces[:, 2]) & (faces[:, 0] != faces[:, 2])]
    mesh = bpy.data.meshes.new(name or Path(path).stem)
    mesh.from_pydata(verts.tolist(), [], faces.tolist())
    mesh.validate()
    mesh.shade_smooth()
    mesh.set_sharp_from_angle(angle=math.radians(30))
    obj = bpy.data.objects.new('part:' + mesh.name, mesh)
    bpy.context.scene.collection.objects.link(obj)
    return obj


def place(obj, x=0.0, y=0.0, rot_z=0.0, flip_x=False, origin=None):
    """Rest the part on the ground with its footprint centred on (x, y), turned rot_z degrees.

    With origin=(ox, oy), the file's point (ox, oy) goes to (x, y) instead, so parts drawn
    in the same coordinates (a mod and Voron's original) line up exactly.
    """
    m = obj.data
    if flip_x:
        m.transform(Matrix.Scale(-1, 4, (1, 0, 0)))
        m.flip_normals()
    m.transform(Matrix.Rotation(math.radians(rot_z), 4, 'Z'))
    co = np.array([vv.co[:] for vv in m.vertices])
    lo, hi = co.min(0), co.max(0)
    cx, cy = ((lo[0] + hi[0]) / 2, (lo[1] + hi[1]) / 2) if origin is None else origin
    m.transform(Matrix.Translation(Vector((-cx, -cy, -lo[2]))))
    obj.location = (x, y, 0)
    return hi - lo


def part_material(hex_colour, name):
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes['Principled BSDF']
    bsdf.inputs['Base Color'].default_value = linear(hex_colour)
    bsdf.inputs['Roughness'].default_value = 0.55
    bsdf.inputs['Specular IOR Level'].default_value = 0.25
    return mat


def paint(obj, mat):
    obj.data.materials.clear()
    obj.data.materials.append(mat)


def _shrink_parts():
    """Scale the layout from millimetres down so lights, shadows and camera work at a sane size."""
    root = bpy.data.objects.new('layout', None)
    bpy.context.scene.collection.objects.link(root)
    for obj in list(bpy.context.scene.objects):
        if obj.name.startswith('part:'):
            obj.parent = root
    root.scale = (UNIT, UNIT, UNIT)
    bpy.context.view_layer.update()


def _ground():
    """A floor that shows only soft shadows on the flat background colour."""
    bpy.ops.mesh.primitive_plane_add(size=100)
    ground = bpy.context.active_object
    mat = bpy.data.materials.new('shadow floor')
    mat.use_nodes = True
    nt = mat.node_tree
    nt.nodes.clear()
    diffuse = nt.nodes.new('ShaderNodeBsdfDiffuse')
    diffuse.inputs['Color'].default_value = (1, 1, 1, 1)
    to_rgb = nt.nodes.new('ShaderNodeShaderToRGB')
    gray = nt.nodes.new('ShaderNodeRGBToBW')
    lit = nt.nodes.new('ShaderNodeMapRange')       # how lit the floor is, 0 in shadow to 1 in full light
    lit.inputs['From Min'].default_value = 0.0
    lit.inputs['From Max'].default_value = 0.0      # set by lighting()
    lit.inputs['To Min'].default_value = 0.0
    lit.inputs['To Max'].default_value = 1.0
    lit.clamp = True
    lit.name = 'lit'
    floor = nt.nodes.new('ShaderNodeMapRange')
    floor.inputs['From Min'].default_value = 0.0
    floor.inputs['From Max'].default_value = 1.0
    floor.inputs['To Min'].default_value = SHADOW_FLOOR
    floor.inputs['To Max'].default_value = 1.0
    mix = nt.nodes.new('ShaderNodeMix')
    mix.data_type = 'RGBA'
    mix.blend_type = 'MULTIPLY'
    mix.inputs['Factor'].default_value = 1.0
    mix.inputs['A'].default_value = linear(BACKGROUND)
    emit = nt.nodes.new('ShaderNodeEmission')
    out = nt.nodes.new('ShaderNodeOutputMaterial')
    nt.links.new(diffuse.outputs[0], to_rgb.inputs[0])
    nt.links.new(to_rgb.outputs['Color'], gray.inputs[0])
    nt.links.new(gray.outputs[0], lit.inputs['Value'])
    nt.links.new(lit.outputs[0], floor.inputs['Value'])
    nt.links.new(floor.outputs[0], mix.inputs['B'])
    nt.links.new(mix.outputs['Result'], emit.inputs['Color'])
    nt.links.new(emit.outputs[0], out.inputs['Surface'])
    ground.data.materials.append(mat)
    ground.visible_shadow = False
    return lit


def _world():
    """Background pixels are exactly BACKGROUND; light from the sky is a soft neutral fill."""
    world = bpy.data.worlds.new('studio')
    bpy.context.scene.world = world
    world.use_nodes = True
    nt = world.node_tree
    nt.nodes.clear()
    path = nt.nodes.new('ShaderNodeLightPath')
    seen = nt.nodes.new('ShaderNodeBackground')
    seen.inputs['Color'].default_value = linear(BACKGROUND)
    fill = nt.nodes.new('ShaderNodeBackground')
    fill.inputs['Color'].default_value = (1, 1, 1, 1)
    fill.inputs['Strength'].default_value = SKY
    mix = nt.nodes.new('ShaderNodeMixShader')
    out = nt.nodes.new('ShaderNodeOutputWorld')
    nt.links.new(path.outputs['Is Camera Ray'], mix.inputs['Fac'])
    nt.links.new(fill.outputs[0], mix.inputs[1])
    nt.links.new(seen.outputs[0], mix.inputs[2])
    nt.links.new(mix.outputs[0], out.inputs['Surface'])


def _light(name, kind, energy, direction_deg, angle_or_size, distance=20):
    data = bpy.data.lights.new(name, kind)
    data.energy = energy
    if kind == 'SUN':
        data.angle = math.radians(angle_or_size)
    else:
        data.size = angle_or_size
    obj = bpy.data.objects.new(name, data)
    bpy.context.scene.collection.objects.link(obj)
    az, el = (math.radians(a) for a in direction_deg)
    d = Vector((math.cos(el) * math.sin(az), -math.cos(el) * math.cos(az), math.sin(el)))
    obj.location = d * distance
    obj.rotation_euler = (-d).to_track_quat('-Z', 'Y').to_euler()
    return obj


def lighting():
    """Key from the left, a softer fill from the front right, a rim from behind."""
    _shrink_parts()
    _world()
    lit = _ground()
    for name, energy, direction, soft in LIGHTS:
        _light(name, 'SUN', energy, direction, soft)
    # Unshadowed floor brightness: every light on a level white surface, plus the sky.
    unshadowed = sum(e * math.sin(math.radians(d[1])) for _, e, d, _ in LIGHTS) / math.pi + SKY
    lit.inputs['From Min'].default_value = 0.55 * unshadowed
    lit.inputs['From Max'].default_value = 0.97 * unshadowed


def camera_three_quarter(width_px, height_px, azimuth=-32, elevation=38, margin=0.06):
    """Orthographic camera looking down at the parts from the front left, framed to fit."""
    scene = bpy.context.scene
    scene.render.resolution_x = width_px
    scene.render.resolution_y = height_px
    cam_data = bpy.data.cameras.new('camera')
    cam_data.type = 'ORTHO'
    cam_data.clip_start = 0.1
    cam_data.clip_end = 200
    cam = bpy.data.objects.new('camera', cam_data)
    scene.collection.objects.link(cam)
    scene.camera = cam
    az, el = math.radians(azimuth), math.radians(elevation)
    d = Vector((math.sin(az) * math.cos(el), -math.cos(az) * math.cos(el), math.sin(el)))
    cam.location = d * 40
    cam.rotation_euler = (-d).to_track_quat('-Z', 'Y').to_euler()
    bpy.context.view_layer.update()
    to_cam = cam.matrix_world.inverted()
    pts = []
    for obj in scene.objects:
        if obj.type == 'MESH' and obj.name.startswith('part:'):
            mw = obj.matrix_world
            pts.extend((to_cam @ (mw @ v.co))[:2] for v in obj.data.vertices)
    pts = np.array(pts)
    lo, hi = pts.min(0), pts.max(0)
    w, h = hi - lo
    aspect = width_px / height_px
    scale = max(w, h * aspect) * (1 + 2 * margin)
    cam_data.ortho_scale = scale
    cx, cy = (lo + hi) / 2
    cam_data.shift_x = cx / scale
    cam_data.shift_y = cy / scale
    return cam


def render(out_path, samples=64):
    scene = bpy.context.scene
    scene.render.engine = 'BLENDER_EEVEE'
    eevee = scene.eevee
    eevee.taa_render_samples = samples
    for attr, value in (('use_raytracing', True), ('use_shadows', True),
                        ('shadow_ray_count', 4), ('shadow_step_count', 16),
                        ('use_gtao', True), ('gtao_distance', 0.06),
                        ('fast_gi_distance', 0.06)):
        if hasattr(eevee, attr):
            setattr(eevee, attr, value)
    scene.view_settings.view_transform = 'Standard'
    scene.view_settings.look = 'None'
    scene.view_settings.exposure = 0
    scene.render.film_transparent = False
    scene.render.image_settings.file_format = 'PNG'
    scene.render.image_settings.color_mode = 'RGB'
    scene.render.image_settings.compression = 90
    scene.render.filepath = str(Path(out_path).resolve())
    bpy.ops.render.render(write_still=True)
    import gpu
    print('rendered with', gpu.platform.renderer_get())
