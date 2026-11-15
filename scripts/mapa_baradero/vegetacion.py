"""Vegetacion realista CC0: importacion, thinning uniforme, LODs e instanciado.

Los modelos de Poly Haven (CC0-1.0) se importan una vez. Las tarjetas de hoja
se reducen con un hash espacial, de modo que la copa conserva densidad y
distribucion: borrar al azar dejaria huecos visibles. Las ramas y el tronco se
colapsan. Se generan LOD0 y LOD1 por especie, como pide la guia de vegetacion
para uso en juego, y las copias comparten la misma malla.
"""
from __future__ import annotations

import math
import random
from collections import Counter

import bpy
from mathutils import Vector

from . import common

ASSETS = common.ROOT / 'mapa/recursos/sanmartin'


def enum_set(data, prop, value):
    allowed = [i.identifier for i in data.bl_rna.properties[prop].enum_items]
    if value not in allowed:
        raise ValueError(f'{prop}: {value} not in {allowed}')
    setattr(data, prop, value)


def _is_leaf_material(material):
    """Los materiales de Poly Haven se llaman ..._leaves: 'leaf' no alcanza."""
    if material is None:
        return False
    name = material.name.lower()
    return 'leaf' in name or 'leaves' in name or 'foliage' in name


def _category(obj):
    """Clasifica cada slot del material: 'hoja', 'rama' o 'tronco'."""
    category = {}
    for index, slot in enumerate(obj.material_slots):
        material = slot.material
        if material is None:
            category[index] = 'rama'
            continue
        name = material.name.lower()
        if _is_leaf_material(material):
            category[index] = 'hoja'
        elif 'trunk' in name or 'bark' in name:
            category[index] = 'tronco'
        else:
            category[index] = 'rama'
    return category


def _thin_leaves_uniform(obj, keep_ratio, seed=11):
    """Reduce tarjetas de hoja con hash espacial: la cobertura se mantiene.

    Se recorre una grilla 3D sobre la copa y en cada celda se conservan las
    tarjetas cuyo hash supera el umbral. Asi la densidad es uniforme y no
    aparecen claros en una sola cara del arbol.
    """
    import bmesh
    rng = random.Random(seed)
    mesh = obj.data
    category = _category(obj)
    leaf_slots = {index for index, value in category.items() if value == 'hoja'}
    if not leaf_slots:
        return 0
    bm = bmesh.new()
    bm.from_mesh(mesh)
    bm.faces.ensure_lookup_table()
    leaf_faces = [f for f in bm.faces if f.material_index in leaf_slots]
    if not leaf_faces:
        bm.free()
        return 0
    minimum = Vector((min(f.calc_center_median().x for f in leaf_faces),
                      min(f.calc_center_median().y for f in leaf_faces),
                      min(f.calc_center_median().z for f in leaf_faces)))
    maximum = Vector((max(f.calc_center_median().x for f in leaf_faces),
                      max(f.calc_center_median().y for f in leaf_faces),
                      max(f.calc_center_median().z for f in leaf_faces)))
    span = maximum - minimum
    cells = max(4, int(math.cbrt(max(len(leaf_faces), 1)) ** 0.5))
    buckets = {}
    for face in leaf_faces:
        centre = face.calc_center_median() - minimum
        grid = []
        for axis in range(3):
            extent = span[axis] if span[axis] > 1e-6 else 1.0
            grid.append(min(cells - 1, int((centre[axis] / extent) * cells)))
        buckets.setdefault(tuple(grid), []).append(face)
    drop = []
    for key, faces in buckets.items():
        rng.shuffle(faces)
        keep = max(1, int(len(faces) * keep_ratio))
        drop.extend(faces[keep:])
    bmesh.ops.delete(bm, geom=drop, context='FACES')
    loose = [v for v in bm.verts if not v.link_faces]
    if loose:
        bmesh.ops.delete(bm, geom=loose, context='VERTS')
    bm.to_mesh(mesh)
    bm.free()
    mesh.update()
    return len(drop)


def _collapse(obj, ratio):
    if ratio >= 0.999 or not obj.data.polygons:
        return False
    modifier = obj.modifiers.new('Densidad juego', 'DECIMATE')
    modifier.ratio = max(0.02, ratio)
    modifier.decimate_type = 'COLLAPSE'
    for other in list(bpy.context.selected_objects):
        other.select_set(False)
    bpy.context.view_layer.objects.active = obj
    obj.select_set(True)
    bpy.ops.object.modifier_apply(modifier=modifier.name)
    obj.select_set(False)
    return True


