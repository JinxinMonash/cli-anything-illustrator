"""Visual comparison engine.

``compare_images(ref_png, candidate_png, ...)`` registers two rendered
images, computes global fidelity metrics (pixel MAE, RMSE, SSIM, Sobel
edge-map F1, mean CIE76 Lab delta), localizes the largest discrepancies on
a tile grid, writes a heatmap and a magenta/green overlay PNG, and
``map_regions_to_objects`` maps discrepancy regions to Illustrator item
descriptors (bounds in points) from the CLI's items_list output.

All numerics are numpy-only (no scipy / scikit-image) and deterministic.
"""

import math
import os

from cli_anything.illustrator.fidelity import require

# Sobel edge threshold on gradient magnitude of 0-255 grayscale.
EDGE_THRESHOLD = 96.0
# Tile is reported only when its mean (1 - SSIM) exceeds this floor.
REGION_FLOOR = 0.02
# Colour-aware region triggering: SSIM works on luminance, so an isoluminant
# recolour (e.g. pink -> light blue) can be nearly SSIM-invisible. A tile also
# becomes a region when its mean CIE76 delta-E exceeds COLOR_REGION_MIN, and
# the tile score blends both signals (delta-E normalised by COLOR_DELTA_NORM).
COLOR_REGION_MIN = 6.0
COLOR_DELTA_NORM = 50.0
# Severity cut-offs on mean (1 - SSIM) per tile.
SEVERITY_HIGH = 0.5
SEVERITY_MED = 0.2
# probable_type heuristics.
TEXT_EDGE_DENSITY = 0.14   # fraction of edge pixels (union) in the tile
COLOR_EDGE_XOR_MAX = 0.01  # edge-map disagreement below this = same geometry
COLOR_DELTA_MIN = 8.0      # mean CIE76 delta-E above this = colour change
MAX_REGIONS = 10


# ------------------------------------------------------------ numpy helpers

def _np():
    return require("numpy")


def _load_rgb(path):
    """Load as RGB float64, compositing any alpha onto WHITE.

    Illustrator exports PNG24 with a transparent background by default;
    a naive RGBA->RGB conversion drops alpha to black and makes the whole
    canvas compare as a mismatch against white-background reference renders
    (found in the first live reconstruct run: pixel_mae ~247).
    """
    np = _np()
    Image = require("PIL.Image")
    with Image.open(path) as im:
        if im.mode in ("RGBA", "LA") or \
                (im.mode == "P" and "transparency" in im.info):
            rgba = im.convert("RGBA")
            bg = Image.new("RGBA", rgba.size, (255, 255, 255, 255))
            bg.alpha_composite(rgba)
            return np.asarray(bg.convert("RGB"), dtype=np.float64)
        return np.asarray(im.convert("RGB"), dtype=np.float64)


def _conv1d(a, k, axis):
    """Separable 1-D correlation along ``axis`` with reflect padding."""
    np = _np()
    from numpy.lib.stride_tricks import sliding_window_view
    k = np.asarray(k, dtype=np.float64)
    pad = len(k) // 2
    spec = [(0, 0)] * a.ndim
    spec[axis] = (pad, pad)
    padded = np.pad(a, spec, mode="reflect")
    moved = np.moveaxis(padded, axis, -1)
    win = sliding_window_view(moved, len(k), axis=-1)
    out = win @ k
    return np.moveaxis(out, -1, axis)


def _gaussian_kernel(size=11, sigma=1.5):
    np = _np()
    x = np.arange(size, dtype=np.float64) - (size - 1) / 2.0
    k = np.exp(-(x * x) / (2.0 * sigma * sigma))
    return k / k.sum()


def _gray(rgb):
    return (0.299 * rgb[..., 0] + 0.587 * rgb[..., 1]
            + 0.114 * rgb[..., 2])


