"""ilc_tth_cpv — shared physics library for the ILC ttH CPV student project.

All physics conventions are frozen in docs/PHYSICS_CONVENTIONS.md.
All ported implementations are tracked in docs/CODE_PROVENANCE.md.

Core modules are pure python (math only) so that unit tests run everywhere;
pyLCIO / numpy / matplotlib / catboost are imported lazily where needed.
"""

__version__ = "0.1.0"

from . import angles, frames, weights, fisher, polarization  # noqa: F401
