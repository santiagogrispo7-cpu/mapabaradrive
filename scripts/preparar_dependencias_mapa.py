"""Ejecutar con Blender --background --python este_archivo.py.

Instala una rueda binaria aislada por versión Python. No modifica el Python global
ni el proyecto .blend. Requiere Internet solo durante esta preparación.
"""
import importlib.util
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
target = ROOT / "mapa" / ".deps" / f"py{sys.version_info.major}{sys.version_info.minor}"
target.mkdir(parents=True, exist_ok=True)
python = Path(sys.prefix) / "bin" / "python.exe"
if not python.is_file():
    raise RuntimeError(f"No se encontró el Python de Blender: {python}")
subprocess.run([str(python), "-m", "ensurepip"], check=True)
subprocess.run([str(python), "-m", "pip", "install", "--target", str(target),
                "--only-binary=:all:", "--no-deps", "shapely==2.1.2"], check=True)
sys.path.insert(0, str(target))
import shapely
import numpy
if not hasattr(shapely, "constrained_delaunay_triangles"):
    raise RuntimeError("Falta triangulación restringida; revisar la versión de Shapely")
print(f"Dependencia lista: Shapely {shapely.__version__}, GEOS {shapely.geos_version_string}, NumPy {numpy.__version__}, ruta {target}")
