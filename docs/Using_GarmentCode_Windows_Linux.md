# Using GarmentCode on Windows and Linux

This guide covers a full Windows/Linux setup for GarmentCode, PyGarment, and the
GarmentCodeData NVIDIA Warp fork. It is intended for systems where CUDA support
is possible, especially Linux workstations or servers with NVIDIA GPUs.

For Apple Silicon or Intel macOS, use `docs/Using_GarmentCode_macOS.md`
instead. The macOS build path is CPU-only because this Warp fork disables CUDA
on Darwin.

Commands assume this sibling repository layout:

```text
<workspace>/
  GarmentCode/
  NvidiaWarp-GarmentCode/
```

Do not place the Warp fork inside the GarmentCode repository. Install both
projects into the same Python environment.

## 1. What This Setup Provides

GarmentCode is the parametric sewing-pattern system. The repository contains:

- `pygarment/`: panels, edges, components, stitching, serialization, mesh
  generation, simulation helpers, rendering helpers, and data configuration.
- `assets/garment_programs/`: provided garment programs such as shirts,
  bodices, collars, sleeves, skirts, pants, and `MetaGarment`.
- `assets/design_params/`: design YAML presets used by the GUI and scripts.
- `assets/bodies/`: default body meshes, measurements, and segmentations.
- `assets/Sim_props/`: simulation and rendering configuration presets.
- `gui.py` and `gui/`: the NiceGUI browser configurator.
- `test_garmentcode.py`: one-off 2D sewing-pattern generation.
- `test_garment_sim.py`: one-off Warp draping of a pattern JSON.
- `pattern_sampler.py`: random sewing-pattern dataset generation.
- `pattern_fitter.py`: fitting one design to many body shapes.
- `pattern_data_sim.py`: batch Warp simulation of generated datasets.

The GarmentCodeData Warp fork provides the simulation backend used by
PyGarment v2.0.0+. It adds cloth-specific XPBD behavior that is not available
from the public `warp-lang` package on PyPI.

## 2. Platform Expectations

Use Linux if you want the most practical CUDA path. Windows is supported by the
Warp build scripts, but the surrounding GarmentCode research workflow is usually
more straightforward on Linux.

Minimum practical requirements:

- Python 3.9 for GarmentCode.
- Git and Git LFS.
- A C++ compiler.
- CUDA Toolkit 11.5 or newer if CUDA acceleration is required.
- NVIDIA driver compatible with your CUDA Toolkit.
- Enough disk space for generated datasets and simulation output.

Windows-specific requirements:

- Microsoft Visual Studio 2019 or newer with C++ build tools.
- Windows SDK.
- Git LFS.
- Python 3.9, preferably through conda.

Linux-specific requirements:

- GCC/G++ 7.2 or newer for this Warp fork.
- CUDA Toolkit 11.5 or newer for GPU builds.
- `curl` or `wget`, because Packman downloads LLVM/Clang dependencies.
- System libraries needed by `CairoSVG`, `pyrender`, and OpenGL if you render.

## 3. Create the Python Environment

The project documentation expects Python 3.9. Use one environment for both
GarmentCode and the Warp fork.

### Linux

```bash
cd <workspace>/GarmentCode
python3.9 -m venv .venv
source .venv/bin/activate
python -m pip install -U pip setuptools wheel build
python -m pip install -e .
```

If your system Python is not 3.9, use conda:

```bash
conda create -n garmentcode python=3.9
conda activate garmentcode
cd <workspace>/GarmentCode
pip install -U pip setuptools wheel build
pip install -e .
```

### Windows

Run these from Anaconda Prompt, PowerShell, or a terminal where Visual Studio
build tools are available:

```powershell
cd <workspace>\GarmentCode
conda create -n garmentcode python=3.9
conda activate garmentcode
python -m pip install -U pip setuptools wheel build
python -m pip install -e .
```

Verify the environment:

```bash
python - <<'PY'
import sys
import numpy
print(sys.executable)
print(sys.version)
print("numpy", numpy.__version__)
PY
```

## 4. Configure `system.json`

`system.json` is GarmentCode's machine-local path file. It is not part of Warp.
It tells GarmentCode where to write logs, generated sewing-pattern datasets,
simulation outputs, body samples, and simulation configs.

Create it in the GarmentCode repo root:

```bash
cd <workspace>/GarmentCode
mkdir -p Logs datasets datasets_sim
cp system.template.json system.json
```

Use this as a local starter:

```json
{
  "output": "./Logs/",
  "datasets_path": "./datasets",
  "datasets_sim": "./datasets_sim",
  "sim_configs_path": "./assets/Sim_props",
  "bodies_default_path": "./assets/bodies",
  "body_samples_path": "./assets/bodies"
}
```