def _merge_meshes(objects, name):
    """Fusiona mallas en una sola por bmesh, conservando los materiales."""
    import bmesh

    merged = bpy.data.meshes.new(f'{name}_Malla')
    target = bmesh.new()
    slots = []
    for obj in objects:
        mapping = []
        for slot in obj.material_slots:
            material = slot.material
            if material is None:
                mapping.append(None)
                continue
            if material.name not in [s.name for s in slots]:
                slots.append(material)
            mapping.append([s.name for s in slots].index(material.name))
        piece = bmesh.new()
        piece.from_mesh(obj.data)
        piece.transform(obj.matrix_world)
        piece.faces.ensure_lookup_table()
        remap = {}
        for face in piece.faces:
            index = face.material_index
            remap[index] = mapping[index] if index < len(mapping) and mapping[index] is not None else 0
        vertex_map = {}
        for vertex in piece.verts:
            vertex_map[vertex] = target.verts.new(vertex.co)
        target.verts.index_update()
        for face in piece.faces:
            try:
                new_face = target.faces.new([vertex_map[v] for v in face.verts])
            except ValueError:
                continue
            new_face.material_index = remap.get(face.material_index, 0)
            new_face.smooth = face.smooth
        piece.free()
    target.verts.index_update()
    target.to_mesh(merged)
    target.free()
    for material in slots:
        merged.materials.append(material)
    merged.update()
    return merged, slots


def _prepare_materials(slots):
    for material in slots:
        if material is None:
            continue
        material.use_backface_culling = False
        if _is_leaf_material(material):
            blend = [i.identifier for i in
                     bpy.types.Material.bl_rna.properties['blend_method'].enum_items]
            if 'BLEND' in blend:
                material.blend_method = 'BLEND'
            shadow = [i.identifier for i in
                      bpy.types.Material.bl_rna.properties['shadow_method'].enum_items]
            if 'HASHED' in shadow:
                material.shadow_method = 'HASHED'


def import_template(asset, name, leaf_keep=0.30, branch_ratio=0.30, trunk_ratio=0.45):
    """Importa un modelo CC0 y deja una plantilla LOD0 ligera y reutilizable."""
    folder = ASSETS / asset
    path = folder / f'{asset}_1k.gltf'
    before = set(bpy.data.objects)
    bpy.ops.import_scene.gltf(filepath=str(path))
    imported = [o for o in bpy.data.objects if o not in before]
    meshes = [o for o in imported if o.type == 'MESH' and o.data.polygons]
    if not meshes:
        raise RuntimeError(f'{asset}: la importacion no produjo mallas')
    merged_mesh, slots = _merge_meshes(meshes, name)
    for obj in imported:
        bpy.data.objects.remove(obj, do_unlink=True)
    template = bpy.data.objects.new(name, merged_mesh)
    bpy.context.scene.collection.objects.link(template)
    _prepare_materials(slots)
    total = len(merged_mesh.polygons)
    dropped = _thin_leaves_uniform(template, leaf_keep)
    collapsed = _collapse(template, branch_ratio)
    final = len(merged_mesh.polygons)
    template['bara_kind'] = 'vegetacion_cc0'
    template['bara_asset'] = name
    template['bara_license'] = 'CC0-1.0 Poly Haven'
    template['bara_notice'] = 'Modelo CC0 de Poly Haven, simplificado para uso en juego'
    template['bara_source_tris'] = total
    template['bara_final_tris'] = final
    template['bara_source_asset'] = asset
    template['bara_lod'] = 0
    return template, total, final


def make_lod1(template, name, leaf_keep=0.55, collapse_ratio=0.45):
    """LOD1: menos tarjetas de hoja y ramas colapsadas, para distancia."""
    import bmesh
    mesh = template.data.copy()
    mesh.name = f'{name}_Malla'
    lod = bpy.data.objects.new(name, mesh)
    bpy.context.scene.collection.objects.link(lod)
    lod.matrix_world = template.matrix_world.copy()
    _thin_leaves_uniform(lod, leaf_keep, seed=29)
    _collapse(lod, collapse_ratio)
    lod['bara_kind'] = 'vegetacion_cc0'
    lod['bara_asset'] = name
    lod['bara_license'] = 'CC0-1.0 Poly Haven'
    lod['bara_lod'] = 1
    lod['bara_source_tris'] = len(mesh.polygons)
    lod['bara_final_tris'] = len(mesh.polygons)
    return lod


def instance(template, name, location, rotation_z=0.0, scale=1.0, collection=None,
             lod=0):
    """Copia con datos compartidos: una sola malla en memoria por especie."""
    obj = bpy.data.objects.new(name, template.data)
    (collection or template.users_collection[0]).objects.link(obj)
    obj.location = location
    obj.rotation_euler = (0.0, 0.0, rotation_z)
    obj.scale = (scale, scale, scale)
    obj['bara_kind'] = 'vegetacion_cc0_instancia'
    obj['bara_asset'] = template.get('bara_asset', '')
    obj['bara_license'] = 'CC0-1.0 Poly Haven'
    obj['bara_lod'] = lod
    return obj


def measure(objects):
    counts = Counter()
    tris = 0
    for obj in objects:
        counts[obj.get('bara_kind')] += 1
        if obj.type == 'MESH':
            tris += sum(max(0, len(p.vertices) - 2) for p in obj.data.polygons)
    return counts, tris
