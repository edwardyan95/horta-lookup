"""Small synthetic fixtures; no lab data or private coordinates are required."""
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
import numpy as np
from atlas_engine import AtlasEngine
from data_bundle import DataBundle

class EngineTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        annotation = np.zeros((6, 7, 8), dtype=np.uint32)
        annotation[2, 3, 4] = 128
        np.save(self.root / 'annotation.npy', annotation)
        np.save(self.root / 'centers.npy', np.array([[50., 75., 100.]]))
        field = np.indices(annotation.shape, dtype=np.float32).transpose(1, 2, 3, 0).copy()
        field *= np.array([.1, .2, -.25], dtype=np.float32)
        np.save(self.root / 'warp.npy', field)
        self.write('structures.json', {'msg':[{'id':128,'name':'Midbrain reticular nucleus','acronym':'MRN',
                    'color_hex_triplet':'FFCC00','children':[]}]})
        self.write('meshes.json', {})
        profile = dict(label='Synthetic', default_mode='nonlinear', modes=['affine','nonlinear'],
            registration='Synthetic unit test', resolution_um=25, original_shape_xyz=[200,200,200],
            resample=[1,1,1], native_voxel_um=[1,1,1], pyramid_factor=25, flip_axes={},
            affine=dict(matrix=np.eye(3).tolist(),translation=[0,0,0],center=[0,0,0]),
            note='Synthetic fixture',examples=[],warp='warp.npy',warp_shape=[6,7,8,3])
        self.write('profile.json', profile)
        profile = dict(profile, modes=['affine'], default_mode='affine', flip_axes={'0':10},
            affine=dict(matrix=np.diag([2,3,4]).tolist(),translation=[1,2,3],center=[1,1,1]))
        self.write('affine.json', profile)
        self.manifest = dict(schema_version=1, bundle_id='synthetic-test', default_dataset='synthetic',
            datasets={'synthetic':'profile.json', 'flipped':'affine.json'},
            atlas=dict(annotation='annotation.npy', structures='structures.json', meshes='meshes.json',
                mrn_centers='centers.npy',shape=[6,7,8],spacing_um=25,mrn_ids=[128,539,548,555],midline_ml_um=100))
        self.refresh_manifest()
        self.engine = AtlasEngine(self.root)

    def write(self, name, value):
        (self.root / name).write_text(json.dumps(value), encoding='utf-8')

    def refresh_manifest(self):
        self.manifest['files'] = [{'path':p.name,'bytes':p.stat().st_size,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()}
            for p in self.root.iterdir() if p.name != 'manifest.json']
        self.write('manifest.json', self.manifest)

    def tearDown(self):
        self.engine.fields.clear()
        self.temp.cleanup()

    def test_affine_inverse_center_translation_and_flip(self):
        actual, _ = self.engine.convert('flipped', [200,275,375], 'affine')
        np.testing.assert_allclose(actual, [25,275/3,93.75], atol=1e-12)
        self.assertEqual(self.engine.fields, {})

    def test_trilinear_vector_field(self):
        actual, affine = self.engine.convert('synthetic', [56.25,87.5,106.25], 'nonlinear')
        np.testing.assert_allclose(actual, [61.875,105,79.6875], atol=1e-6)
        np.testing.assert_array_equal(affine, [56.25,87.5,106.25])

    def test_membership_distances_and_slices(self):
        result = self.engine.check('synthetic', [50,75,100], 'affine')
        self.assertTrue(result['inside_mrn'])
        self.assertEqual(result['boundary_distance_um'], 12.5)
        self.assertEqual(len(result['slices']), 3)
        distance, nearest = self.engine.boundary_distance(np.array([75,75,100]), False)
        self.assertEqual(distance, 12.5)
        np.testing.assert_array_equal(nearest, [62.5,75,100])
        self.assertIsNone(self.engine.label(np.array([10000,0,0])))

    def test_invalid_inputs_and_unavailable_warp(self):
        for args in [('flipped',[1,2,3],'nonlinear'),('no',[1,2,3],'affine'),
                     ('synthetic',[1,2],'affine'),('synthetic',[1,float('nan'),3],'affine'),
                     ('synthetic',[-1,2,3],'affine'),('synthetic',[10000,2,3],'affine'),
                     ('synthetic',[125,25,25],'nonlinear')]:
            with self.subTest(args=args), self.assertRaises(ValueError):
                self.engine.convert(*args)

    def test_read_only_and_checksums(self):
        before = {p.name:p.read_bytes() for p in self.root.iterdir()}
        self.engine.check('synthetic', [50,75,100], 'nonlinear')
        DataBundle(self.root, verify_hashes=True)
        self.assertEqual(before, {p.name:p.read_bytes() for p in self.root.iterdir()})
        (self.root / 'meshes.json').write_text('[]')
        with self.assertRaisesRegex(ValueError, 'Checksum mismatch'):
            DataBundle(self.root, verify_hashes=True)

    def test_missing_truncated_and_outside_paths(self):
        with self.assertRaises(ValueError):
            DataBundle(self.root / 'absent')
        with self.assertRaises(ValueError):
            self.engine.bundle.path('../outside.npy')
        (self.root / 'meshes.json').write_text('incomplete')
        with self.assertRaisesRegex(ValueError, 'Incomplete or changed'):
            DataBundle(self.root)

if __name__ == '__main__':
    unittest.main()
