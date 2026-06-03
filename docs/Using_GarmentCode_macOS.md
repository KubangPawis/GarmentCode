# Using GarmentCode on macOS

This guide covers GarmentCode, PyGarment, and the GarmentCodeData NVIDIA Warp
fork on macOS. It reflects the practical setup for Apple Silicon and current
macOS systems.

The important macOS constraint is that the GarmentCodeData Warp fork builds
CPU-only on macOS. The fork's `build_lib.py` explicitly disables CUDA on Darwin,
so CUDA/NVIDIA GPU acceleration is not available from this local macOS build.
Use Linux or Windows with an NVIDIA GPU for accelerated dataset-scale
simulation.

Commands assume this sibling repository layout:

```text
/Users/<you>/dev/kodecraft/outsourced/
  GarmentCode/
  NvidiaWarp-GarmentCode/
```

Do not put the Warp fork inside the GarmentCode repository. Install both
projects into the same Python environment.

## 1. What This Setup Provides

GarmentCode is the parametric sewing-pattern system. The repository contains:

- `pygarment/`: panels, edges, components, stitching, serialization, mesh
  generation, simulation helpers, rendering helpers, and data configuration.
- `assets/garment_programs/`: garment programs such as shirts, bodices,
  collars, sleeves, skirts, pants, and `MetaGarment`.
- `assets/design_params/`: YAML design presets used by the GUI and scripts.
- `assets/bodies/`: default body meshes, measurements, and segmentation files.
- `assets/Sim_props/`: simulation and rendering presets.
- `gui.py` and `gui/`: the NiceGUI browser configurator.
- `test_garmentcode.py`: one-off 2D sewing-pattern generation.
- `test_garment_sim.py`: one-off Warp draping of a pattern JSON.
- `pattern_sampler.py`: random sewing-pattern dataset generation.
- `pattern_data_sim.py`: batch Warp simulation of generated datasets.

The GarmentCodeData Warp fork is not the same as public `warp-lang` from PyPI.
PyGarment v2.0.0+ uses the fork because it includes garment-specific XPBD cloth
simulation additions.

## 2. macOS Reality Check

What works locally on macOS:

- The browser GUI.
- 2D sewing-pattern generation.
- Pattern serialization to JSON, SVG, PNG, and printable PDF.
- CPU-only Warp simulation after building the Warp fork.
- Small smoke-test draping runs.

What should be moved to Linux/Windows with NVIDIA GPU:

- Large GarmentCodeData dataset draping.
- Production-scale simulation batches.
- Performance-sensitive XPBD simulation experiments.

Known macOS setup issues:

- Python 3.14 is too new for this old Warp fork.
- The GarmentCode environment should use Python 3.9.
- `CairoSVG` needs the native Cairo library discoverable by Python.
- The Warp fork must be built before `pip install -e .` or `uv pip install -e .`.
- The current Warp fork build creates universal macOS dylibs and downloads
  LLVM/Clang dependencies through Packman.

## 3. Install macOS System Tools

Install Xcode Command Line Tools:

```bash
xcode-select --install
```

Install Homebrew if needed, then install native dependencies:

```bash
brew install git git-lfs cairo
```

Verify:

```bash
git lfs version
clang --version
g++ --version
brew --prefix cairo
```

On Apple Silicon, Cairo is normally under:

```text
/opt/homebrew/lib
```

## 4. Use the Existing GarmentCode Virtual Environment

In this workspace, GarmentCode already has:

```text
/Users/kubangpawis/dev/kodecraft/outsourced/GarmentCode/.venv
```

It is a `uv` environment using CPython 3.9.25, which is a good match for
GarmentCode.

Activate it:

```bash
cd /Users/kubangpawis/dev/kodecraft/outsourced/GarmentCode
source .venv/bin/activate
```

This venv was created without `pip`, so use `uv pip` for package changes:

```bash
env UV_CACHE_DIR=/private/tmp/uv-cache \
  uv pip list --python .venv/bin/python
```

