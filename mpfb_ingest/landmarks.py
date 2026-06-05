"""Constant-vertex-index landmark registry for the fixed MakeHuman topology."""
import json
from pathlib import Path
import numpy as np


class Landmarks:
    def __init__(self, data: dict):
        self.n_vertices_expected = int(data.get("n_vertices_expected", 0))
        self.vertices = {k: int(v) for k, v in data.get("vertices", {}).items()}
        self.levels = {k: int(v) for k, v in data.get("levels", {}).items()}

    @classmethod
    def load(cls, path):
        return cls(json.loads(Path(path).read_text()))

    def vertex_index(self, name: str) -> int:
        return self.vertices[name]

    def point(self, mesh, name: str):
        return np.asarray(mesh.vertices[self.vertices[name]], dtype=np.float64)

    def level_y(self, mesh, name: str) -> float:
        return float(mesh.vertices[self.levels[name]][1])

    def validate(self, mesh):
        n = len(mesh.vertices)
        if self.n_vertices_expected and n != self.n_vertices_expected:
            raise ValueError(
                f"Mesh vertex count {n} != expected {self.n_vertices_expected}; "
                "topology mismatch (not the calibrated MakeHuman base mesh?)."
            )
        for name, idx in {**self.vertices, **self.levels}.items():
            if not (0 <= idx < n):
                raise ValueError(f"Landmark '{name}' index {idx} out of range (n={n}).")
