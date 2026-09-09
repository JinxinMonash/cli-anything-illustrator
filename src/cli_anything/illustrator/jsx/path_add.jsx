// Add an arbitrary Bezier path from canvas-coordinate anchors and optional
// per-anchor left/right handles (absolute canvas coordinates; null/omitted
// handle = coincident with the anchor).
(function () {
    try {
        var P = CAI.parse(__PARAMS_JSON);
        var doc = CAI.resolveDoc(P);
        var ab = P.artboard || 0;
        var anchors = P.anchors;
        if (!anchors || anchors.length < 2)
            throw CAI.err("BAD_PARAMS", "anchors must contain at least 2 [x,y] pairs.");
        var pts = [];
        var i;
        for (i = 0; i < anchors.length; i++) {
            if (!anchors[i] || anchors[i].length < 2)
                throw CAI.err("BAD_PARAMS", "anchors[" + i + "] must be an [x,y] pair.");
            pts.push(CAI.toAI(doc, ab, anchors[i][0], anchors[i][1]));
        }
        var it = doc.pathItems.add();
        it.setEntirePath(pts);
        it.closed = !!P.closed;
        for (i = 0; i < it.pathPoints.length; i++) {
            var pp = it.pathPoints[i];
            var lh = (P.left_handles && P.left_handles[i])
                ? CAI.toAI(doc, ab, P.left_handles[i][0], P.left_handles[i][1]) : null;
            var rh = (P.right_handles && P.right_handles[i])
                ? CAI.toAI(doc, ab, P.right_handles[i][0], P.right_handles[i][1]) : null;
            pp.leftDirection = lh ? lh : [pts[i][0], pts[i][1]];
            pp.rightDirection = rh ? rh : [pts[i][0], pts[i][1]];
            pp.pointType = (lh && rh) ? PointType.SMOOTH : PointType.CORNER;
        }
        if (P.fill) { it.fillColor = CAI.rgb(P.fill); it.filled = true; }
        else { it.filled = false; }
        if (P.stroke) {
            it.strokeColor = CAI.rgb(P.stroke);
            it.stroked = true;
            if (P.stroke_width) it.strokeWidth = P.stroke_width;
        } else { it.stroked = false; }
        if (P.name) it.name = String(P.name);
        if (P.layer) {
            var layer = CAI.getLayer(doc, P.layer, !!P.layer_create);
            it.move(layer, ElementPlacement.PLACEATBEGINNING);
        }
        return CAI.ok(CAI.describePathDeep(doc, ab, it, P.limit));
    } catch (e) { return CAI.failFromException(e); }
})();
