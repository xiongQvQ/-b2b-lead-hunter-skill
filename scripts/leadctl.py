#!/usr/bin/env python3
"""Location-independent launcher; invoke with the skill's virtualenv Python."""
import sys
from pathlib import Path
root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root / "src"))
from lead_hunter.cli import main
if __name__ == "__main__":
    main()
