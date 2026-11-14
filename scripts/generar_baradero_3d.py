"""Entrada para Blender 4.2: calles 3D + zona urbana de prueba.

Uso (Windows, consola):
  "C:\\Program Files\\Blender Foundation\\Blender 4.2\\blender.exe" ^
    --background --factory-startup --python scripts\\generar_baradero_3d.py -- ^
    --source mapa/blender/Baradero_mapa.blend ^
    --output mapa/blender/Baradero_3D.blend

Los edificios generados son PROVISIONALES y no representan construcciones
reales de Baradero.
"""
from __future__ import annotations

import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from mapa_baradero import common  # noqa: E402

common.add_dependency_path()

from mapa_baradero.runner import run_urban_entry  # noqa: E402

if __name__ == "__main__":
    sys.exit(run_urban_entry("generar_baradero_3d"))
