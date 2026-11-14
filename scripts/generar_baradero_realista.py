"""Entrada para Blender 4.2: Plaza Mitre + Municipalidad de Baradero.

Lee la escena existente (calles, veredas, edificios provisionales) y agrega una
reconstruccion APROXIMADA de Plaza Mitre y de la Municipalidad (Av. San Martin
905), tomando formas y colores de las fotografias locales.

Uso (Windows, consola):
  "C:\\Program Files\\Blender Foundation\\Blender 4.2\\blender.exe" ^
    --background --factory-startup --python scripts\\generar_baradero_realista.py -- ^
    --source mapa/blender/Baradero_3D.blend ^
    --output mapa/blender/Baradero_Realista_v2.blend

No se borra ni se sobrescribe ningun archivo original.
"""
from __future__ import annotations

import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from mapa_baradero import common  # noqa: E402

common.add_dependency_path()

from mapa_baradero.runner import run_realista_entry  # noqa: E402

if __name__ == "__main__":
    sys.exit(run_realista_entry("generar_baradero_realista"))
