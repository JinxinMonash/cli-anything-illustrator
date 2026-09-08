// Non-destructive item updates: rename, absolute/relative move, uniform scale
// (aspect ratio always preserved; strokes scaled proportionally), z-order.
(function () {
    try {
        var P = CAI.parse(__PARAMS_JSON);
        var doc = CAI.resolveDoc(P);
        var ab = P.artboard || 0;
        var items = CAI.requireItems(doc, P.selector || {}, !!P.allow_multiple);
        var U = P.updates || {};
        var results = [];
        for (var i = 0; i < items.length; i++) {
            var it = items[i];
            var before = CAI.describeItem(doc, ab, it);
            if (U.new_name) it.name = String(U.new_name);
            if (U.scale_percent && U.scale_percent !== 100) {
                it.resize(U.scale_percent, U.scale_percent,
                          true, true, true, true, U.scale_percent,
                          Transformation.TOPLEFT);
            }
            if (U.x !== undefined && U.x !== null && U.y !== undefined && U.y !== null) {
                var b = it.visibleBounds; // [L, T, R, B]
                var target = CAI.toAI(doc, ab, U.x, U.y);
                it.translate(target[0] - b[0], target[1] - b[1]);
            } else if (U.dx || U.dy) {
                it.translate(U.dx || 0, -(U.dy || 0));
            }
            if (U.zorder === "front") it.zOrder(ZOrderMethod.BRINGTOFRONT);
            else if (U.zorder === "back") it.zOrder(ZOrderMethod.SENDTOBACK);
            if (U.opacity !== undefined && U.opacity !== null) it.opacity = U.opacity;
            results.push({ before: before, after: CAI.describeItem(doc, ab, it) });
        }
        return CAI.ok({ updated: results.length, items: results });
    } catch (e) { return CAI.failFromException(e); }
})();
