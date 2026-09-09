// Edit anchors/handles of one existing path, addressed by selector + point
// index. Moving an anchor without giving handles drags its handles along.
(function () {
    try {
        var P = CAI.parse(__PARAMS_JSON);
        var doc = CAI.resolveDoc(P);
        var ab = P.artboard || 0;
        var sel = P.selector || {};
        if (!sel.type) sel.type = "path";
        var items = CAI.requireItems(doc, sel, false);
        var it = items[0];
        if (CAI.typeName(it) !== "path")
            throw CAI.err("BAD_PARAMS", "Selector must resolve to a path item (got " +
                          CAI.typeName(it) + ").");
        if (P.closed !== undefined && P.closed !== null) it.closed = !!P.closed;
        var edits = P.points || [];
        for (var i = 0; i < edits.length; i++) {
            var e0 = edits[i];
            var n = it.pathPoints.length;
            var idx = e0.index;
            if (idx === undefined || idx === null || idx < 0 || idx >= n)
                throw CAI.err("BAD_PARAMS", "Point index out of range: " + idx +
                              " (path has " + n + " anchors).");
            var pp = it.pathPoints[idx];
            if (e0.anchor) {
                var na = CAI.toAI(doc, ab, e0.anchor[0], e0.anchor[1]);
                var oa = pp.anchor;
                var dx = na[0] - oa[0], dy = na[1] - oa[1];
                pp.anchor = na;
                if (!e0.left) {
                    var ol = pp.leftDirection;
                    pp.leftDirection = [ol[0] + dx, ol[1] + dy];
                }
                if (!e0.right) {
                    var orr = pp.rightDirection;
                    pp.rightDirection = [orr[0] + dx, orr[1] + dy];
                }
            }
            if (e0.left) pp.leftDirection = CAI.toAI(doc, ab, e0.left[0], e0.left[1]);
            if (e0.right) pp.rightDirection = CAI.toAI(doc, ab, e0.right[0], e0.right[1]);
            if (e0.point_type) {
                var pt = String(e0.point_type).toLowerCase();
                if (pt !== "smooth" && pt !== "corner")
                    throw CAI.err("BAD_PARAMS", "point_type must be smooth|corner: " + pt);
                pp.pointType = (pt === "smooth") ? PointType.SMOOTH : PointType.CORNER;
            }
        }
        return CAI.ok(CAI.describePathDeep(doc, ab, it, P.limit));
    } catch (e) { return CAI.failFromException(e); }
})();