If you are setting up from scratch instead:

```bash
cd /Users/kubangpawis/dev/kodecraft/outsourced/GarmentCode
uv venv --python 3.9 .venv
source .venv/bin/activate
env UV_CACHE_DIR=/private/tmp/uv-cache uv pip install --python .venv/bin/python -e .
```

## 5. Configure macOS Environment Variables

Set these before running GarmentCode commands that import `pygarment`, render,
or simulate:

```bash
export DYLD_FALLBACK_LIBRARY_PATH=/opt/homebrew/lib
export MPLCONFIGDIR=/private/tmp/matplotlib-cache
```

Why:

- `DYLD_FALLBACK_LIBRARY_PATH` lets `cairocffi` find Homebrew's
  `libcairo.2.dylib`.
- `MPLCONFIGDIR` avoids Matplotlib trying to write font cache files under an
  unwritable home cache path.

You can add them to your shell profile if you use this project often:

```bash
echo 'export DYLD_FALLBACK_LIBRARY_PATH=/opt/homebrew/lib' >> ~/.zshrc
echo 'export MPLCONFIGDIR=/private/tmp/matplotlib-cache' >> ~/.zshrc
```

Verify Cairo:

```bash
DYLD_FALLBACK_LIBRARY_PATH=/opt/homebrew/lib \
.venv/bin/python - <<'PY'
import cairosvg
print("CairoSVG OK:", cairosvg.__file__)
PY
```

## 6. Configure `system.json`

`system.json` is GarmentCode's local path configuration file. It is not part of
NVIDIA Warp. It tells GarmentCode where to write logs, generated pattern
datasets, simulation outputs, and where to find simulation configs and body
assets.

Create it in the GarmentCode repo root:

```bash
cd /Users/kubangpawis/dev/kodecraft/outsourced/GarmentCode
mkdir -p Logs datasets datasets_sim
cp system.template.json system.json
```

Use this starter:

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

For full dataset generation, replace `body_samples_path` with the parent folder
that contains the GarmentCodeData body-shape sample dataset, commonly:

```text
5000_body_shapes_and_measures/
```

Verify:

```bash
DYLD_FALLBACK_LIBRARY_PATH=/opt/homebrew/lib \
.venv/bin/python - <<'PY'
from pygarment.data_config import Properties
p = Properties("system.json")
print(p.properties)
PY
```

## 7. Build the GarmentCodeData Warp Fork on macOS

Make sure the GarmentCode venv is the Python used for the build.

```bash
cd /Users/kubangpawis/dev/kodecraft/outsourced/NvidiaWarp-GarmentCode
git lfs install
git lfs pull
chmod +x tools/packman/packman tools/packman/python.sh
export PM_PACKAGES_ROOT="$PWD/.packman-cache"
../GarmentCode/.venv/bin/python build_lib.py
```

Expected macOS build outputs:

```text
warp/bin/libwarp.dylib
warp/bin/libwarp-clang.dylib
```

On macOS the build script:

- ignores `CUDA_PATH`
- builds without CUDA support
- downloads prebuilt LLVM/Clang packages with Packman
- builds `x86_64` and `aarch64` slices
- combines them into universal dylibs with `lipo`

If Packman cannot write to its default cache, keep:

```bash
export PM_PACKAGES_ROOT="$PWD/.packman-cache"
```

If `tools/packman/packman` reports permission denied, re-run:

```bash
chmod +x tools/packman/packman tools/packman/python.sh
```

## 8. Install the Warp Fork into the GarmentCode Venv

From the Warp fork repo:

```bash
cd /Users/kubangpawis/dev/kodecraft/outsourced/NvidiaWarp-GarmentCode

env UV_CACHE_DIR=/private/tmp/uv-cache \
  uv pip install --python ../GarmentCode/.venv/bin/python -e .
```

Install USD bindings if needed:

