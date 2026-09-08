(function () {
    try {
        var P = CAI.parse(__PARAMS_JSON);
        var doc = CAI.resolveDoc(P);
        var ab = P.artboard || 0;
        var items = CAI.requireItems(doc, P.selector || {}, true);
        var layer = P.layer ? CAI.getLayer(doc, P.layer, !!P.layer_create)
                            : items[0].layer;
        var grp = layer.groupItems.add();
        if (P.name) grp.name = String(P.name);
        // move() re-parents without changing geometry
        for (var i = 0; i < items.length; i++) {
            items[i].move(grp, ElementPlacement.PLACEATEND);
        }
        var desc = CAI.describeItem(doc, ab, grp);
        desc.member_count = grp.pageItems.length;
        return CAI.ok(desc);
    } catch (e) { return CAI.failFromException(e); }
})();
