"""Materiales PBR y mapeo UV para superficies existentes y nuevas.

Usa texturas CC0 de Poly Haven. Los materiales se construyen con Principled BSDF
y mapas de color, rugosidad y normales: son exportables a glTF y por tanto
compatibles con Godot. La proyeccion UV es en caja sobre coordenadas de mundo,
de modo que las teselas grandes de calle y vereda conserven escala real.
"""
from __future__ import annotations

import math
from pathlib import Path

import bpy
from mathutils import Vector

from . import common

ASSETS = common.ROOT / 'mapa/recursos/sanmartin'
AUTHORED = ASSETS / 'authored'


def enum_set(data, prop, value):
    allowed = [i.identifier for i in data.bl_rna.properties[prop].enum_items]
    if value not in allowed:
        raise ValueError(f'{prop}: {value} not in {allowed}')
    setattr(data, prop, value)


def _image(path, non_color=False):
    image = bpy.data.images.load(str(path), check_existing=True)
    if non_color:
        image.colorspace_settings.name = 'Non-Color'
    return image


def tinted_albedo(source, name, tint, strength=1.0):
    """Gris de la textura teñido con el color de marca; PNG en disco para glTF."""
    import numpy as np
    AUTHORED.mkdir(parents=True, exist_ok=True)
    target = AUTHORED / f'{name}.png'
    if not target.is_file():
        pixels = np.empty(len(source.pixels), dtype=np.float32)
        source.pixels.foreach_get(pixels)
        rgba = pixels.reshape(-1, 4)
        grey = rgba[:, :3].mean(axis=1)
        mean = max(float(grey.mean()), 1e-4)
        rgba[:, :3] = np.clip((grey / mean)[:, None] * np.array(tint, dtype=np.float32)[None, :]
                              * strength, 0.0, 1.0)
        generated = bpy.data.images.new(f'SM_{name}', width=source.size[0], height=source.size[1])
        generated.pixels.foreach_set(np.ascontiguousarray(rgba).ravel())
        generated.filepath_raw = str(target)
        enum_set(generated, 'file_format', 'PNG')
        generated.save()
        bpy.data.images.remove(generated)
    return _image(target)


def pbr_material(name, base_color, texture=None, roughness=.8, metallic=0.0,
                 tint=None, tile_m=2.0, normal_strength=.6, emissive=None):
    """Material maestro reutilizable; una instancia por superficie."""
    mat = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    mat.use_nodes = True
    nodes, links = mat.node_tree.nodes, mat.node_tree.links
    shader = next((n for n in nodes if n.type == 'BSDF_PRINCIPLED'), None)
    if shader is None:
        raise RuntimeError(f'{name}: sin Principled BSDF')
    for node in list(nodes):
        if node.type != 'BSDF_PRINCIPLED':
            nodes.remove(node)
    shader.inputs['Base Color'].default_value = (*base_color, 1.0)
    shader.inputs['Roughness'].default_value = roughness
    shader.inputs['Metallic'].default_value = metallic
    if emissive is not None:
        shader.inputs['Emission Color'].default_value = (*emissive, 1.0)
        shader.inputs['Emission Strength'].default_value = 1.0
    mat.diffuse_color = (*base_color, 1.0)
    mat.roughness = roughness
    mat.metallic = metallic
    mat['tile_m'] = float(tile_m)
    if texture:
        folder = ASSETS / texture
        diffuse = _image(folder / f'{texture}_diff_1k.jpg')
        if tint is not None:
            diffuse = tinted_albedo(diffuse, f'{texture}_{name}', tint)
        tex = nodes.new('ShaderNodeTexImage')
        tex.image = diffuse
        tex.extension = 'REPEAT'
        tex.location = (-800, 300)
        links.new(tex.outputs['Color'], shader.inputs['Base Color'])
        rough = nodes.new('ShaderNodeTexImage')
        rough.image = _image(folder / f'{texture}_rough_1k.jpg', non_color=True)
        rough.extension = 'REPEAT'
        rough.location = (-800, 0)
        links.new(rough.outputs['Color'], shader.inputs['Roughness'])
        normal_tex = nodes.new('ShaderNodeTexImage')
        normal_tex.image = _image(folder / f'{texture}_nor_gl_1k.jpg', non_color=True)
        normal_tex.extension = 'REPEAT'
        normal_tex.location = (-800, -300)
        normal = nodes.new('ShaderNodeNormalMap')
        normal.inputs['Strength'].default_value = normal_strength
        normal.location = (-400, -300)
        links.new(normal_tex.outputs['Color'], normal.inputs['Color'])
        links.new(normal.outputs['Normal'], shader.inputs['Normal'])
    mat['bara_license'] = 'CC0-1.0 Poly Haven' if texture else 'BARA-DRIVE authored'
    return mat


def box_uv(obj, tile_m=2.0, world=True):
    """UV en caja, en metros de mundo, para que la textura tenga escala real."""
    if obj.type != 'MESH' or not obj.data.polygons:
        return False
    mesh = obj.data
    layer = mesh.uv_layers.get('UVMap') or mesh.uv_layers.new(name='UVMap')
    for face in mesh.polygons:
        normal = face.normal
        axis = max(range(3), key=lambda i: abs(normal[i]))
        axes = [i for i in range(3) if i != axis]
        for loop_index in face.loop_indices:
            co = mesh.vertices[mesh.loops[loop_index].vertex_index].co
            if world:
                co = obj.matrix_world @ co
            layer.data[loop_index].uv = (co[axes[0]] / tile_m, co[axes[1]] / tile_m)
    mesh.update()
    return True


def recalc_normals(obj):
    """Reorienta las normales hacia fuera.

    Las teselas generadas por prismas tienen caras con orientacion mixta. Con
    un mapa de normales PBR esas caras se dibujan casi negras; corregirlas es
    lo que hace legible el asfalto y las veredas.
    """
    import bmesh
    if obj.type != 'MESH' or not obj.data.polygons:
        return False
    mesh = obj.data
    bm = bmesh.new()
    bm.from_mesh(mesh)
    bmesh.ops.recalc_face_normals(bm, faces=list(bm.faces))
    bm.to_mesh(mesh)
    bm.free()
    mesh.update()
    return True


def assign(bpy, obj, mat, tile_m=None, fix_normals=False):
    obj.data.materials.clear()
    obj.data.materials.append(mat)
    if fix_normals:
        recalc_normals(obj)
    if tile_m:
        box_uv(obj, tile_m)
    obj['bara_pbr'] = True
    obj['bara_material'] = mat.name
    return obj


def surface_materials():
    """Maestros PBR del entorno urbano."""
    return {
        'asfalto': pbr_material('MAT_SM_Asfalto', (0.075, 0.075, 0.070), 'asphalt_02',
                                roughness=.92, tile_m=3.0, normal_strength=.8),
        'vereda': pbr_material('MAT_SM_Vereda', (0.34, 0.32, 0.28), 'concrete_pavement',
                                roughness=.88, tile_m=2.0, normal_strength=.55),
        'cesped': pbr_material('MAT_SM_Cesped', (0.085, 0.16, 0.045), 'grass_ground',
                                roughness=.95, tile_m=3.0, normal_strength=.5),
        'revoque': pbr_material('MAT_SM_Revoque', (0.62, 0.59, 0.52), 'grey_plaster',
                                 roughness=.85, tile_m=2.0, normal_strength=.45),
    }