Key meanings:

- `output`: one-off script logs and outputs.
- `datasets_path`: generated 2D pattern datasets.
- `datasets_sim`: Warp draping and simulation results.
- `sim_configs_path`: simulation config files, normally `./assets/Sim_props`.
- `bodies_default_path`: default body assets, normally `./assets/bodies`.
- `body_samples_path`: body-shape sample datasets. Replace this with the full
  GarmentCodeData body sample folder if you have it.

Verify it loads:

```bash
python - <<'PY'
from pygarment.data_config import Properties
p = Properties("system.json")
print(p.properties)
PY
```

## 5. Build and Install the GarmentCodeData Warp Fork

Do not install public `warp-lang` for GarmentCodeData simulation. The public
package is not the fork used by PyGarment v2.0.0+.

### 5.1 Clone and Fetch LFS Assets

```bash
cd <workspace>
git clone https://github.com/maria-korosteleva/NvidiaWarp-GarmentCode.git
cd NvidiaWarp-GarmentCode
git lfs install
git lfs pull
```

If the repo is already cloned, still run `git lfs pull`.

### 5.2 Linux CUDA Build

Make sure the GarmentCode environment is active:

```bash
cd <workspace>/GarmentCode
source .venv/bin/activate
```

Set CUDA if it is not already discoverable:

```bash
export CUDA_PATH=/usr/local/cuda
export CUDA_HOME=/usr/local/cuda
export PATH="$CUDA_PATH/bin:$PATH"
```

Build from the Warp fork:

```bash
cd <workspace>/NvidiaWarp-GarmentCode
chmod +x tools/packman/packman tools/packman/python.sh
export PM_PACKAGES_ROOT="$PWD/.packman-cache"
python build_lib.py
python -m pip install -e .
```

Expected Linux build outputs:

```text
warp/bin/warp.so
warp/bin/warp-clang.so
```

If CUDA is missing or not found, the build can still produce a CPU-only Warp
library. For dataset-scale GarmentCodeData simulation, use a CUDA-capable Linux
machine when possible.

### 5.3 Windows Build

Run from a Developer PowerShell or terminal with MSVC available:

```powershell
conda activate garmentcode
cd <workspace>\NvidiaWarp-GarmentCode
python build_lib.py
python -m pip install -e .
```

If CUDA is not in its default location, pass it explicitly:

```powershell
python build_lib.py --cuda_path="C:\Program Files\NVIDIA GPU Computing Toolkit\CUDA\v11.8"
```

Expected Windows build outputs:

```text
warp/bin/warp.dll
warp/bin/warp-clang.dll
```

If MSVC cannot be found automatically, use the `--msvc_path` and `--sdk_path`
options shown by:

```powershell
python build_lib.py --help
```

### 5.4 Verify Warp in the GarmentCode Environment

Run from anywhere while the GarmentCode environment is active:

```bash
python - <<'PY'
import warp as wp
wp.init()
print("Warp version:", wp.config.version)
print("CUDA available:", wp.is_cuda_available())
print("Devices:", wp.get_devices())
PY
```

The expected version for this fork is:

```text
1.0.0-beta.6
```

If Python imports a different Warp version, uninstall it and reinstall the fork:

```bash
python -m pip uninstall -y warp-lang
cd <workspace>/NvidiaWarp-GarmentCode
python -m pip install -e .
```

## 6. Optional USD and Rendering Dependencies

Install USD bindings if you want USD outputs or examples that use
`warp.render.UsdRenderer`:

```bash
python -m pip install usd-core
```

Linux rendering may also need system OpenGL/EGL libraries depending on the
machine and renderer.

## 7. Verify GarmentCode Imports

From the GarmentCode repo root:

```bash
cd <workspace>/GarmentCode
python - <<'PY'
import pygarment
import pygarment.meshgen.simulation
print("PyGarment OK:", pygarment.__file__)
print("Simulation imports OK")
PY
```

Then verify command-line help:

```bash
python pattern_data_sim.py --help
python test_garment_sim.py --help
```

## 8. Run the Browser Configurator

Start the GUI:

```bash
cd <workspace>/GarmentCode
python gui.py
```

Open the URL printed by NiceGUI, usually:

```text
http://localhost:8080
```

The GUI loads:

- design defaults from `assets/design_params/default.yaml`
- body defaults from `assets/bodies/mean_all.yaml`
- 2D preview assets from `assets/img`
- simulation settings from `assets/Sim_props/gui_sim_props.yaml`

The 2D pattern workflow can work without Warp. The 3D drape requires the Warp
fork.

## 9. Generate One Sewing Pattern

Run:

```bash
python test_garmentcode.py
```

The script:

