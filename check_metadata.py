#!/usr/bin/env python3
"""Run metadata consistency check."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent / "tools"))
import check_metadata
if __name__ == "__main__":
    sys.exit(check_metadata.main())
