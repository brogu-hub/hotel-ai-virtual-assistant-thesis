#!/usr/bin/env python3
"""Generate a more meaningful Figure 6.1: per-category accuracy comparison."""
import subprocess, os, sys
from pathlib import Path

MMDC = os.path.expanduser("~/AppData/Roaming/npm/mmdc.cmd")
OUT = Path("thesis/figures/Fig_6.1_Accuracy_Comparison.png")

# Per-category grouped bar as an XY chart
mermaid = """---
config:
  theme: default
  xyChart:
    titleFontSize: 16
    chartOrientation: vertical
---
xychart-beta
    title "ความแม่นยำรายหมวดหมู่: Local 9B vs Cloud"
    x-axis ["Knowledge\\n(8 cases)", "Booking\\n(6 cases)", "Language\\n(3 cases)", "Greeting\\n(4 cases)", "Edge Cases\\n(4 cases)", "Overall\\n(25 cases)"]
    y-axis "ความแม่นยำ (%)" 0 --> 105
    bar [100, 100, 100, 75, 75, 92]
    bar [100, 100, 100, 100, 100, 100]
"""

def main():
    tmp = Path("thesis/figures/_tmp_6_1.mmd")
    tmp.write_text(mermaid, encoding="utf-8")
    cmd = [
        MMDC, "-i", str(tmp), "-o", str(OUT),
        "-s", "3", "-w", "1600", "-b", "white",
    ]
    print(f"Generating {OUT}...")
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        print(f"STDERR: {r.stderr}")
        # Fallback: simpler chart
        mermaid2 = """xychart-beta
    title "Per-Category Accuracy: Local 9B vs Cloud"
    x-axis ["Knowledge", "Booking", "Language", "Greeting", "Edge Cases", "Overall"]
    y-axis "Accuracy (%)" 0 --> 105
    bar [100, 100, 100, 75, 75, 92]
    bar [100, 100, 100, 100, 100, 100]
"""
        tmp.write_text(mermaid2, encoding="utf-8")
        r = subprocess.run(cmd, capture_output=True, text=True)
        if r.returncode != 0:
            print(f"Fallback also failed: {r.stderr}")
            sys.exit(1)
    tmp.unlink(missing_ok=True)
    print(f"OK: {OUT} ({OUT.stat().st_size // 1024} KB)")

if __name__ == "__main__":
    main()
