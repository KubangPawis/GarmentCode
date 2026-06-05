"""Clean-room MPFB/MakeHuman -> GarmentCode body-measurement ingestion.

Implemented from the published GarmentCode measurement definitions
(docs/Body Measurements GarmentCode.pdf). Does NOT use, link, or derive
from the GPLv3 mbotsch/GarmentMeasurements tool.
"""

__all__ = ["mesh_io", "geometry", "landmarks", "measurements", "emit"]
