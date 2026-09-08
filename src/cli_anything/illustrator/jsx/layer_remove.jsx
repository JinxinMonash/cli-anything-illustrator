(function () {
    try {
        var P = CAI.parse(__PARAMS_JSON);
        var doc = CAI.resolveDoc(P);
        var ly = CAI.getLayer(doc, P.name, false);
        var n = ly.pageItems.length;
        if (n > 0 && !P.force)
            throw CAI.err("LAYER_NOT_EMPTY",
                "Layer '" + P.name + "' contains " + n + " item(s); pass --force to delete anyway.");
        ly.locked = false;
        ly.remove();
        return CAI.ok({ removed: P.name, items_deleted: n, layer_count: doc.layers.length });
    } catch (e) { return CAI.failFromException(e); }
})();
