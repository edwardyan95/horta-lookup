"""Read-only access to a versioned atlas/transform bundle."""
import hashlib
import json
from pathlib import Path

class DataBundle:
    def __init__(self, root, verify_hashes=False):
        self.root = Path(root).expanduser().resolve()
        try:
            self.manifest = json.loads((self.root / 'manifest.json').read_text(encoding='utf-8'))
        except (OSError, ValueError) as e:
            raise ValueError(f'Cannot read manifest.json in {self.root}. Connect the shared drive or choose the data folder again.') from e
        m = self.manifest
        if m.get('schema_version') != 1:
            raise ValueError('Unsupported data bundle version. Update Horta Lookup.')
        self.bundle_id = m['bundle_id']
        self.records = {entry['path']: entry for entry in m['files']}
        self.verify(verify_hashes)
        self.atlas = m['atlas']
        # This application implements the 25 um CCFv3 annotation convention.
        if self.atlas['spacing_um'] != 25 or self.atlas['mrn_ids'] != [128, 539, 548, 555]:
            raise ValueError('Unsupported atlas spacing or MRN definition.')
        self.datasets = {name: json.loads(self.path(path).read_text(encoding='utf-8'))
                         for name, path in m['datasets'].items()}
        self.default_dataset = m['default_dataset']
        if self.default_dataset not in self.datasets:
            raise ValueError('The default dataset is missing from the bundle.')
        for key in ('annotation', 'structures', 'meshes', 'mrn_centers'):
            self.path(self.atlas[key])
        for ds in self.datasets.values():
            if ds['default_mode'] not in ds['modes'] or not set(ds['modes']) <= {'affine', 'nonlinear'}:
                raise ValueError('Invalid transform modes in dataset profile.')
            if 'nonlinear' in ds['modes']:
                self.path(ds['warp'])

    def path(self, relative):
        p = (self.root / relative).resolve()
        if not p.is_relative_to(self.root) or Path(relative).is_absolute():
            raise ValueError('A data path points outside the selected bundle.')
        if relative not in self.records:
            raise ValueError(f'File is not listed in the bundle manifest: {relative}')
        if not p.is_file():
            raise ValueError(f'Missing data file: {relative}. Check the shared drive.')
        return p

    def verify(self, hashes=False):
        for relative, record in self.records.items():
            p = self.path(relative)
            if p.stat().st_size != record['bytes']:
                raise ValueError(f'Incomplete or changed data file: {relative}. Copy it again.')
            if hashes:
                digest = hashlib.sha256()
                with p.open('rb') as f:
                    for block in iter(lambda: f.read(8 * 1024 * 1024), b''):
                        digest.update(block)
                if digest.hexdigest() != record['sha256']:
                    raise ValueError(f'Checksum mismatch: {relative}. Copy it again.')