```bash
env UV_CACHE_DIR=/private/tmp/uv-cache \
  uv pip install --python ../GarmentCode/.venv/bin/python usd-core
```

Do not replace this with:

```bash
pip install warp-lang
```

Public `warp-lang` is not the GarmentCodeData fork.

## 9. Verify Warp and GarmentCode Together

From the GarmentCode repo root:

```bash
cd /Users/kubangpawis/dev/kodecraft/outsourced/GarmentCode

DYLD_FALLBACK_LIBRARY_PATH=/opt/homebrew/lib \
MPLCONFIGDIR=/private/tmp/matplotlib-cache \
PYTHONDONTWRITEBYTECODE=1 \
.venv/bin/python - <<'PY'
import warp as wp
wp.init()
print("Warp version:", wp.config.version)
print("CUDA available:", wp.is_cuda_available())
print("Devices:", wp.get_devices())
import pygarment.meshgen.simulation
print("GarmentCode simulation imports OK")
PY
```

Expected:

- Warp version is `1.0.0-beta.6`.
- CUDA is `False` on macOS.
- Devices include CPU.
- `pygarment.meshgen.simulation` imports without error.

If `wp.init()` fails with `libwarp.dylib` missing, build the Warp fork first.

If `pygarment` fails with a Cairo error, set
`DYLD_FALLBACK_LIBRARY_PATH=/opt/homebrew/lib`.

## 10. Run the Browser Configurator

```bash
cd /Users/kubangpawis/dev/kodecraft/outsourced/GarmentCode

DYLD_FALLBACK_LIBRARY_PATH=/opt/homebrew/lib \
MPLCONFIGDIR=/private/tmp/matplotlib-cache \
.venv/bin/python gui.py
```

Open the URL printed by NiceGUI, usually:

```text
http://localhost:8080
```

The GUI loads:

- design defaults from `assets/design_params/default.yaml`
- body defaults from `assets/bodies/mean_all.yaml`
- 2D preview assets from `assets/img`
- draping config from `assets/Sim_props/gui_sim_props.yaml`

The 2D pattern workflow should be the first macOS smoke test. The 3D drape can
work after Warp is built, but it will run on CPU.

## 11. Generate One Sewing Pattern

Run:

```bash
cd /Users/kubangpawis/dev/kodecraft/outsourced/GarmentCode

DYLD_FALLBACK_LIBRARY_PATH=/opt/homebrew/lib \
MPLCONFIGDIR=/private/tmp/matplotlib-cache \
.venv/bin/python test_garmentcode.py
```

The script:

1. reads `system.json`
2. loads `assets/bodies/mean_all.yaml`
3. loads `assets/design_params/t-shirt.yaml`
4. builds a `MetaGarment`
5. writes JSON, SVG/PNG preview files, and printable output under
   `system["output"]`

Change the body by editing `body_to_use` in `test_garmentcode.py`.

Change the design by editing the `design_files` dictionary in
`test_garmentcode.py`.

## 12. Simulate One Existing Pattern on macOS CPU

Run:

```bash
DYLD_FALLBACK_LIBRARY_PATH=/opt/homebrew/lib \
MPLCONFIGDIR=/private/tmp/matplotlib-cache \
.venv/bin/python test_garment_sim.py \
  --pattern_spec ./assets/Patterns/shirt_mean_specification.json \
  --sim_config ./assets/Sim_props/default_sim_props.yaml
```

This is a CPU simulation smoke test. Expect it to be slower than a CUDA-enabled
Linux workstation.

The script:

1. reads `system.json`
2. creates a simulation output context under `system["output"]`
3. creates a box mesh from the pattern
4. runs Warp XPBD simulation
5. writes simulation metadata and stats

## 13. Generate and Simulate a Small Dataset

For local macOS testing, keep dataset sizes small:

```bash
DYLD_FALLBACK_LIBRARY_PATH=/opt/homebrew/lib \
MPLCONFIGDIR=/private/tmp/matplotlib-cache \
.venv/bin/python pattern_sampler.py --name smoke-test --size 3
```

