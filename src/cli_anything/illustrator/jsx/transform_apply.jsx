// Geometric transform on selector-matched items: scale (percent, x/y),
// rotate (degrees, counter-clockwise, Illustrator convention), translate
// (canvas dx/dy, y down). Applied in that order. `about` picks the anchor
// for scale/rotate: center (default) or topleft. `preserve_strokes` keeps
// stroke weights unscaled.
(function () {
    try {
        var P = CAI.parse(__PARAMS_JSON);
        var doc = CAI.resolveDoc(P);
        var ab = P.artboard || 0;
        var items = CAI.requireItems(doc, P.selector || {}, !!P.allow_multiple);
        var aboutStr = String(P.about || "center").toLowerCase();
        if (aboutStr !== "center" && aboutStr !== "topleft")
            throw CAI.err("BAD_PARAMS", "about must be center|topleft: " + aboutStr);
        var about = (aboutStr === "topleft") ? Transformation.TOPLEFT : Transformation.CENTER;
        var sx = (P.scale_x === undefined || P.scale_x === null) ? null : P.scale_x;
        var sy = (P.scale_y === undefined || P.scale_y === null) ? sx : P.scale_y;
        if (sx === null && sy !== null) sx = 100;
        var results = [];
        for (var i = 0; i < items.length; i++) {
            var it = items[i];
            var before = CAI.describeItem(doc, ab, it);
            if (sx !== null && (sx !== 100 || sy !== 100)) {
                var lw = P.preserve_strokes ? 100 : (sx + sy) / 2;
                it.resize(sx, sy, true, true, true, true, lw, about);
            }
            if (P.rotate) it.rotate(P.rotate, true, true, true, true, about);
            if (P.dx || P.dy) it.translate(P.dx || 0, -(P.dy || 0));
            results.push({ before: before, after: CAI.describeItem(doc, ab, it) });
        }
        return CAI.ok({ updated: results.length, items: results });
    } catch (e) { return CAI.failFromException(e); }
})();
