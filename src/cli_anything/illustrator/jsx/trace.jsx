// Deterministic vector trace of a placed/raster item (Illustrator Image
// Trace), then expansion into editable paths. LIVE ILLUSTRATOR ONLY: the
// portable mock DOM does not model tracing.
(function () {
    try {
        var P = CAI.parse(__PARAMS_JSON);
        var doc = CAI.resolveDoc(P);
        var ab = P.artboard || 0;
        var items = CAI.requireItems(doc, P.selector || {}, false);
        var it = items[0];
        var tn = CAI.typeName(it);
        if (tn === "group") {
            // template import wraps the placed item in a group
            var found = null;
            for (var i = 0; i < it.pageItems.length; i++) {
                var m = CAI.typeName(it.pageItems[i]);
                if (m === "placed" || m === "raster") { found = it.pageItems[i]; break; }
            }
            if (!found) throw CAI.err("BAD_PARAMS",
                "Selector matched a group without placed/raster content.");
            it = found; tn = CAI.typeName(it);
        }
        if (tn !== "placed" && tn !== "raster")
            throw CAI.err("BAD_PARAMS", "Trace needs a placed or raster item, got: " + tn);
        if (tn === "placed") { it = it.embed ? (it.embed(), doc.rasterItems[0]) : it; }
        var plugin = it.trace();
        app.redraw();
        var traced = plugin.tracing.expandTracing();
        if (P.name) traced.name = String(P.name);
        if (P.layer) {
            var ly = CAI.getLayer(doc, P.layer, !!P.layer_create);
            traced.move(ly, ElementPlacement.PLACEATBEGINNING);
        }
        var desc = CAI.describeItem(doc, ab, traced);
        var paths = 0;
        try { paths = traced.pathItems ? traced.pathItems.length : 0; } catch (e) {}
        desc.paths_created = paths;
        return CAI.ok(desc);
    } catch (e) { return CAI.failFromException(e); }
})();
