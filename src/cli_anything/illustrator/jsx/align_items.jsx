// Align or distribute items. mode: left|hcenter|right|top|vcenter|bottom|
// hdist|vdist. reference: "artboard" or "selection" bounding box.
(function () {
    try {
        var P = CAI.parse(__PARAMS_JSON);
        var doc = CAI.resolveDoc(P);
        var ab = P.artboard || 0;
        var items = CAI.requireItems(doc, P.selector || {}, true);
        var mode = String(P.mode);
        var isDist = (mode === "hdist" || mode === "vdist");
        if (items.length < 2 && (isDist || P.reference === "selection"))
            throw CAI.err("BAD_PARAMS", "Need at least 2 matched items for " + mode +
                          " with reference=selection.");

        // reference box in AI coords [L, T, R, B]
        var ref;
        if (P.reference === "artboard") {
            ref = CAI.abRect(doc, ab);
        } else {
            var b0 = items[0].visibleBounds;
            ref = [b0[0], b0[1], b0[2], b0[3]];
            for (var i = 1; i < items.length; i++) {
                var b = items[i].visibleBounds;
                if (b[0] < ref[0]) ref[0] = b[0];
                if (b[1] > ref[1]) ref[1] = b[1];
                if (b[2] > ref[2]) ref[2] = b[2];
                if (b[3] < ref[3]) ref[3] = b[3];
            }
        }

        var moved = [];
        if (!isDist) {
            for (var j = 0; j < items.length; j++) {
                var it = items[j];
                var vb = it.visibleBounds;
                var dx = 0, dy = 0;
                if (mode === "left") dx = ref[0] - vb[0];
                else if (mode === "right") dx = ref[2] - vb[2];
                else if (mode === "hcenter") dx = (ref[0] + ref[2]) / 2 - (vb[0] + vb[2]) / 2;
                else if (mode === "top") dy = ref[1] - vb[1];
                else if (mode === "bottom") dy = ref[3] - vb[3];
                else if (mode === "vcenter") dy = (ref[1] + ref[3]) / 2 - (vb[1] + vb[3]) / 2;
                else throw CAI.err("BAD_PARAMS", "Unknown align mode: " + mode);
                it.translate(dx, dy);
                moved.push(CAI.describeItem(doc, ab, it));
            }
        } else {
            // sort by leading edge, then distribute with equal gaps in the ref span
            var arr = [];
            var total = 0;
            for (var k = 0; k < items.length; k++) {
                var bb = items[k].visibleBounds;
                var size = (mode === "hdist") ? (bb[2] - bb[0]) : (bb[1] - bb[3]);
                arr.push({ item: items[k], b: bb, size: size });
                total += size;
            }
            arr.sort(function (a, c) {
                return (mode === "hdist") ? (a.b[0] - c.b[0]) : (c.b[1] - a.b[1]);
            });
            var span = (mode === "hdist") ? (ref[2] - ref[0]) : (ref[1] - ref[3]);
            var gap = (span - total) / (arr.length - 1);
            var cursor = (mode === "hdist") ? ref[0] : ref[1];
            for (var m = 0; m < arr.length; m++) {
                var e2 = arr[m];
                if (mode === "hdist") {
                    e2.item.translate(cursor - e2.b[0], 0);
                    cursor += e2.size + gap;
                } else {
                    e2.item.translate(0, cursor - e2.b[1]);
                    cursor -= (e2.size + gap);
                }
                moved.push(CAI.describeItem(doc, ab, e2.item));
            }
        }
        return CAI.ok({ mode: mode, reference: P.reference || "selection",
                        moved: moved.length, items: moved });
    } catch (e) { return CAI.failFromException(e); }
})();