def _ssim_map(g1, g2):
    """Standard SSIM map: 11x11 gaussian window (sigma 1.5), K1=0.01,
    K2=0.03, L=255."""
    k = _gaussian_kernel(11, 1.5)

    def blur(im):
        return _conv1d(_conv1d(im, k, 0), k, 1)

    C1 = (0.01 * 255.0) ** 2
    C2 = (0.03 * 255.0) ** 2
    mu1, mu2 = blur(g1), blur(g2)
    mu1s, mu2s, mu12 = mu1 * mu1, mu2 * mu2, mu1 * mu2
    s1 = blur(g1 * g1) - mu1s
    s2 = blur(g2 * g2) - mu2s
    s12 = blur(g1 * g2) - mu12
    return (((2.0 * mu12 + C1) * (2.0 * s12 + C2))
            / ((mu1s + mu2s + C1) * (s1 + s2 + C2)))


def _sobel_magnitude(g):
    np = _np()
    diff = np.array([1.0, 0.0, -1.0])
    smooth = np.array([1.0, 2.0, 1.0])
    gx = _conv1d(_conv1d(g, diff, 1), smooth, 0)
    gy = _conv1d(_conv1d(g, diff, 0), smooth, 1)
    return np.hypot(gx, gy)


def _edge_map(g):
    return _sobel_magnitude(g) > EDGE_THRESHOLD


def _edge_f1(e1, e2):
    np = _np()
    inter = float(np.logical_and(e1, e2).sum())
    a, b = float(e1.sum()), float(e2.sum())
    if a + b == 0.0:
        return 1.0
    return 2.0 * inter / (a + b)


def _rgb_to_lab(rgb):
    """sRGB (0-255) -> CIE Lab (D65)."""
    np = _np()
    c = rgb / 255.0
    lin = np.where(c <= 0.04045, c / 12.92,
                   ((c + 0.055) / 1.055) ** 2.4)
    M = np.array([[0.4124564, 0.3575761, 0.1804375],
                  [0.2126729, 0.7151522, 0.0721750],
                  [0.0193339, 0.1191920, 0.9503041]])
    xyz = lin @ M.T
    wp = np.array([0.95047, 1.0, 1.08883])
    t = xyz / wp
    eps = 216.0 / 24389.0
    kap = 24389.0 / 27.0
    ft = np.where(t > eps, np.cbrt(t), (kap * t + 16.0) / 116.0)
    L = 116.0 * ft[..., 1] - 16.0
    a = 500.0 * (ft[..., 0] - ft[..., 1])
    b = 200.0 * (ft[..., 1] - ft[..., 2])
    return np.stack([L, a, b], axis=-1)


# Piecewise-linear approximation of the viridis colormap.
_VIRIDIS = (
    (0.267, 0.005, 0.329), (0.283, 0.141, 0.458), (0.254, 0.265, 0.530),
    (0.207, 0.372, 0.553), (0.164, 0.471, 0.558), (0.128, 0.567, 0.551),
    (0.135, 0.659, 0.518), (0.267, 0.749, 0.441), (0.478, 0.821, 0.318),
    (0.741, 0.873, 0.150), (0.993, 0.906, 0.144),
)


def _viridis(values):
    """values in [0,1] (2-D) -> float RGB (0-255) array."""
    np = _np()
    stops = np.asarray(_VIRIDIS)
    v = np.clip(values, 0.0, 1.0) * (len(stops) - 1)
    lo = np.floor(v).astype(int)
    hi = np.minimum(lo + 1, len(stops) - 1)
    frac = (v - lo)[..., None]
    rgb = stops[lo] * (1.0 - frac) + stops[hi] * frac
    return rgb * 255.0


# ------------------------------------------------------------------ public

