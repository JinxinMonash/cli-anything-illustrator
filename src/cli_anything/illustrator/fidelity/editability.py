"""Structural editability scoring.

``score_editability(doc_report)`` consumes the JSON produced by the CLI's
``doc report`` operation (jsx/doc_report.jsx) and returns a structural
editability report with a PASS/WARN/FAIL status.  Stdlib-only.

The doc-report shape handled (all keys optional; absence handled
gracefully):
    text_frames (int), raster_items (int), placed_items (int),
    page_items (int), layers (int), legacy_text_items (int),
    compound_paths (int), clipping_paths (int),
    fonts_used [{font, text_frames, available_in_app}],
    fonts_unavailable [str], placed_links [{name, missing, file}],
    locked_layers [str], hidden_layers [str],
    editability (optional counts block, e.g. {path_items, gradients,
        clipping_groups, rasterized_regions, live_text, vector_objects})
"""


def _num(*values):
    """First value that is a real number; else None."""
    for v in values:
        if isinstance(v, bool):
            continue
        if isinstance(v, (int, float)):
            return int(v)
    return None


def score_editability(doc_report):
    """Score the structural editability of an Illustrator document.

    Parameters:
        doc_report (dict): output of the CLI ``doc report`` operation
            (see module docstring).  An optional ``editability`` counts
            block, when present, takes precedence for the counts it
            carries; every field may be absent.

    Returns:
        dict:
            live_text (int|None): live (non-legacy) text frames
            text_objects (int|None): live + legacy text objects
            vector_objects (int|None): editable vector items (from
                editability.vector_objects/path_items when present, else
                page_items - text_frames - raster_items - placed_items,
                floored at 0; None when underivable)
            rasterized_regions (int|None): raster items (+ editability
                block value when present)
            gradients (int|None): None when the report carries no count
            layers (dict): {count (int|None), locked [str], hidden [str]}
            clipping_groups (int|None)
            editability_status (str): "PASS" | "WARN" | "FAIL"
            reasons (list[str]): human-readable justifications for every
                WARN/FAIL contribution (empty for a clean PASS)

    Status logic:
        FAIL  - no editable content at all (live_text == 0 and
                vector_objects == 0 and legacy == 0 and text/vector counts
                are known), or document has 0 page items, or ALL text is
                legacy (text exists but none is live).
        WARN  - rasterized regions present; unavailable fonts; legacy
                text alongside live text; missing placed links; locked or
                hidden layers; or an empty/unparseable report.
        PASS  - otherwise.
    """
    rep = dict(doc_report or {})
    ed = rep.get("editability") or {}

    live_text = _num(ed.get("live_text"), ed.get("text_frames"),
                     rep.get("text_frames"))
    legacy = _num(rep.get("legacy_text_items"), ed.get("legacy_text_items"))
    text_objects = None
    if live_text is not None:
        text_objects = live_text + (legacy or 0)

    raster = _num(ed.get("rasterized_regions"), ed.get("raster_items"),
                  rep.get("raster_items"))
    placed = _num(rep.get("placed_items"))
    if placed is None:
        links = rep.get("placed_links")
        placed = len(links) if isinstance(links, list) else None
    page_items = _num(rep.get("page_items"))

    vector_objects = _num(ed.get("vector_objects"), ed.get("path_items"))
    if vector_objects is None and page_items is not None:
        vector_objects = max(
            page_items - (live_text or 0) - (legacy or 0)
            - (raster or 0) - (placed or 0), 0)

    gradients = _num(ed.get("gradients"))
    clipping = _num(ed.get("clipping_groups"), rep.get("clipping_paths"))

    layers_count = _num(rep.get("layers"), ed.get("layers"))
    locked = rep.get("locked_layers") or []
    hidden = rep.get("hidden_layers") or []

    fonts_unavailable = rep.get("fonts_unavailable") or []
    links = rep.get("placed_links") or []
    missing_links = [l.get("name") or "(unnamed)" for l in links
                     if isinstance(l, dict) and l.get("missing")]

    reasons = []
    status = ["PASS"]
    _RANK = {"PASS": 0, "WARN": 1, "FAIL": 2}

    def raise_to(level, msg):
        reasons.append("%s: %s" % (level, msg))
        if _RANK[level] > _RANK[status[0]]:
            status[0] = level

    if not rep:
        raise_to("WARN", "empty document report; nothing to score")
    else:
        known = (live_text is not None and vector_objects is not None)
        if page_items == 0:
            raise_to("FAIL", "document contains no page items")
        elif known and live_text == 0 and vector_objects == 0 \
                and (legacy or 0) == 0:
            raise_to("FAIL",
                     "no live text and no vector objects: content is not "
                     "editable" + (" (raster only)" if (raster or 0) > 0
                                   else ""))
        elif (legacy or 0) > 0 and (live_text or 0) == 0:
            raise_to("FAIL",
                     "all %d text object(s) are legacy text; convert to "
                     "live text to edit" % legacy)
        elif (legacy or 0) > 0:
            raise_to("WARN",
                     "%d legacy text item(s) are not editable until "
                     "converted" % legacy)
        if not known and page_items is None and rep:
            raise_to("WARN",
                     "report lacks item counts; editability could not be "
                     "fully assessed")
        if (raster or 0) > 0:
            raise_to("WARN",
                     "%d rasterized region(s): pixels, not editable "
                     "vectors" % raster)
        if fonts_unavailable:
            raise_to("WARN",
                     "fonts unavailable on this system: %s"
                     % ", ".join(str(f) for f in fonts_unavailable))
        if missing_links:
            raise_to("WARN",
                     "placed item(s) with missing links: %s"
                     % ", ".join(missing_links))
        if locked:
            raise_to("WARN", "locked layer(s): %s"
                     % ", ".join(str(x) for x in locked))
        if hidden:
            raise_to("WARN", "hidden layer(s): %s"
                     % ", ".join(str(x) for x in hidden))

    return {
        "live_text": live_text,
        "text_objects": text_objects,
        "vector_objects": vector_objects,
        "rasterized_regions": raster,
        "gradients": gradients,
        "layers": {"count": layers_count,
                   "locked": list(locked), "hidden": list(hidden)},
        "clipping_groups": clipping,
        "editability_status": status[0],
        "reasons": reasons,
    }
