"""Verificacion independiente de la Fase 2, en un proceso Blender aparte.

Comprueba estructura, transformaciones, solidos cerrados, areas, materiales y
que los objetos originales no hayan cambiado. Genera vistas Workbench para
revision visual. No guarda el .blend verificado.
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from collections import Counter
from pathlib import Path

from . import common, inspection


def _resolve(path):
    path = Path(path)
    return path if path.is_absolute() else (common.ROOT / path)


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description="Verificador del mapa BARA-DRIVE")
    parser.add_argument("--config", default="scripts/mapa_config.json")
    parser.add_argument("--file", default="mapa/blender/Baradero_mapa_3d.blend")
    parser.add_argument("--report", default="docs/informe_calles.json")
    parser.add_argument("--diagnostic", default="docs/diagnostico_mapa.json")
    parser.add_argument("--out", default="docs/verificacion_calles.json")
    parser.add_argument("--renders", default="docs/renders")
    parser.add_argument("--no-render", action="store_true")
    argv = argv if argv is not None else sys.argv
    argv = argv[argv.index("--") + 1:] if "--" in argv else []
    return parser.parse_args(argv)


class Checks:
    def __init__(self):
        self.items = []

    def add(self, name, passed, detail=""):
        self.items.append({"name": name, "passed": bool(passed), "detail": detail})
        return passed

    @property
    def failed(self):
        return [item for item in self.items if not item["passed"]]


def _is_identity(obj, tolerance=1e-6):
    for row in range(4):
        for column in range(4):
            expected = 1.0 if row == column else 0.0
            if abs(obj.matrix_world[row][column] - expected) > tolerance:
                return False
    return True


def _top_area(obj, z_top, tolerance=1e-4):
    mesh = obj.data
    total = 0.0
    for polygon in mesh.polygons:
        if all(abs(mesh.vertices[index].co.z - z_top) <= tolerance
               for index in polygon.vertices):
            total += polygon.area
    return total


def _manifold(obj):
    import bmesh
    mesh = obj.data
    bm = bmesh.new()
    try:
        bm.from_mesh(mesh)
        boundary = sum(1 for edge in bm.edges if len(edge.link_faces) == 1)
        non_manifold = sum(1 for edge in bm.edges if len(edge.link_faces) != 2)
        return boundary, non_manifold, len(bm.edges)
    finally:
        bm.free()


def _z_range(obj):
    if not obj.data.vertices:
        return None, None
    values = [vertex.co.z for vertex in obj.data.vertices]
    return min(values), max(values)


def verify(args, logger):
    import bpy

    checks = Checks()
    target = _resolve(args.file)
    report_path = _resolve(args.report)
    diagnostic_path = _resolve(args.diagnostic)
    if not target.is_file():
        raise FileNotFoundError(f"No existe el archivo a verificar: {target}")
    if not report_path.is_file():
        raise FileNotFoundError(f"Falta el informe de generacion: {report_path}")
    report = json.loads(report_path.read_text(encoding="utf-8"))
    config = common.load_config(_resolve(args.config))

    logger.info("Abriendo %s", target)
    bpy.ops.wm.open_mainfile(filepath=str(target))
    scene = bpy.context.scene
    root = bpy.data.collections.get(config["root_collection"])
    checks.add("coleccion_raiz", root is not None, config["root_collection"])
    if root is None:
        raise RuntimeError("No existe la coleccion raiz esperada")

    folder_names = {child.name for child in root.children}
    for folder in ("CALLES", "CORDONES", "VEREDAS"):
        checks.add(f"coleccion_{folder.lower()}", folder in folder_names, folder)

    generated = list(common.generated_objects(root))
    generated_ids = {obj.name for obj in generated}
    checks.add("objetos_generados", len(generated) > 0, f"{len(generated)} objetos")

    source = bpy.data.collections.get(config["source_collection"])
    checks.add("coleccion_fuente", source is not None, config["source_collection"])
    source_names = {obj.name for obj in source.objects} if source else set()
    checks.add("fuente_separada", not (generated_ids & source_names),
               "ningun objeto generado dentro de la coleccion fuente")

    by_layer = Counter(obj.get("bara_layer") for obj in generated)
    for layer, expected in report["layers"].items():
        checks.add(f"cantidad_{layer.lower()}", by_layer.get(layer, 0) == expected["objects"],
                   f"esperados {expected['objects']}, encontrados {by_layer.get(layer, 0)}")

    bad_transform = [obj.name for obj in generated if not _is_identity(obj)]
    checks.add("transformaciones_identidad", not bad_transform, str(bad_transform[:5]))

    bad_mesh = []
    bad_material = []
    bad_metadata = []
    bad_z = []
    boundary_total = 0
    non_manifold_total = 0
    edge_total = 0
    area_by_layer = Counter()
    for obj in generated:
        if obj.type != "MESH" or not obj.data.polygons:
            bad_mesh.append(obj.name)
            continue
        if not obj.data.materials or obj.data.materials[0] is None:
            bad_material.append(obj.name)
        if not obj.get("bara_generated") or obj.get("bara_crs") != "EPSG:32721":
            bad_metadata.append(obj.name)
        layer = obj.get("bara_layer")
        z_bottom, z_top = _z_range(obj)
        expected = report["layers"].get(layer)
        if (expected is None or z_bottom is None
                or abs(z_bottom - expected["z_bottom_m"]) > 1e-3
                or abs(z_top - expected["z_top_m"]) > 1e-3):
            bad_z.append(obj.name)
        else:
            area_by_layer[layer] += _top_area(obj, z_top)
        boundary, non_manifold, edges = _manifold(obj)
        boundary_total += boundary
        non_manifold_total += non_manifold
        edge_total += edges
    checks.add("mallas_con_caras", not bad_mesh, str(bad_mesh[:5]))
    checks.add("materiales_asignados", not bad_material, str(bad_material[:5]))
    checks.add("metadatos", not bad_metadata, str(bad_metadata[:5]))
    checks.add("cotas_esperadas", not bad_z, str(bad_z[:5]))
    checks.add("sin_bordes_abiertos", boundary_total == 0,
               f"{boundary_total} bordes con una sola cara de {edge_total}")
    checks.add("solidos_cerrados", non_manifold_total == 0,
               f"{non_manifold_total} aristas no manifold")

    for layer, expected in report["layers"].items():
        found = area_by_layer.get(layer, 0.0)
        target_area = float(expected["area_m2"])
        relative = abs(found - target_area) / max(target_area, 1e-9)
        checks.add(f"area_{layer.lower()}", relative <= 0.005,
                   f"informe {target_area:.1f} m2, malla {found:.1f} m2, "
                   f"diferencia {relative * 100:.3f}%")

    if diagnostic_path.is_file():
        diagnostic = json.loads(diagnostic_path.read_text(encoding="utf-8"))
        current = {obj.name: obj for obj in scene.objects}
        changed = []
        missing = []
        for entry in diagnostic["objects"]:
            if not entry.get("osm_way_id"):
                continue
            obj = current.get(entry["name"])
            if obj is None:
                missing.append(entry["name"])
            elif inspection.mesh_signature(obj) != entry["signature"]:
                changed.append(entry["name"])
        checks.add("originales_intactos", not changed and not missing,
                   f"modificados {changed[:5]}, faltantes {missing[:5]}")
        checks.add("calles_originales", len(diagnostic.get("objects", [])) >= 28,
                   f"{len(diagnostic.get('objects', []))} objetos en el diagnostico")
    else:
        checks.add("originales_intactos", False, f"falta {diagnostic_path}")

    if not args.no_render:
        renders = render_views(bpy, _resolve(args.renders), logger, config)
        checks.add("vistas_generadas", all(Path(path).is_file() for path in renders),
                   ", ".join(renders))
    else:
        renders = []

    payload = {
        "verified_file": str(target),
        "blender_version": bpy.app.version_string,
        "scene": scene.name,
        "unit_system": scene.unit_settings.system,
        "scale_length": scene.unit_settings.scale_length,
        "generated_objects": len(generated),
        "objects_by_layer": dict(by_layer),
        "areas_by_layer_m2": {key: round(value, 3) for key, value in area_by_layer.items()},
        "source_objects": len(source_names),
        "renders": renders,
        "checks": checks.items,
        "passed": not checks.failed,
    }
    write_json(_resolve(args.out), payload)
    for item in checks.items:
        logger.info("%s %s%s", "OK  " if item["passed"] else "FALLA",
                    item["name"], f" ({item['detail']})" if item["detail"] else "")
    if checks.failed:
        raise RuntimeError(f"{len(checks.failed)} verificaciones fallaron")
    logger.info("Verificacion completa: %d controles aprobados", len(checks.items))
    return payload


def write_json(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _junction_centre(config, center):
    """Nodo OSM compartido por mas vias, cerca del centro de la red."""
    try:
        import bpy
        osm = inspection.load_osm(_resolve(config["osm"]))
        source = bpy.data.collections.get(config["source_collection"])
        origin_east = float(source["origin_easting_m"])
        origin_north = float(source["origin_northing_m"])
        uses = Counter(
            ref for way in osm["ways"].values()
            if "highway" in way["tags"]
            for ref in way["refs"])
        shared = [ref for ref, count in uses.items() if count >= 2]
        if not shared:
            return None
        points = []
        for ref in shared:
            east, north = inspection.utm21s(
                osm["nodes"][ref]["lon"], osm["nodes"][ref]["lat"])
            points.append((east - origin_east, north - origin_north))
        return min(points, key=lambda point: (point[0] - center.x) ** 2
                   + (point[1] - center.y) ** 2)
    except Exception:
        return None


def render_views(bpy, folder, logger, config=None):
    from mathutils import Vector

    folder.mkdir(parents=True, exist_ok=True)
    scene = bpy.context.scene
    root = bpy.data.collections.get(scene.get("bara_root", "BARA_MAPA_3D"))
    meshes = [obj for obj in common.generated_objects(root) if obj.type == "MESH"]
    if not meshes:
        raise RuntimeError("No hay geometria generada para encuadrar")
    points = []
    for obj in meshes:
        points.extend(obj.matrix_world @ Vector(corner) for corner in obj.bound_box)
    min_x = min(p.x for p in points)
    max_x = max(p.x for p in points)
    min_y = min(p.y for p in points)
    max_y = max(p.y for p in points)
    center = Vector(((min_x + max_x) / 2, (min_y + max_y) / 2, 0.0))
    span_x, span_y = max_x - min_x, max_y - min_y
    largest = max(span_x, span_y, 1.0)

    for candidate in ("BLENDER_WORKBENCH", "BLENDER_EEVEE_NEXT", "BLENDER_EEVEE", "CYCLES"):
        try:
            scene.render.engine = candidate
            break
        except TypeError:
            continue
    scene.render.resolution_x = 1400
    scene.render.resolution_y = 1200
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"
    scene.render.film_transparent = False
    scene.render.use_file_extension = True
    shading = scene.display.shading
    for attribute, value in (("light", "STUDIO"), ("color_type", "MATERIAL"),
                             ("background_type", "VIEWPORT"),
                             ("background_color", (0.66, 0.71, 0.76)),
                             ("show_cavity", True), ("show_shadows", True)):
        try:
            setattr(shading, attribute, value)
        except (AttributeError, TypeError):
            pass

    camera_data = bpy.data.cameras.new("TMP_Camara_Verificacion")
    camera = bpy.data.objects.new("TMP_Camara_Verificacion", camera_data)
    scene.collection.objects.link(camera)
    scene.camera = camera
    camera_data.clip_start = 0.1
    camera_data.clip_end = largest * 20.0
    paths = []

    camera_data.type = "ORTHO"
    camera_data.ortho_scale = largest * 1.08
    camera.location = center + Vector((0, 0, largest * 2.0))
    camera.rotation_euler = (0.0, 0.0, 0.0)
    top_path = folder / "calles_superior.png"
    scene.render.filepath = str(top_path)
    bpy.ops.render.render(write_still=True)
    paths.append(str(top_path))
    logger.info("Vista superior: %s", top_path)

    camera_data.type = "PERSP"
    camera_data.lens = 42.0
    camera.location = center + Vector((span_x * 0.55, -span_y * 0.85, largest * 0.85))
    direction = center - camera.location
    camera.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()
    oblique_path = folder / "calles_oblicua.png"
    scene.render.filepath = str(oblique_path)
    bpy.ops.render.render(write_still=True)
    paths.append(str(oblique_path))
    logger.info("Vista oblicua: %s", oblique_path)

    # Acercamientos: a escala de ciudad las veredas miden pocos pixeles.
    camera_data.type = "ORTHO"
    camera_data.ortho_scale = 240.0
    camera.location = center + Vector((0, 0, largest * 2.0))
    camera.rotation_euler = (0.0, 0.0, 0.0)
    detail_top = folder / "calles_detalle_superior.png"
    scene.render.filepath = str(detail_top)
    bpy.ops.render.render(write_still=True)
    paths.append(str(detail_top))
    logger.info("Detalle superior: %s", detail_top)

    camera_data.type = "PERSP"
    camera.location = center + Vector((90.0, -130.0, 120.0))
    direction = center - camera.location
    camera.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()
    detail_oblique = folder / "calles_detalle_oblicua.png"
    scene.render.filepath = str(detail_oblique)
    bpy.ops.render.render(write_still=True)
    paths.append(str(detail_oblique))
    logger.info("Detalle oblicuo: %s", detail_oblique)

    junction = _junction_centre(config, center) if config else None
    if junction:
        target = Vector((junction[0], junction[1], 0.0))
        camera_data.type = "ORTHO"
        camera_data.ortho_scale = 85.0
        camera.location = target + Vector((0, 0, largest * 2.0))
        camera.rotation_euler = (0.0, 0.0, 0.0)
        corner_top = folder / "calles_esquina_superior.png"
        scene.render.filepath = str(corner_top)
        bpy.ops.render.render(write_still=True)
        paths.append(str(corner_top))
        logger.info("Esquina superior (%s): %s", junction, corner_top)

        camera_data.type = "PERSP"
        camera_data.lens = 35.0
        camera.location = target + Vector((26.0, -38.0, 30.0))
        direction = target - camera.location
        camera.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()
        corner_oblique = folder / "calles_esquina_oblicua.png"
        scene.render.filepath = str(corner_oblique)
        bpy.ops.render.render(write_still=True)
        paths.append(str(corner_oblique))
        logger.info("Esquina oblicua: %s", corner_oblique)

    bpy.data.objects.remove(camera, do_unlink=True)
    bpy.data.cameras.remove(camera_data)
    return paths


def run(argv=None):
    logger = None
    try:
        args = parse_args(argv)
        logger, log_path = common.setup_logging("verificacion", common.ROOT / "mapa" / "logs")
        logger.info("Argumentos: %s", vars(args))
        verify(args, logger)
        logger.info("Log: %s", log_path)
        return 0
    except Exception:
        import traceback
        trace = traceback.format_exc()
        print(trace, file=sys.stderr)
        try:
            from datetime import datetime
            stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            path = common.ROOT / "mapa" / "logs" / f"error_verificacion_{stamp}.log"
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(trace, encoding="utf-8")
        except Exception:
            pass
        return 1