def compare_images(ref_png, candidate_png, tile=64, dpi=96.0,
                   heatmap_png=None, overlay_png=None):
    """Compare a candidate render against a reference render.

    Parameters:
        ref_png (str): reference PNG path (defines the target geometry).
        candidate_png (str): candidate PNG path.  If its dimensions
            differ from the reference by <= 2% per axis it is resized
            (Lanczos) to the reference dims; a larger mismatch raises.
        tile (int): tile size in reference pixels for discrepancy
            localization (default 64).
        dpi (float): resolution of the reference render; used to express
            region bboxes in points (default 96.0).
        heatmap_png (str|None): output path for the SSIM heatmap
            (default: ``<candidate stem>_heatmap.png`` next to the
            candidate).
        overlay_png (str|None): output path for the magenta(ref) /
            green(candidate) alignment overlay (default:
            ``<candidate stem>_overlay.png``).

    Returns:
        dict:
            reference: {path, width_px, height_px}
            candidate: {path, width_px, height_px, resized (bool)}
            dpi (float), tile_size (int)
            metrics:
                pixel_mae (float): mean |ref-cand| over RGB, 0-255 scale
                rmse (float): root-mean-square error, 0-255 scale
                ssim (float): mean SSIM (11x11 gaussian, K1=.01, K2=.03)
                edge_similarity (float): F1 between thresholded Sobel
                    edge maps (1.0 when both images have no edges)
                color_delta (float): mean CIE76 Lab distance
            largest_differences: up to 10 regions, ranked by mean
                (1 - SSIM), each:
                {rank (int, 1-based),
                 bbox_px [x1,y1,x2,y2] (reference pixels),
                 bbox_pt [x1,y1,x2,y2] (points, = px * 72/dpi),
                 score (float, mean 1-SSIM in tile),
                 severity ("high" > 0.5 >= "med" > 0.2 >= "low"),
                 color_delta (float, tile mean CIE76),
                 edge_density (float, union edge fraction in tile),
                 probable_type ("color" if edge maps agree but colour
                     differs; "text" if edge density > 0.14; else
                     "geometry")}
            artifacts: {heatmap_png, overlay_png} (paths written)

    Raises:
        FileNotFoundError: an input PNG is missing.
        ValueError: dimension mismatch exceeds 2% per axis, or tile <= 0.
        ImportError: missing optional dependency.
    """
    np = _np()
    Image = require("PIL.Image")
    for p in (ref_png, candidate_png):
        if not os.path.isfile(p):
            raise FileNotFoundError("image not found: %s" % p)
    if tile <= 0:
        raise ValueError("tile must be a positive integer, got %r" % (tile,))

    ref = _load_rgb(ref_png)
    cand = _load_rgb(candidate_png)
    rh, rw = ref.shape[:2]
    ch, cw = cand.shape[:2]
    resized = False
    if (ch, cw) != (rh, rw):
        if abs(ch - rh) / float(rh) <= 0.02 and \
           abs(cw - rw) / float(rw) <= 0.02:
            with Image.open(candidate_png) as im:
                cand = np.asarray(
                    im.convert("RGB").resize((rw, rh), Image.LANCZOS),
                    dtype=np.float64)
            resized = True
        else:
            raise ValueError(
                "candidate dimensions %dx%d differ from reference %dx%d "
                "by more than 2%%; render both at the same dpi"
                % (cw, ch, rw, rh))

    # ---- global metrics
    diff = ref - cand
    pixel_mae = float(np.abs(diff).mean())
    rmse = float(math.sqrt((diff * diff).mean()))
    g_ref, g_cand = _gray(ref), _gray(cand)
    ssim_map = _ssim_map(g_ref, g_cand)
    ssim = float(ssim_map.mean())
    e_ref, e_cand = _edge_map(g_ref), _edge_map(g_cand)
    edge_similarity = _edge_f1(e_ref, e_cand)
    de = np.sqrt(((_rgb_to_lab(ref) - _rgb_to_lab(cand)) ** 2).sum(axis=-1))
    color_delta = float(de.mean())

    # ---- per-tile localization
    ny = (rh + tile - 1) // tile
    nx = (rw + tile - 1) // tile
    inv = 1.0 - ssim_map
    edge_union = np.logical_or(e_ref, e_cand)
    edge_xor = np.logical_xor(e_ref, e_cand)
    tile_vals = np.zeros((ny, nx), dtype=np.float64)
    tile_type = [[None] * nx for _ in range(ny)]
    tile_de = np.zeros((ny, nx), dtype=np.float64)
    for ty in range(ny):
        for tx in range(nx):
            y1, x1 = ty * tile, tx * tile
            y2, x2 = min(y1 + tile, rh), min(x1 + tile, rw)
            inv_mean = float(inv[y1:y2, x1:x2].mean())
            t_de = float(de[y1:y2, x1:x2].mean())
            tile_de[ty, tx] = t_de
            tile_vals[ty, tx] = max(inv_mean,
                                    min(t_de / COLOR_DELTA_NORM, 1.0))
            if inv_mean <= REGION_FLOOR and t_de <= COLOR_REGION_MIN:
                continue
            t_edge = float(edge_union[y1:y2, x1:x2].mean())
            t_xor = float(edge_xor[y1:y2, x1:x2].mean())
            if t_xor < COLOR_EDGE_XOR_MAX and t_de > COLOR_DELTA_MIN:
                tile_type[ty][tx] = "color"
            elif t_edge > TEXT_EDGE_DENSITY:
                tile_type[ty][tx] = "text"
            else:
                tile_type[ty][tx] = "geometry"

    # Merge 8-connected flagged tiles OF THE SAME PROBABLE TYPE into single
    # regions: one moved object becomes one actionable region, while adjacent
    # discrepancies of different kinds (a recolour beside a text edit) stay
    # separate.
    regions = []
    seen = [[False] * nx for _ in range(ny)]
    for ty in range(ny):
        for tx in range(nx):
            ptype = tile_type[ty][tx]
            if ptype is None or seen[ty][tx]:
                continue
            stack = [(ty, tx)]
            seen[ty][tx] = True
            members = []
            while stack:
                cy, cx = stack.pop()
                members.append((cy, cx))
                for dy in (-1, 0, 1):
                    for dx in (-1, 0, 1):
                        my, mx = cy + dy, cx + dx
                        if 0 <= my < ny and 0 <= mx < nx and \
                                not seen[my][mx] and \
                                tile_type[my][mx] == ptype:
                            seen[my][mx] = True
                            stack.append((my, mx))
            tys = [m[0] for m in members]
            txs = [m[1] for m in members]
            y1, x1 = min(tys) * tile, min(txs) * tile
            y2 = min((max(tys) + 1) * tile, rh)
            x2 = min((max(txs) + 1) * tile, rw)
            score = float(max(tile_vals[m] for m in members))
            t_de = float(max(tile_de[m] for m in members))
            t_edge = float(edge_union[y1:y2, x1:x2].mean())
            severity = ("high" if score > SEVERITY_HIGH
                        else "med" if score > SEVERITY_MED else "low")
            sc = 72.0 / float(dpi)
            regions.append({
                "bbox_px": [int(x1), int(y1), int(x2), int(y2)],
                "bbox_pt": [round(x1 * sc, 2), round(y1 * sc, 2),
                            round(x2 * sc, 2), round(y2 * sc, 2)],
                "tiles": len(members),
                "score": round(score, 4),
                "severity": severity,
                "color_delta": round(t_de, 2),
                "edge_density": round(t_edge, 4),
                "probable_type": ptype,
            })
    regions.sort(key=lambda r: (-r["score"],
                                r["bbox_px"][1], r["bbox_px"][0]))
    regions = regions[:MAX_REGIONS]
    for i, r in enumerate(regions):
        r["rank"] = i + 1

    # ---- artifacts
    stem = os.path.splitext(candidate_png)[0]
    if heatmap_png is None:
        heatmap_png = stem + "_heatmap.png"
    if overlay_png is None:
        overlay_png = stem + "_overlay.png"

    vmax = float(tile_vals.max())
    norm = tile_vals / vmax if vmax > 0 else tile_vals
    color_tiles = _viridis(norm)
    full = np.kron(color_tiles,
                   np.ones((tile, tile, 1)))[:rh, :rw, :]
    alpha = np.kron(np.clip(tile_vals, 0.0, 1.0),
                    np.ones((tile, tile)))[:rh, :rw]
    alpha = np.clip(0.15 + 0.6 * (alpha / vmax if vmax > 0 else alpha),
                    0.0, 0.75)[..., None]
    heat = ref * (1.0 - alpha) + full * alpha
    Image.fromarray(np.clip(heat, 0, 255).astype("uint8")).save(heatmap_png)

    ink_ref = 255.0 - g_ref
    ink_cand = 255.0 - g_cand
    ov = np.empty((rh, rw, 3), dtype=np.float64)
    ov[..., 0] = 255.0 - ink_cand   # candidate ink removes red+blue = green
    ov[..., 1] = 255.0 - ink_ref    # reference ink removes green = magenta
    ov[..., 2] = 255.0 - ink_cand
    Image.fromarray(np.clip(ov, 0, 255).astype("uint8")).save(overlay_png)

    return {
        "reference": {"path": ref_png, "width_px": int(rw),
                      "height_px": int(rh)},
        "candidate": {"path": candidate_png, "width_px": int(cw),
                      "height_px": int(ch), "resized": resized},
        "dpi": float(dpi),
        "tile_size": int(tile),
        "metrics": {
            "pixel_mae": round(pixel_mae, 4),
            "rmse": round(rmse, 4),
            "ssim": round(ssim, 6),
            "edge_similarity": round(edge_similarity, 6),
            "color_delta": round(color_delta, 4),
        },
        "largest_differences": regions,
        "artifacts": {"heatmap_png": heatmap_png,
                      "overlay_png": overlay_png},
    }


