import unittest


class MatplotlibBackendTest(unittest.TestCase):
    def test_mesh_texture_rendering_uses_non_gui_backend(self):
        import matplotlib
        import pygarment.meshgen.render.texture_utils

        self.assertEqual(matplotlib.get_backend().lower(), "agg")


if __name__ == "__main__":
    unittest.main()
