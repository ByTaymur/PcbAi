"""PcbAi İşaret button: open the Asistan window on its marker note for the current KiCad selection (plan IM)."""
from assistant import launch
from pcbai_kicad import run

run(lambda: launch("--marker"))
