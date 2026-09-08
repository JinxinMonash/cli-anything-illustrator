(function () {
    try {
        var P = CAI.parse(__PARAMS_JSON);
        var doc = CAI.resolveDoc(P);
        var ab = P.artboard || 0;
        var it;
        if (P.kind === "rect") {
            var tl = CAI.toAI(doc, ab, P.x, P.y);
            if (P.corner_radius && P.corner_radius > 0)
                it = doc.pathItems.roundedRectangle(tl[1], tl[0], P.w, P.h,
                                                    P.corner_radius, P.corner_radius);
            else
                it = doc.pathItems.rectangle(tl[1], tl[0], P.w, P.h);
        } else if (P.kind === "ellipse") {
            var tle = CAI.toAI(doc, ab, P.x, P.y);
            it = doc.pathItems.ellipse(tle[1], tle[0], P.w, P.h);
        } else if (P.kind === "line") {
            var p1 = CAI.toAI(doc, ab, P.x1, P.y1);
            var p2 = CAI.toAI(doc, ab, P.x2, P.y2);
            it = doc.pathItems.add();
            it.setEntirePath([p1, p2]);
            it.filled = false;
        } else if (P.kind === "polygon") {
            var cp = CAI.toAI(doc, ab, P.cx, P.cy);
            it = doc.pathItems.polygon(cp[0], cp[1], P.radius, P.sides);
        } else if (P.kind === "star") {
            var cs = CAI.toAI(doc, ab, P.cx, P.cy);
            it = doc.pathItems.star(cs[0], cs[1], P.radius, P.inner_radius, P.points);
        } else {
            throw CAI.err("BAD_PARAMS", "Unknown shape kind: " + P.kind);
        }
        if (P.fill) { it.fillColor = CAI.rgb(P.fill); it.filled = true; }
        else if (P.kind !== "line" && P.fill === null) { it.filled = false; }
        if (P.stroke) {
            it.strokeColor = CAI.rgb(P.stroke);
            it.stroked = true;
            if (P.stroke_width) it.strokeWidth = P.stroke_width;
        } else if (P.stroke === null) { it.stroked = false; }
        if (P.name) it.name = String(P.name);
        if (P.layer) {
            var layer = CAI.getLayer(doc, P.layer, !!P.layer_create);
            it.move(layer, ElementPlacement.PLACEATBEGINNING);
        }
        return CAI.ok(CAI.describeItem(doc, ab, it));
    } catch (e) { return CAI.failFromException(e); }
})();