def map_regions_to_objects(regions, objects_json, dpi=96.0):
    """Map discrepancy regions to Illustrator item descriptors.

    Parameters:
        regions (list[dict]): regions as produced by ``compare_images``
            (``largest_differences``).  Each needs ``bbox_pt`` (points),
            or ``bbox_px`` which is converted using ``dpi``.
        objects_json (list|dict): item descriptors with bounds in POINTS,
            the CLI's items_list shape:
            ``{name, uuid, type, bounds: {x, y, w, h}}``.  A dict input
            uses its ``items`` (or ``results``) list.  Items without
            bounds are skipped.
        dpi (float): used only to convert ``bbox_px`` -> points when a
            region lacks ``bbox_pt`` (default 96.0).

    Returns:
        list[dict], one entry per input region (same order):
            {region_index (int, 0-based),
             bbox_pt [x1,y1,x2,y2],
             probable_type (str|None, copied from region),
             candidates: [{uuid, name, type,
                           overlap_fraction (float, intersection area /
                           region area, 0-1)}]
             ranked by overlap_fraction desc (ties: larger item area
             last, then name), max 5, overlap > 0 only}

    Raises:
        ValueError: a region has neither bbox_pt nor bbox_px.
    """
    if isinstance(objects_json, dict):
        items = objects_json.get("items") or objects_json.get("results") or []
    else:
        items = list(objects_json or [])

    out = []
    s = 72.0 / float(dpi)
    for idx, region in enumerate(regions or []):
        bbox = region.get("bbox_pt")
        if bbox is None:
            px = region.get("bbox_px")
            if px is None:
                raise ValueError(
                    "region %d has neither bbox_pt nor bbox_px" % idx)
            bbox = [v * s for v in px]
        rx1, ry1, rx2, ry2 = [float(v) for v in bbox]
        r_area = max(rx2 - rx1, 0.0) * max(ry2 - ry1, 0.0)
        cands = []
        for it in items:
            b = it.get("bounds") if isinstance(it, dict) else None
            if not b:
                continue
            ox1, oy1 = float(b["x"]), float(b["y"])
            ox2, oy2 = ox1 + float(b["w"]), oy1 + float(b["h"])
            ix = max(0.0, min(rx2, ox2) - max(rx1, ox1))
            iy = max(0.0, min(ry2, oy2) - max(ry1, oy1))
            inter = ix * iy
            if inter <= 0.0 or r_area <= 0.0:
                continue
            cands.append({
                "uuid": it.get("uuid"),
                "name": it.get("name", ""),
                "type": it.get("type"),
                "overlap_fraction": round(inter / r_area, 4),
                "_area": (ox2 - ox1) * (oy2 - oy1),
            })
        cands.sort(key=lambda c: (-c["overlap_fraction"], c["_area"],
                                  c["name"] or ""))
        for c in cands:
            del c["_area"]
        out.append({
            "region_index": idx,
            "bbox_pt": [round(float(v), 2) for v in bbox],
            "probable_type": region.get("probable_type"),
            "candidates": cands[:5],
        })
    return out