1. loads body measurements from `assets/bodies/mean_all.yaml`
2. loads design parameters from `assets/design_params/t-shirt.yaml`
3. builds a `MetaGarment`
4. serializes a pattern JSON, SVG/PNG previews, and printable output
5. writes under `system["output"]`

To change the body, edit `body_to_use` in `test_garmentcode.py`.

To change the design, edit the `design_files` dictionary in
`test_garmentcode.py`.

## 10. Simulate One Existing Pattern

Run:

```bash
python test_garment_sim.py \
  --pattern_spec ./assets/Patterns/shirt_mean_specification.json \
  --sim_config ./assets/Sim_props/default_sim_props.yaml
```

The script:

1. reads `system.json`
2. creates a simulation output context under `system["output"]`
3. creates a box mesh from the pattern
4. runs the Warp XPBD simulation
5. writes simulation metadata and updated stats

If this command fails with `ModuleNotFoundError: No module named 'warp'`, the
Warp fork is not installed in the active Python environment.

If this command initializes Warp but reports no CUDA devices, check the NVIDIA
driver, CUDA Toolkit, and `CUDA_PATH`.

## 11. Generate a Dataset

For a small smoke test:

```bash
python pattern_sampler.py --name smoke-test --size 10
```

For batched generation:

```bash
python pattern_sampler.py --name garmentcodedata --size 100 --batch_id 0
```

The sampler writes under `system["datasets_path"]`. It creates default-body
and random-body pattern subsets when body samples are available.

The default full body-sample folder expected by the scripts is:

```text
5000_body_shapes_and_measures/
```

Set `body_samples_path` in `system.json` to the parent folder containing that
dataset.

## 12. Simulate a Dataset

Simulate the default-body subset:

```bash
python pattern_data_sim.py \
  --data <dataset_folder_name> \
  --config default_sim_props.yaml \
  --default_body
```

Simulate the random-body subset:

```bash
python pattern_data_sim.py \
  --data <dataset_folder_name> \
  --config default_sim_props.yaml
```

Use mini-batches for long runs:

```bash
python pattern_data_sim.py \
  --data <dataset_folder_name> \
  --config default_sim_props.yaml \
  --minibatch 100
```

Simulation outputs go under `system["datasets_sim"]`. Progress and failure
metadata are stored in dataset properties YAML files so runs can resume.

## 13. Common Troubleshooting

### `system.json` Is Missing

Create it from `system.template.json` in the GarmentCode repo root.

### `ModuleNotFoundError: No module named 'warp'`

The Warp fork is not installed in the active GarmentCode environment. Activate
the environment and run:

```bash
cd <workspace>/NvidiaWarp-GarmentCode
python -m pip install -e .
```

If the install fails with `No libraries found in warp/bin`, run
`python build_lib.py` first.

### Wrong Warp Version

Run:

```bash
python - <<'PY'
import warp
print(warp.__file__)
print(warp.config.version)
PY
```

GarmentCodeData should use the sibling `NvidiaWarp-GarmentCode` checkout and
version `1.0.0-beta.6`.

### CUDA Is Not Available

On Linux/Windows:

- confirm `nvidia-smi` works
- confirm `nvcc --version` works
- confirm `CUDA_PATH` or `CUDA_HOME` points to the CUDA Toolkit
- rebuild the Warp fork after fixing CUDA

### `usd-core` or `pxr` Is Missing

Install:

```bash
python -m pip install usd-core
```

### Cairo or CairoSVG Fails

Install the native Cairo system package.

Linux examples:

```bash
sudo apt-get install libcairo2 libcairo2-dev
```

Windows users should prefer the packages installed through the Python
environment or conda where possible.

### GUI Draping Fails but 2D Pattern Works

The 2D GUI does not require Warp. The 3D drape button imports
`pygarment.meshgen.simulation`, which imports `warp`. Verify the Warp fork in
the same environment used to launch `gui.py`.

### Dataset Generation Cannot Find Body Samples

Set `body_samples_path` in `system.json` to the parent folder containing the
body sample dataset.

## 14. Recommended Workflow

1. Install GarmentCode in Python 3.9.
2. Create `system.json`.
3. Build and install `NvidiaWarp-GarmentCode` in the same environment.
4. Verify `import warp`, `wp.init()`, and `pygarment.meshgen.simulation`.
5. Run `python test_garmentcode.py`.
6. Run `python test_garment_sim.py`.
7. Use the GUI for design exploration.
8. Generate and simulate small datasets before running large batches.

## 15. Related Docs

- `docs/Installation.md`
- `docs/Running_garmentcode.md`
- `docs/Running_data_generation.md`
- `docs/Running_Maya_Qualoth.md`
- `docs/Body Measurements GarmentCode.pdf`
- `docs/Using_GarmentCode_macOS.md`
