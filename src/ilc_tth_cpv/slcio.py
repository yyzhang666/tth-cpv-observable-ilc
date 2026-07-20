"""pyLCIO access helpers (soft imports).

Reader patterns ported from analysis/tth/mva_inputs/io_lcio.py and the
theory-study scripts. Everything that does not need pyLCIO lives elsewhere so
the rest of the package stays testable without the ILC software stack.
"""

from __future__ import annotations

from pathlib import Path
from typing import Iterator, List, Optional


def require_pylcio():
    """Import pyLCIO or fail with the exact fix."""
    try:
        from pyLCIO import IOIMPL, UTIL  # type: ignore

        return IOIMPL, UTIL
    except Exception as exc:  # pragma: no cover - environment dependent
        raise RuntimeError(
            "Missing pyLCIO. Run: source env/setup.sh first (it loads the "
            "ZHH/ILCSoft software stack)."
        ) from exc


def vec_to_list(vec) -> list:
    if vec is None:
        return []
    try:
        return [vec[i] for i in range(int(vec.size()))]
    except Exception:
        try:
            return list(vec)
        except Exception:
            return []


def open_stdhep(path: Path):
    """LCStdHepRdr for generator stdhep files (theory-study pattern)."""
    _, UTIL = require_pylcio()
    return UTIL.LCStdHepRdr(str(path))


def iter_stdhep_events(reader, max_events: int = 0) -> Iterator[list]:
    """Yield MCParticle lists per stdhep physics event."""
    count = 0
    while True:
        if max_events and count >= max_events:
            return
        col = reader.readEvent()
        if col is None:
            return
        yield [col.getElementAt(i) for i in range(col.getNumberOfElements())]
        count += 1


def iter_slcio_events(paths: List[Path], max_events: int = 0) -> Iterator:
    """Yield LCEvent objects from one or more SLCIO files."""
    IOIMPL, _ = require_pylcio()
    count = 0
    for path in paths:
        reader = IOIMPL.LCFactory.getInstance().createLCReader()
        reader.open(str(path))
        try:
            while True:
                if max_events and count >= max_events:
                    return
                evt = reader.readNextEvent()
                if evt is None:
                    break
                yield evt
                count += 1
        finally:
            reader.close()


def list_collections(evt) -> List[str]:
    return [name for name in vec_to_list(evt.getCollectionNames())]


def get_collection(evt, name: str):
    """Collection or None (caller decides whether missing is fatal)."""
    try:
        return evt.getCollection(name)
    except Exception:
        return None


def pdg(mc) -> Optional[int]:
    try:
        return int(mc.getPDG())
    except Exception:
        return None


def four_momentum(obj) -> Optional[tuple]:
    """(E, px, py, pz) for MCParticle or ReconstructedParticle."""
    if obj is None:
        return None
    try:
        mom = obj.getMomentum()
        return (float(obj.getEnergy()), float(mom[0]), float(mom[1]), float(mom[2]))
    except Exception:
        return None


def get_pid_parameters(evt, jet_collection_name: str, algorithm: str = "weaver") -> list:
    """Extract PID parameter dictionaries per jet.

    `RefinedJets6` carries the 'weaver' PID algorithm (ParT-style flavor
    scores) and the 'yth' algorithm (ymerge values). Never read these from
    OutputErrorFlowJets6 (docs/KINFIT_JET_ASSIGNMENT.md).
    Returns a list of {parameter_name: value} per jet; empty dict when absent.
    """
    from pyLCIO import UTIL  # type: ignore

    collection = get_collection(evt, jet_collection_name)
    if collection is None:
        return []
    pid_handler = UTIL.PIDHandler(collection)
    try:
        algo_id = pid_handler.getAlgorithmID(algorithm)
    except Exception:
        return [{} for _ in range(collection.getNumberOfElements())]
    param_names = vec_to_list(pid_handler.getParameterNames(algo_id))
    out = []
    for i in range(collection.getNumberOfElements()):
        jet = collection.getElementAt(i)
        try:
            pid = pid_handler.getParticleID(jet, algo_id)
            values = vec_to_list(pid.getParameters())
            out.append({str(n): float(v) for n, v in zip(param_names, values)})
        except Exception:
            out.append({})
    return out
