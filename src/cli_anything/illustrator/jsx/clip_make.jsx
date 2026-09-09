// Clipping mask: group the selector-matched items; the TOPMOST matched item
// (front of stacking order) must be a path/compound path and becomes the
// clipping path.
(function () {
    try {
        var P = CAI.parse(__PARAMS_JSON);
        var doc = CAI.resolveDoc(P);
        var ab = P.artboard || 0;
        var items = CAI.requireItems(doc, P.selector || {}, true);
        if (items.length < 2)
            throw CAI.err("BAD_PARAMS", "clip_make needs at least 2 items (clipping path on top " +
                          "plus content); selector matched " + items.length + ".");
        var top = items[0]; // findItems returns front-to-back order
        var tt = CAI.typeName(top);
        if (tt !== "path" && tt !== "compound")
            throw CAI.err("BAD_PARAMS", "Topmost matched item must be a path or compound path " +
                          "to act as the clipping path (got " + tt + ").");
        var layer = P.layer ? CAI.getLayer(doc, P.layer, !!P.layer_create) : top.layer;
        var grp = layer.groupItems.add();
        if (P.name) grp.name = String(P.name);
        for (var i = 0; i < items.length; i++) {
            items[i].move(grp, ElementPlacement.PLACEATEND);
        }
        grp.clipped = true;
        if (tt === "compound") {
            try { top.clipping = true; } catch (eC) {}
            for (var k = 0; k < top.pathItems.length; k++) top.pathItems[k].clipping = true;
        } else {
            top.clipping = true;
        }
        var desc = CAI.describeItem(doc, ab, grp);
        desc.member_count = grp.pageItems.length;
        desc.clipped = true;
        desc.clip_bounds = CAI.canvasBounds(doc, ab, top.geometricBounds);
        return CAI.ok(desc);
    } catch (e) { return CAI.failFromException(e); }
})();
