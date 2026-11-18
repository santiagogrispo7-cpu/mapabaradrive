"""Recursos CC0 de Poly Haven; sin instalar paquetes Python ni addons."""
import concurrent.futures
import hashlib
import json
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'mapa/recursos/sanmartin'
MODELS = ['island_tree_02', 'jacaranda_tree']
TEXTURES = ['asphalt_02', 'concrete_pavement', 'grey_plaster', 'grass_ground', 'palm_bark']


def request(url):
    return urllib.request.urlopen(urllib.request.Request(
        url, headers={'User-Agent': 'BARA-DRIVE-local-artwork/1.0'}), timeout=180)


def download(item):
    path, spec = item
    if path.exists() and hashlib.md5(path.read_bytes()).hexdigest().lstrip('0') == spec['md5'].lstrip('0'):
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    with request(spec['url']) as response, path.with_suffix(path.suffix+'.part').open('wb') as target:
        while chunk := response.read(1024*1024):
            target.write(chunk)
    temporary = path.with_suffix(path.suffix+'.part')
    if hashlib.md5(temporary.read_bytes()).hexdigest().lstrip('0') != spec['md5'].lstrip('0'):
        raise RuntimeError(f'Checksum incorrecto: {path}')
    temporary.replace(path)
    print('Downloaded', path.name, flush=True)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    tasks, manifest = [], []
    for asset in MODELS + TEXTURES:
        with request('https://api.polyhaven.com/files/'+asset) as response:
            files = json.load(response)
        (OUT/(asset+'_files.json')).write_text(json.dumps(files, indent=2), encoding='utf-8')
        record = {'id': asset, 'source': 'https://polyhaven.com/a/'+asset,
                  'license': 'CC0-1.0', 'license_url': 'https://polyhaven.com/license', 'files': []}
        if asset in MODELS:
            entry = files['gltf']['1k']['gltf']
            pairs = [(asset+'_1k.gltf', entry), *entry['include'].items()]
            # Alpha separada disponible para revisar hojas al importar.
            if 'leaves_alpha' in files:
                pairs.append(('textures/'+asset+'_leaves_alpha_1k.png', files['leaves_alpha']['1k']['png']))
        else:
            pairs = [(asset+'_'+channel+'_1k.jpg', files[key]['1k']['jpg'])
                     for channel, key in [('diff', 'Diffuse'), ('nor_gl', 'nor_gl'), ('rough', 'Rough')]]
        for relative, spec in pairs:
            target = OUT/asset/relative
            tasks.append((target, spec))
            record['files'].append({'path': str(target.relative_to(ROOT)), 'url': spec['url'], 'md5': spec['md5']})
        manifest.append(record)
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        list(pool.map(download, tasks))
    (OUT/'licenses.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')
    print('READY',len(tasks),'verified files',flush=True)


if __name__ == '__main__':
    main()
