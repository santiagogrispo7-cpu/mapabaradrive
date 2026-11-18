"""Correccion puntual de la calle de prueba PB_ en Blender 4.2.

En Blender: main('inspect') no modifica objetos; main('apply') respalda la
escena abierta, elimina solo los 23 objetos comprobados y guarda otra version.
En consola: blender --background --python este_script.py -- --verify
reabre la salida y compara todos los objetos conservados con el manifiesto.
"""
import hashlib
import json
import sys
from datetime import datetime
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))
from mapa_baradero import common, inspection
common.add_dependency_path()
from shapely.geometry import LineString, Polygon, box
from shapely.ops import unary_union
from mapa_baradero import streets

ROOT = common.ROOT
SOURCE = ROOT / 'mapa/blender/Baradero_Realista_v2.blend'
OUTPUT = ROOT / 'mapa/blender/Baradero_Calles_Corregidas.blend'
REPORT = ROOT / 'docs/correccion_calles_baradero.json'
TARGETS = ['PB_Calle_Asfalto', 'PB_Vereda_Norte', 'PB_Vereda_Sur'] + [
    f'PB_Linea_Central_{i:02d}' for i in range(1, 21)]


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def footprint(obj):
    """Union de caras proyectadas, no envolvente de la tesela completa."""
    vertices = [obj.matrix_world @ v.co for v in obj.data.vertices]
    polygons = []
    for face in obj.data.polygons:
        p = Polygon([(vertices[i].x, vertices[i].y) for i in face.vertices])
        if p.is_valid and p.area > 1e-8:
            polygons.append(p)
    return unary_union(polygons)


def state(obj):
    return {'signature': inspection.mesh_signature(obj),
            'collections': sorted(c.name for c in obj.users_collection),
            'hide_render': obj.hide_render, 'hide_viewport': obj.hide_viewport,
            'hide_get': obj.hide_get()}


def enum_set(data, prop, value):
    allowed = [i.identifier for i in data.bl_rna.properties[prop].enum_items]
    if value not in allowed:
        raise ValueError(f'{prop}: {value} no esta en {allowed}')
    setattr(data, prop, value)


