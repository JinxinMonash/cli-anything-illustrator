// Stroke/fill styling on selector-matched items. Path-level properties are
// applied to every path reachable from each match (groups/compounds descend);
// a fill colour also applies to matched text frames; opacity applies to the
// matched item itself.
(function () {
    try {
        var P = CAI.parse(__PARAMS_JSON);
        var doc = CAI.resolveDoc(P);
        var ab = P.artboard || 0;
        var items = CAI.requireItems(doc, P.selector || {}, !!P.allow_multiple);
        var capV = (P.cap !== undefined && P.cap !== null) ? CAI.strokeCapFrom(P.cap) : null;
        var joinV = (P.join !== undefined && P.join !== null) ? CAI.strokeJoinFrom(P.join) : null;
        var results = [];
        for (var i = 0; i < items.length; i++) {
            var it = items[i];
            if (P.opacity !== undefined && P.opacity !== null) it.opacity = P.opacity;
            if (P.fill && CAI.typeName(it) === "text" && String(P.fill) !== "none") {
                it.textRange.characterAttributes.fillColor = CAI.rgb(P.fill);
            }
            var paths = CAI.collectPaths(it, []);
            for (var j = 0; j < paths.length; j++) {
                var p = paths[j];
                if (P.fill !== undefined && P.fill !== null) {
                    if (String(P.fill) === "none") p.filled = false;
                    else { p.fillColor = CAI.rgb(P.fill); p.filled = true; }
                }
                if (P.stroke !== undefined && P.stroke !== null) {
                    if (String(P.stroke) === "none") p.stroked = false;
                    else { p.strokeColor = CAI.rgb(P.stroke); p.stroked = true; }
                }
                if (P.stroke_width !== undefined && P.stroke_width !== null)
                    p.strokeWidth = P.stroke_width;
                if (capV !== null) p.strokeCap = capV;
                if (joinV !== null) p.strokeJoin = joinV;
                if (P.miter_limit !== undefined && P.miter_limit !== null)
                    p.strokeMiterLimit = P.miter_limit;
                if (P.dash !== undefined && P.dash !== null) p.strokeDashes = P.dash;
                if (P.dash_offset !== undefined && P.dash_offset !== null)
                    p.strokeDashOffset = P.dash_offset;
            }
            var d = CAI.describeItem(doc, ab, it);
            d.paths_styled = paths.length;
            results.push(d);
        }
        return CAI.ok({ updated: results.length, items: results });
    } catch (e) { return CAI.failFromException(e); }
})();
