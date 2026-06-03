import sys
import types
import unittest
from pathlib import Path
from unittest.mock import Mock, patch


class GuiDrapeTest(unittest.TestCase):
    def test_drape_3d_skips_png_rendering_for_gui(self):
        import gui.gui_pattern as gui_pattern

        class FakeProperties(dict):
            def set_section_stats(self, section, **stats):
                self[section].setdefault("stats", {}).update(stats)

        fake_paths = types.SimpleNamespace(
            in_g_spec=Path("Configured_design_specification.json"),
            g_sim=Path("Configured_design_3D_sim.obj"),
            g_sim_glb=Path("Configured_design_3D_sim.glb"),
            out_el=Path("tmp_gui/downloads/session/Configured_design_3D"),
        )
        fake_run_sim = Mock()

        fake_simulation = types.ModuleType("pygarment.meshgen.simulation")
        fake_simulation.run_sim = fake_run_sim
        fake_warp = types.ModuleType("warp")
        fake_warp.get_device = Mock(return_value=types.SimpleNamespace(is_cuda=True))

        pattern = gui_pattern.GUIPattern.__new__(gui_pattern.GUIPattern)
        pattern.default_body_params = object()
        pattern.design_params = {}
        pattern.save_path = Path("tmp_gui/downloads/session")
        pattern.sew_pattern = types.SimpleNamespace(name="Configured_design")
        pattern.save = Mock(return_value=Path("tmp_gui/downloads/session/pattern"))

        fake_mesh = Mock()
        fake_material = Mock()
        fake_mesh.visual.material.to_pbr.return_value = fake_material

        props = FakeProperties({
            "sim": {"config": {"resolution_scale": 1}},
            "render": {"config": {"uv_texture": None}},
        })

        with patch.dict(sys.modules, {"pygarment.meshgen.simulation": fake_simulation, "warp": fake_warp}):
            with patch.object(gui_pattern.data_config, "Properties", return_value=props):
                with patch.object(gui_pattern, "MetaGarment", return_value=types.SimpleNamespace(name="Configured_design")):
                    with patch.object(gui_pattern, "PathCofig", return_value=fake_paths):
                        with patch.object(gui_pattern, "BoxMesh") as fake_boxmesh:
                            with patch.object(gui_pattern.trimesh, "load_mesh", return_value=fake_mesh):
                                fake_boxmesh.return_value.name = "Configured_design_3D"

                                pattern.drape_3d()

        _, kwargs = fake_run_sim.call_args
        self.assertIs(kwargs["render"], False)

if __name__ == "__main__":
    unittest.main()
