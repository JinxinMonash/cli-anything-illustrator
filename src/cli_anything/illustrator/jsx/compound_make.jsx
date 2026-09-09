// Combine selector-matched paths into one CompoundPathItem.
(function () {
    try {
        var P = CAI.parse(__PARAMS_JSON);
        var doc = CAI.resolveDoc(P);
        var ab = P.artboard || 0;
        var items = CAI.requireItems(doc, P.selector || {}, true);
        var paths = [];
        for (var i = 0; i < items.length; i++) {
            if (CAI.typeName(items[i]) === "path") paths.push(items[i]);
        }
        if (paths.length < 2)
            throw CAI.err("BAD_PARAMS", "compound_make needs at least 2 paths; selector matched " +
                          paths.length + " path item(s).");
        var layer = P.layer ? CAI.getLayer(doc, P.layer, !!P.layer_create) : paths[0].layer;
        var cp = layer.compoundPathItems.add();
        if (P.name) cp.name = String(P.name);
        for (var j = 0; j < paths.length; j++) {
            paths[j].move(cp, ElementPlacement.PLACEATEND);
        }
        var desc = CAI.describeItem(doc, ab, cp);
        desc.path_count = cp.pathItems.length;
        return CAI.ok(desc);
    } catch (e) { return CAI.failFromException(e); }
})();
