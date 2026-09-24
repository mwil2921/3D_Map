"""Build a standalone interactive 3D block model of kunanyi / Mt Wellington.

Reads the LIST 25 m DEM (Esri ASCII grid, GDA94 / MGA zone 55), packs the
heights into the HTML template, and inlines three.js so the result opens
from disk with no server or internet connection.

Run from this folder:
    pixi exec --spec python=3.12 --spec numpy python build_block_model.py
"""

import base64
import json
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
DEM = HERE.parent / "LIST_DEM_25M_HOBART" / "list_dem_25m_hobart.asc"
TEMPLATE = HERE / "template.html"
OUT = HERE / "kunanyi_block_model.html"
VENDOR = HERE / "vendor"

NODATA_CODE = 65535  # packed value used for NoData cells


def read_ascii_grid(path):
    header = {}
    with open(path) as f:
        for _ in range(6):
            key, value = f.readline().split()
            header[key.lower()] = float(value)
    data = np.loadtxt(path, skiprows=6, dtype=np.float64)
    nrows, ncols = int(header["nrows"]), int(header["ncols"])
    assert data.shape == (nrows, ncols), data.shape
    return header, data


def main():
    header, z = read_ascii_grid(DEM)
    nodata = header["nodata_value"]
    valid = z != nodata
    nrows, ncols = z.shape
    cell = header["cellsize"]
    # yllcorner is stored as 5245449.9999998 - snap to the cell grid.
    xll = round(header["xllcorner"] / cell) * cell
    yll = round(header["yllcorner"] / cell) * cell

    # Heights packed as unsigned decimetres (0.1 m precision, max 6553.4 m).
    packed = np.full(z.shape, NODATA_CODE, dtype="<u2")
    packed[valid] = np.round(z[valid] * 10).astype("<u2")

    zv = np.where(valid, z, -np.inf)
    r, c = np.unravel_index(np.argmax(zv), z.shape)
    meta = {
        "ncols": ncols,
        "nrows": nrows,
        "cellsize": cell,
        "xll": xll,
        "yll": yll,
        "nodata": NODATA_CODE,
        "scale": 0.1,
        "zmin": float(z[valid].min()),
        "zmax": float(z[valid].max()),
        "validCells": int(valid.sum()),
        "summit": {
            "row": int(r),
            "col": int(c),
            "elev": float(z[r, c]),
            "e": xll + (c + 0.5) * cell,
            "n": yll + (nrows - r - 0.5) * cell,
        },
    }

    html = TEMPLATE.read_text(encoding="utf-8")
    replacements = {
        "/*__THREE__*/": (VENDOR / "three.min.js").read_text(encoding="utf-8"),
        "/*__ORBIT__*/": (VENDOR / "OrbitControls.js").read_text(encoding="utf-8"),
        "/*__META__*/null": json.dumps(meta),
        "__DEM_B64__": base64.b64encode(packed.tobytes()).decode("ascii"),
    }
    for key, value in replacements.items():
        assert html.count(key) == 1, f"placeholder {key} missing or repeated"
        html = html.replace(key, value)
    OUT.write_text(html, encoding="utf-8")

    print(f"grid {ncols} x {nrows} @ {cell:g} m, {meta['validCells']:,} valid cells")
    print(f"elevation {meta['zmin']:.1f} - {meta['zmax']:.3f} m; summit E{meta['summit']['e']} N{meta['summit']['n']}")
    print(f"wrote {OUT.name} ({OUT.stat().st_size / 1e6:.2f} MB)")


if __name__ == "__main__":
    main()
