# Horta Lookup

Enter an absolute Horta XYZ location, select a dataset, and see its Allen CCF location and whether it falls inside the midbrain reticular nucleus (MRN).

The app runs on each user's computer. Atlas and transform files live in a separate, versioned data folder on a shared drive such as `Z:\HortaLookupData` or a UNC path. This repository contains the tool; obtain the data folder from your lab's maintainer.

## Windows setup

1. Download this repository (**Code → Download ZIP**) and extract it into a local folder, or clone it.
2. Install [Python 3.12](https://www.python.org/downloads/windows/), including the Python launcher.
3. Double-click **Setup Windows.cmd**. This creates a local Python environment and installs the dependencies. Internet access is needed for this step.
4. Double-click **Start lookup.cmd**. On first use, select the shared data folder that contains `manifest.json`.
5. Choose a dataset, paste Horta **X, Y, Z in micrometers**, and click **Locate in atlas**.

Use **Configure data folder.cmd** to change the data location. Reopen the app afterward. The app also accepts `HORTA_LOOKUP_DATA` as an environment variable; it overrides the saved folder. Unset it when switching back to the folder chooser.

After setup, the lookup works without internet as long as the data folder is accessible. The app binds to your computer's loopback address, starting at port 8771. The launcher reuses a matching running app or finds a free port. Closing the browser tab leaves the local server running until sign-out; use the command-line server below when you want to stop it with Ctrl+C.

### Put data on the server once

Copy the **entire** `horta-lookup-data` folder to your server, for example `Z:\HortaLookupData`. Users need read access only. Keep the subfolders and `manifest.json` together. Run **Verify shared data.cmd** after selecting the copied folder; it checks every file's size and SHA-256 checksum.

The supplied bundle is about **1.24 GB**: a 25 µm atlas, region names, meshes, MRN voxel centers, dataset profiles, and the complete 609281 nonlinear field. It contains no traced neurons or fluorescence images. The warp retains its original values; adjacent vector components are stored together for efficient shared-drive reads. Do not put the bundle inside your code repository.

A UNC path such as `\\server\share\HortaLookupData` is useful if a mapped drive is unavailable in another Windows session. Startup reads about 308 MB of annotation data into memory; the warp is memory-mapped and sampled as needed. Startup can take longer over a slow network. Keep a versioned bundle unchanged while people use it; distribute changed transforms as a new bundle with a new ID.

### Local settings and saved checks

`settings.local.json` stores your data folder, output folder and starting port. It is ignored by Git. See `settings.example.json`. By default, **Save check** writes a dated folder under `saved_checks/` containing the input, CCF result, transform method, bundle ID and three atlas slice images. Saved checks and server logs are local and ignored by Git.

## Available transformations

| Dataset | Available mode | Registration |
| --- | --- | --- |
| 613814 | Affine only | CCF_Atlas_Registration10, October 2024 |
| 609281 | Affine + nonlinear, or affine comparison | CCF_Atlas_Registration, July 2023 |

The published 613814 nonlinear file is incomplete. The tool does not substitute a warp or silently fall back to another mode.

### Coordinate conventions

The supplied profiles convert Horta micrometers to source level-5 voxels by dividing by the native voxel spacing and 32. Dataset-specific axis flips and resampling follow. With the saved affine matrix A, translation t and center c, the inverse affine is `q = inverse(A) × (moving - c - t) + c`. For nonlinear mode, the saved inverse displacement is sampled trilinearly at q, then added to q. The resulting vector is multiplied by the registration's atlas spacing (10 or 25 µm) to obtain CCF **AP, DV, ML** in micrometers.

For 613814, X is flipped around voxel 2034 before resampling. For 609281 there is no such flip. These conventions are specific to these registrations; another dataset requires its own verified profile and field. The GUI's 3D axes display AP, ML, DV in millimeters; input and numerical results remain in micrometers.

### Interpretation

- Membership uses the nearest voxel in the **Allen CCFv3 2017 annotation at 25 µm**, including MRN IDs 128, 539, 548 and 555.
- Boundary distance is measured to MRN voxel boxes, whose faces lie 12.5 µm from their centers. The translucent mesh is a visual guide.
- The 100 µm marker highlights proximity to the boundary; it is not an error estimate.
- Hemisphere labels use lower/higher CCF ML around 5700 µm. Anatomical left/right is unverified.
- A correct implementation of a saved transform does not establish anatomical accuracy. Near-boundary assignments should be reviewed against the image.

## Command line

```powershell
.venv\Scripts\python.exe server.py --data-root "Z:\HortaLookupData" --port 8771
.venv\Scripts\python.exe verify_data.py --data-root "Z:\HortaLookupData"
.venv\Scripts\python.exe -m unittest discover -s tests -v
```

The server also accepts `--output-root`. On other operating systems, create a Python 3.12 environment, install `requirements.txt`, and run the same Python scripts with a mounted data path. The Windows setup is the tested path.

## Data provenance and validation

The bundle manifest records file hashes, dataset profiles preserve the original affine parameters, and the 609281 profile records the source warp URL and hash. Public source tests use small synthetic arrays and check affine inversion, flips, interpolation, MRN distances, input rejection, read-only operation and bundle integrity.

Before publication, the portable tool was compared with saved analyses of 4,068 points from 613814 and 12,989 points from 609281. The packaged warp was also compared with the original cached array for exact equality. Numerical agreement verifies implementation continuity, not anatomical ground truth.

Atlas sources: [Allen CCF annotation](https://download.alleninstitute.org/informatics-archive/current-release/mouse_ccf/annotation/ccf_2017/annotation_25.nrrd), [structure graph](https://api.brain-map.org/api/v2/structure_graph_download/1.json), and [CCF meshes](https://github.com/AllenNeuralDynamics/nmcp-static-resources/tree/main/assets/ccfv3/obj). Data remains subject to its source terms. The full atlas and warp are distributed separately from this repository.