def audit(bpy):
    cfg = common.load_config(ROOT / 'scripts/mapa_config.json')
    base, osm, matched = inspection.inspect(bpy, cfg, ROOT / cfg['osm'])
    plaza = Polygon([osm['nodes'][r]['xy'] for r in osm['ways']['239949279']['refs']])
    zone = plaza.buffer(40)
    ways, skipped = streets.collect_ways(bpy, cfg, osm)
    nearby_ways = []
    for wid, way in osm['ways'].items():
        if 'highway' not in way['tags']:
            continue
        line = LineString([osm['nodes'][r]['xy'] for r in way['refs']])
        if line.distance(plaza) < 40:
            nearby_ways.append({'id': wid, 'name': way['tags'].get('name'),
                                'distance_plaza_m': line.distance(plaza),
                                'points': list(line.coords)})

    # Inspeccionar todas las superficies de calle cercanas, incluidas teselas,
    # mallas originales OSM y el tramo de prueba sin identificador geografico.
    nearby_objects = []
    actual = {layer: [] for layer in ('CALZADA', 'CORDON', 'VEREDA')}
    for obj in bpy.context.scene.objects:
        if obj.type != 'MESH':
            continue
        is_road = (obj.get('bara_layer') in actual or obj.get('osm_way_id')
                   or obj.name.startswith('PB_'))
        if not is_road:
            continue
        shape = footprint(obj)
        if not shape.intersects(zone):
            continue
        nearby_objects.append({'name': obj.name, 'collections': [c.name for c in obj.users_collection],
                               'osm_way_id': obj.get('osm_way_id'),
                               'layer': obj.get('bara_layer'), 'bounds': list(shape.bounds),
                               'distance_plaza_m': shape.distance(plaza)})
        if obj.get('bara_layer') in actual:
            actual[obj['bara_layer']].append(shape)

    axis = LineString([(-50, 0), (50, 0)])
    all_osm_lines = unary_union([LineString([osm['nodes'][r]['xy'] for r in w['refs']])
                               for w in osm['ways'].values() if 'highway' in w['tags']])
    covered_length = axis.intersection(all_osm_lines.buffer(0.5)).length
    objects = bpy.data.objects
    checks = []
    for name in TARGETS:
        obj = objects.get(name)
        if obj is None or obj.type != 'MESH':
            raise RuntimeError(f'Falta el objeto esperado {name}; no se borra nada')
        if [c.name for c in obj.users_collection] != ['Prueba_Baradero']:
            raise RuntimeError(f'Coleccion inesperada para {name}')
        if obj.get('osm_way_id') or obj.get('bara_layer') or obj.get('bara_realista'):
            raise RuntimeError(f'{name} tiene metadatos de geometria real')
        shape = footprint(obj)
        expected = (box(-50, -4, 50, 4) if name == 'PB_Calle_Asfalto' else
                    box(-50, 4, 50, 6) if name == 'PB_Vereda_Norte' else
                    box(-50, -6, 50, -4) if name == 'PB_Vereda_Sur' else None)
        if expected is None:
            x = -47.5 + (int(name[-2:]) - 1) * 5
            expected = box(x - 1.5, -0.075, x + 1.5, 0.075)
        if shape.symmetric_difference(expected).area > 0.001 or obj.modifiers:
            raise RuntimeError(f'Geometria inesperada para {name}')
        checks.append(name)
    if covered_length > 10:
        raise RuntimeError('El tramo coincide demasiado con OSM; requiere confirmacion')

    # Las veredas reales ya estan debajo de la superposicion de prueba.
    logger, _ = common.setup_logging('auditoria_correccion', ROOT / 'mapa/logs')
    expected = streets._layer_geometries(unary_union([w['surface'] for w in ways.values()]), cfg, logger)
    repair_zone = box(-50, -6, 50, 6)
    coverage = {}
    for layer in actual:
        found = unary_union(actual[layer]).intersection(repair_zone)
        wanted = expected[layer].intersection(repair_zone)
        coverage[layer] = {'expected_m2': wanted.area, 'existing_m2': found.area,
                           'difference_m2': found.symmetric_difference(wanted).area}
        if coverage[layer]['difference_m2'] > 0.02:
            raise RuntimeError(f'Hay que reparar {layer} antes de retirar la prueba: {coverage[layer]}')
    terrain = objects.get('TERRENO_BASE')
    if terrain is None or not footprint(terrain).covers(repair_zone):
        raise RuntimeError('El terreno no cubre la zona a restaurar')
    return {'source': str(SOURCE), 'alignment': base['alignment'],
            'nearby_osm_ways': nearby_ways, 'nearby_road_objects': nearby_objects,
            'identified_objects': checks,
            'identification': 'Tramo de prueba de 100 m sobre Y=0 en Prueba_Baradero, sin correspondencia OSM',
            'axis_length_m': axis.length, 'axis_within_0_5m_of_osm_m': covered_length,
            'existing_surface_coverage': coverage,
            'terrain': 'TERRENO_BASE continuo, sin huecos; se recupera al retirar la superposicion',
            'plaza_center': list(plaza.centroid.coords)[0]}


def verify_preserved(bpy, report):
    current = {o.name: o for o in bpy.context.scene.objects}
    changed = [name for name, saved in report['preserved'].items()
               if name not in current or state(current[name]) != saved]
    remaining = [name for name in TARGETS if name in current]
    if changed or remaining:
        raise RuntimeError(f'Objetos alterados: {changed}; prueba restante: {remaining}')
    return {'preserved_objects': len(report['preserved']), 'changed': changed,
            'removed_objects': len(TARGETS), 'remaining_incorrect_objects': remaining}


def setup_top(bpy, center):
    from mathutils import Quaternion
    scene = bpy.context.scene
    name = 'CAMARA_CALLES_CORREGIDAS_SUPERIOR'
    if name in bpy.data.objects:
        raise RuntimeError('Ya existe la camara de correccion')
    data = bpy.data.cameras.new(name)
    enum_set(data, 'type', 'ORTHO')
    data.ortho_scale = 235
    data.clip_end = 3000
    camera = bpy.data.objects.new(name, data)
    scene.collection.objects.link(camera)
    camera.location = (center[0] - 12, center[1] - 5, 250)
    camera.rotation_euler = (0, 0, 0)
    camera['bara_correction'] = 'Vista superior; norte UTM hacia arriba'
    scene.camera = camera
    scene.render.resolution_x = 1100
    scene.render.resolution_y = 1100
    scene.render.resolution_percentage = 100
    for screen in bpy.data.screens:
        for area in screen.areas:
            if area.type != 'VIEW_3D':
                continue
            space = area.spaces.active
            space.region_3d.view_rotation = Quaternion((1, 0, 0, 0))
            space.region_3d.view_location = (center[0] - 12, center[1] - 5, 0)
            space.region_3d.view_distance = 235
            enum_set(space.region_3d, 'view_perspective', 'ORTHO')
            space.region_3d.view_camera_zoom = 0
            space.clip_end = 5000
    return name


