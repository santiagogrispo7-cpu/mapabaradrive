"""Utilidades compartidas por las fases del mapa. Solo APIs presentes en 4.2 y 5.2."""
from __future__ import annotations

import json
import logging
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def load_config(path):
    """Lee la configuración y exige las claves que afectan a la geometría."""
    cfg = json.loads(Path(path).read_text(encoding="utf-8"))
    required = (
        "osm", "source_collection", "root_collection", "tile_size_m", "road_thickness_m",
        "road_top_z_m", "road_bottom_z_m", "sidewalk_top_z_m", "curb_top_z_m",
        "sidewalk_width_m_estimated", "curb_width_m_estimated", "curb_height_m_estimated",
        "curb_overlap_m", "buffer_resolution",
        "lane_width_m_estimated", "road_edge_allowance_m_estimated", "widths_m_estimated",
        "building_floor_height_m_estimated", "building_default_height_m_estimated",
        "alignment_tolerance_m", "min_polygon_area_m2",
    )
    missing = [key for key in required if key not in cfg]
    if missing:
        raise ValueError(f"Faltan claves en la configuración: {missing}")
    if not 1.0 <= float(cfg["tile_size_m"]) <= 2048.0:
        raise ValueError("tile_size_m debe estar entre 1 y 2048")
    if not 0.0 <= float(cfg["curb_width_m_estimated"]) < float(cfg["sidewalk_width_m_estimated"]):
        raise ValueError("Ancho de cordón/vereda incoherente")
    return cfg


def setup_logging(name, log_dir):
    log_dir = Path(log_dir)
    log_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = log_dir / f"{stamp}_{name}.log"
    logger = logging.getLogger(f"bara.{name}")
    logger.setLevel(logging.INFO)
    logger.propagate = False
    for handler in list(logger.handlers):
        logger.removeHandler(handler)
        handler.close()
    formatter = logging.Formatter("%(asctime)s %(levelname)s %(message)s")
    for handler in (logging.FileHandler(path, encoding="utf-8"), logging.StreamHandler(sys.stdout)):
        handler.setFormatter(formatter)
        logger.addHandler(handler)
    return logger, path


def add_dependency_path():
    """Añade la carpeta aislada de ruedas binarias de esta versión de Python."""
    target = ROOT / "mapa" / ".deps" / f"py{sys.version_info.major}{sys.version_info.minor}"
    if target.is_dir() and str(target) not in sys.path:
        sys.path.insert(0, str(target))
    return target


def make_material(bpy, name, color, roughness=0.8, metallic=0.0,
                  emission=None, emission_strength=0.0):
    """Material PBR simple, sin nodos procedurales (apto para glTF)."""
    rgba = tuple(color) + (1.0,) if len(color) == 3 else tuple(color)
    material = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    material.use_nodes = True
    shader = next((node for node in material.node_tree.nodes
                   if node.type == "BSDF_PRINCIPLED"), None)
    if shader is None:
        raise RuntimeError(f"El material {name} no tiene shader Principled")
    shader.inputs["Base Color"].default_value = rgba
    shader.inputs["Roughness"].default_value = roughness
    shader.inputs["Metallic"].default_value = metallic
    if emission is not None:
        emission_rgba = tuple(emission) + (1.0,) if len(emission) == 3 else tuple(emission)
        emission_socket = shader.inputs.get("Emission Color") or shader.inputs.get("Emission")
        if emission_socket is not None:
            emission_socket.default_value = emission_rgba
        strength_socket = shader.inputs.get("Emission Strength")
        if strength_socket is not None:
            strength_socket.default_value = emission_strength
    material.diffuse_color = rgba
    material.roughness = roughness
    material.metallic = metallic
    return material


def materials(bpy):
    """Materiales PBR simples, aptos para glTF (sin nodos procedurales)."""
    specs = {
        "BARA_Asfalto": ((0.030, 0.034, 0.036), 0.93),
        "BARA_Hormigon": ((0.360, 0.345, 0.312), 0.87),
        "BARA_Cordon": ((0.255, 0.250, 0.235), 0.90),
    }
    return {name: make_material(bpy, name, color, roughness)
            for name, (color, roughness) in specs.items()}


def ensure_collection(bpy, name, parent):
    collection = bpy.data.collections.get(name)
    if collection is None:
        collection = bpy.data.collections.new(name)
        parent.children.link(collection)
        return collection
    if collection.name not in {child.name for child in parent.children}:
        raise RuntimeError(
            f"Ya existe una coleccion llamada {name!r} fuera de {parent.name!r}. "
            "El pipeline no la adoptara para no mezclar trabajo manual; renombrarla.")
    return collection


def walk(collection):
    yield collection
    for child in collection.children_recursive:
        yield child


def generated_objects(root):
    for collection in walk(root):
        yield from collection.objects


def clear_generated(bpy, root_name):
    """Elimina solo la jerarquía propia. Nunca toca la fuente ni objetos ajenos."""
    root = bpy.data.collections.get(root_name)
    if root is None:
        return 0
    foreign = [obj.name for obj in generated_objects(root) if not obj.get("bara_generated")]
    if foreign:
        raise RuntimeError(
            f"{root_name} contiene objetos no generados por el pipeline: {foreign[:5]}. "
            "Se detiene para no borrar trabajo manual.")
    removed = 0
    for collection in list(walk(root)):
        for obj in list(collection.objects):
            data = obj.data
            bpy.data.objects.remove(obj, do_unlink=True)
            if getattr(data, "users", 1) == 0 and getattr(data, "rna_type", None) is not None:
                if data.rna_type.identifier == "Mesh":
                    bpy.data.meshes.remove(data)
            removed += 1
    for collection in sorted(walk(root), key=lambda c: len(c.children), reverse=True):
        for parent in list(collection.users_collection):
            parent.children.unlink(collection)
        if collection.users == 0:
            bpy.data.collections.remove(collection)
    return removed
