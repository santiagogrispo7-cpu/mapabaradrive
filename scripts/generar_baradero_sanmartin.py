"""Entrada para Blender 4.2: cuadra de Av. San Martin reconstruida desde fotos.

Uso (Windows, consola):
  "C:\\Program Files\\Blender Foundation\\Blender 4.2\\blender.exe" ^
    --background --factory-startup --python scripts\\generar_baradero_sanmartin.py -- ^
    --source mapa/blender/Baradero_Calles_Corregidas.blend ^
    --output mapa/blender/Baradero_SanMartin_Realista.blend

La base (calles corregidas, Plaza Mitre, Delegacion) no se modifica: todo lo
nuevo vive en BARA_SANMARTIN_REALISTA. Los archivos de entrada no se sobrescriben.
"""
from __future__ import annotations

import argparse
import json
import sys
import traceback
from datetime import datetime
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from mapa_baradero import common  # noqa: E402

common.add_dependency_path()

from mapa_baradero import inspection, sanmartin  # noqa: E402


def _resolve(path):
    path = Path(path)
    return path if path.is_absolute() else (common.ROOT / path)


def parse_args(argv):
    parser = argparse.ArgumentParser(description="Generador de la cuadra Av. San Martin")
    parser.add_argument("--config", default="scripts/mapa_config.json")
    parser.add_argument("--source", default="mapa/blender/Baradero_Calles_Corregidas.blend")
    parser.add_argument("--output", default="mapa/blender/Baradero_SanMartin_Realista.blend")
    parser.add_argument("--report", default="docs/informe_sanmartin_realista.json")
    parser.add_argument("--skip-backup", action="store_true")
    argv = argv if argv is not None else sys.argv
    argv = argv[argv.index("--") + 1:] if "--" in argv else []
    return parser.parse_args(argv)


def main(argv=None):
    logger = None
    try:
        args = parse_args(argv)
        logger, log_path = common.setup_logging("generar_sanmartin", common.ROOT / "mapa" / "logs")
        logger.info("Argumentos: %s", vars(args))
        import bpy

        source = _resolve(args.source)
        output = _resolve(args.output)
        if not source.is_file():
            raise FileNotFoundError(f"No existe el .blend de origen: {source}")
        if source.resolve() == output.resolve():
            raise ValueError("La salida no puede ser el mismo archivo que la entrada")
        config = common.load_config(_resolve(args.config))
        osm_path = _resolve(config["osm"])

        logger.info("Abriendo %s", source)
        bpy.ops.wm.open_mainfile(filepath=str(source))
        base_report, osm, matched = inspection.inspect(bpy, config, osm_path)
        logger.info("Base verificada: %d vias, error maximo %.6f m",
                    len(matched), base_report["alignment"]["max_error_m"])
        for name in ("PLAZA_MONUMENTO_CONDOR", "DELEGACION_MUNICIPAL"):
            if bpy.data.objects.get(name) is None:
                raise RuntimeError(f"Falta {name}: la base no es la copia corregida")

        if not args.skip_backup:
            backup = common.ROOT / "backups" / ("Baradero_antes_sanmartin_"
                                               + datetime.now().strftime("%Y%m%d_%H%M%S") + ".blend")
            backup.parent.mkdir(parents=True, exist_ok=True)
            bpy.ops.wm.save_as_mainfile(filepath=str(backup), copy=True)
            logger.info("Respaldo: %s", backup)

        report = sanmartin.make_layout()
        report["output_blend"] = str(output)
        report["source_blend"] = str(source)
        report["generated_at"] = datetime.now().isoformat(timespec="seconds")
        report["osm_alignment"] = {"matched_ways": len(matched),
                                   "max_error_m": base_report["alignment"]["max_error_m"]}
        report["source_photos"] = [
            "referencias/avenida-sanmartin/esquinasemaforo.png",
            "referencias/avenida-sanmartin/esquinasemaforo2.png",
            "referencias/avenida-sanmartin/av.sanmartin.png",
            "referencias/avenida-sanmartin/av.sanmartin1.png",
            "referencias/avenida-sanmartin/avsanmartin2.png",
            "referencias/avenida-sanmartin/avsanmartin3.png",
            "referencias/avenida-sanmartin/patiodecomidas1.png",
        ]
        report["licenses"] = {
            "skills": ["arjun988/blender-skills (MIT)",
                       "Oldcircle/geo-sleuth (MIT)"],
            "assets": "Poly Haven CC0-1.0 (arboles, palmera, asfalto, vereda, cesped, revoque)",
        }
        report["limitations"] = [
            "Modelo aproximado: las fotos no tienen escala ni planta cadastral.",
            "Las alturas de las fachadas se estiman visualmente desde las seis capturas.",
            "La cuadra se ancla al cruce OSM San Martin/Malabia (way 228161668, nodo 2367942995).",
            "Los limites de parcela se aproximan a partir de la foto aerea de referencia.",
            "No se modelaron vehiculos, personas ni cableado de media tension real.",
            "No se reconstruyo la iglesia ni el resto de Plaza Mitre en esta etapa.",
        ]
        output.parent.mkdir(parents=True, exist_ok=True)
        bpy.ops.wm.save_as_mainfile(filepath=str(output))
        logger.info("Guardado: %s", output)
        report_path = _resolve(args.report)
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n",
                                encoding="utf-8")
        logger.info("San Martin completa: %d objetos, %d triangulos",
                    len(bpy.data.collections["BARA_SANMARTIN_REALISTA"].objects),
                    report["triangulos"])
        return 0
    except SystemExit:
        raise
    except Exception:
        trace = traceback.format_exc()
        try:
            stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            error_path = common.ROOT / "mapa" / "logs" / f"error_sanmartin_{stamp}.log"
            error_path.parent.mkdir(parents=True, exist_ok=True)
            error_path.write_text(trace, encoding="utf-8")
        except Exception:
            pass
        print(trace, file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