def main(mode='inspect'):
    import bpy
    if bpy.app.version[:2] != (4, 2):
        raise RuntimeError('Esta correccion requiere Blender 4.2')
    if mode == 'verify':
        report = json.loads(REPORT.read_text(encoding='utf-8'))
        bpy.ops.wm.open_mainfile(filepath=str(OUTPUT))
        result = verify_preserved(bpy, report)
        cfg = common.load_config(ROOT / 'scripts/mapa_config.json')
        base, _, _ = inspection.inspect(bpy, cfg, ROOT / cfg['osm'])
        result['alignment'] = base['alignment']
        result['source_unchanged'] = digest(SOURCE) == report['source_sha256']
        result['backup_exists'] = Path(report['backup']).is_file()
        scene = bpy.context.scene
        camera = scene.camera
        result['camera_top'] = (camera.name == report['top_camera']
                                and camera.data.type == 'ORTHO'
                                and all(abs(v) < 1e-6 for v in camera.rotation_euler))
        result['realistic_objects_preserved'] = len([
            o for o in scene.objects if o.get('bara_realista')])
        result['opened_with'] = bpy.app.version_string
        assert result['source_unchanged'] and result['backup_exists'] and result['camera_top']
        if '--render' in sys.argv:
            enum_set(scene.render.image_settings, 'file_format', 'PNG')
            if hasattr(scene, 'eevee'):
                scene.eevee.taa_render_samples = 16
            paths = []
            for name, suffix in ((report['top_camera'], 'superior'), ('CAMARA_PLAZA', 'perspectiva')):
                scene.camera = bpy.data.objects[name]
                path = ROOT / f'docs/renders/calles_corregidas_{suffix}.png'
                scene.render.filepath = str(path)
                bpy.ops.render.render(write_still=True)
                assert path.is_file()
                paths.append(str(path))
            result['renders'] = paths
        report['verification'] = result
        write(REPORT, report)
        print(json.dumps(result, ensure_ascii=False))
        return report
    if Path(bpy.data.filepath).resolve() != SOURCE.resolve():
        raise RuntimeError('Abrir Baradero_Realista_v2.blend antes de ejecutar')
    report = audit(bpy)
    if mode == 'inspect':
        write(ROOT / 'docs/inspeccion_diagonal_plaza.json', report)
        print(json.dumps(report, ensure_ascii=False))
        return report
    if mode != 'apply':
        raise ValueError(mode)
    if OUTPUT.exists():
        raise FileExistsError(f'La salida ya existe: {OUTPUT}')
    report['source_sha256'] = digest(SOURCE)
    backup = ROOT / 'backups' / ('Baradero_antes_corregir_calles_' + datetime.now().strftime('%Y%m%d_%H%M%S') + '.blend')
    backup.parent.mkdir(parents=True, exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=str(backup), copy=True)
    assert backup.is_file()
    report['backup'] = str(backup)
    report['preserved'] = {o.name: state(o) for o in bpy.context.scene.objects if o.name not in TARGETS}
    report['removed'] = {name: state(bpy.data.objects[name]) for name in TARGETS}
    for name in TARGETS:
        bpy.data.objects.remove(bpy.data.objects[name], do_unlink=True)
    # No huecos ni cortes: las superficies comprobadas quedan expuestas al quitar
    # las 23 piezas superpuestas. No reconstruir teselas ni modificar intersecciones.
    report['in_memory_verification'] = verify_preserved(bpy, report)
    report['top_camera'] = setup_top(bpy, report['plaza_center'])
    bpy.context.view_layer.update()
    bpy.ops.wm.save_as_mainfile(filepath=str(OUTPUT))
    assert digest(SOURCE) == report['source_sha256']
    report['output'] = str(OUTPUT)
    write(REPORT, report)
    print(json.dumps({k: report[k] for k in ('backup', 'output', 'in_memory_verification', 'top_camera')}, ensure_ascii=False))
    return report


if __name__ == '__main__':
    main('verify' if '--verify' in sys.argv else 'inspect')