Then simulate the default-body subset:

```bash
DYLD_FALLBACK_LIBRARY_PATH=/opt/homebrew/lib \
MPLCONFIGDIR=/private/tmp/matplotlib-cache \
.venv/bin/python pattern_data_sim.py \
  --data <dataset_folder_name> \
  --config default_sim_props.yaml \
  --default_body \
  --minibatch 1
```

Use Linux/Windows with CUDA for serious dataset generation and draping.

## 14. Common macOS Troubleshooting

### `python3` Is 3.14 and Warp Import Fails

Use the GarmentCode `.venv` Python 3.9:

```bash
cd /Users/kubangpawis/dev/kodecraft/outsourced/GarmentCode
.venv/bin/python --version
```

Do not build this Warp fork with Python 3.14.

### The Venv Has No `pip`

Use `uv pip`:

```bash
env UV_CACHE_DIR=/private/tmp/uv-cache \
  uv pip list --python /Users/kubangpawis/dev/kodecraft/outsourced/GarmentCode/.venv/bin/python
```

### `CairoSVG` Cannot Find `cairo`

Confirm Homebrew Cairo exists:

```bash
brew list --versions cairo
ls /opt/homebrew/lib/libcairo.2.dylib
```

Run commands with:

```bash
export DYLD_FALLBACK_LIBRARY_PATH=/opt/homebrew/lib
```

### Matplotlib Tries to Write to an Unwritable Cache

Set:

```bash
export MPLCONFIGDIR=/private/tmp/matplotlib-cache
```

### `ModuleNotFoundError: No module named 'warp'`

The Warp fork is not installed in the GarmentCode venv:

```bash
cd /Users/kubangpawis/dev/kodecraft/outsourced/NvidiaWarp-GarmentCode
env UV_CACHE_DIR=/private/tmp/uv-cache \
  uv pip install --python ../GarmentCode/.venv/bin/python -e .
```

### `Failed to load libwarp.dylib`

The Warp fork source is importable, but the native library was not built:

```bash
cd /Users/kubangpawis/dev/kodecraft/outsourced/NvidiaWarp-GarmentCode
../GarmentCode/.venv/bin/python build_lib.py
```

### CUDA Is Not Available

This is expected on macOS for this fork. The build script disables CUDA on
Darwin. Use Linux/Windows with an NVIDIA GPU for CUDA simulation.

### `usd-core` or `pxr` Is Missing

Install it into the GarmentCode venv:

```bash
env UV_CACHE_DIR=/private/tmp/uv-cache \
  uv pip install --python /Users/kubangpawis/dev/kodecraft/outsourced/GarmentCode/.venv/bin/python usd-core
```

### Dataset Generation Cannot Find Body Samples

Update `body_samples_path` in `system.json`. The placeholder
`./assets/bodies` is enough for some local smoke tests, but full random-body
dataset workflows expect a separate body-shape sample dataset.

## 15. Recommended macOS Workflow

1. Activate `GarmentCode/.venv`.
2. Export `DYLD_FALLBACK_LIBRARY_PATH` and `MPLCONFIGDIR`.
3. Create `system.json`.
4. Build `NvidiaWarp-GarmentCode` using `../GarmentCode/.venv/bin/python`.
5. Install the built Warp fork into the GarmentCode venv with `uv pip`.
6. Verify `wp.init()` and `pygarment.meshgen.simulation`.
7. Run `test_garmentcode.py`.
8. Run a small `test_garment_sim.py` CPU smoke test.
9. Use the GUI for design exploration.
10. Move large simulation batches to CUDA Linux/Windows.

## 16. Related Docs

- `docs/Installation.md`
- `docs/Running_garmentcode.md`
- `docs/Running_data_generation.md`
- `docs/Running_Maya_Qualoth.md`
- `docs/Body Measurements GarmentCode.pdf`
- `docs/Using_GarmentCode_Windows_Linux.md`
