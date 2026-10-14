"""Named, evidenced limits; unknown IDs cannot silently justify a skipped check."""
from pcbai.core.contract import PcbAiError

LIMITS = {
    "L-IPC-NO-LIVE-SCH": "Live schematic IPC is not supported",
    "L-UNSAVED-BUFFER": "Only saved file revisions can be measured",
    "L-RENDER-SIZE-10.0.4": "KiCad 10.0.4 render dimensions need measured handling",
    "L-SYMLINK-WINDOWS": "Windows symlink tests require account privileges",
    "L-KH-LABEL-ALIAS": "UUID sheet scope is not a distinct label name",
    "L-KH-PIN-MULTIPLICITY": "External pin counts need multiplicity calibration",
    "L-KH-SMD-CATEGORY": "Connect pads are not necessarily SMD parts",
    "L-NO-INTENT-CHECK": "DRC/parity do not compare design intent",
    "L-EXTERNAL-MODEL-CALIBRATION": "Uncalibrated external models cannot certify dependent detectors",
    "L-FAB-CONNECTION-SUBSET": "Only calibrated positive linear surface artwork is supported; complex and plated paths are incomplete",
}


def require(limit_id):
    if limit_id not in LIMITS:
        raise PcbAiError("unknown_limit_id", "Unknown verification limit ID")
    return LIMITS[limit_id]
