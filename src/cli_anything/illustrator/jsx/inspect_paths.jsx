// Deep geometry/style readback for matched paths: closed flag, anchors with
// left/right handles in CANVAS coordinates, paint (incl. gradient name),
// cap/join/dash, opacity. `limit` caps anchors per path; `max_paths` caps
// the number of paths returned.
(function () {
    try {
        var P = CAI.parse(__PARAMS_JSON);
        var doc = CAI.resolveDoc(P);
        var ab = P.artboard || 0;
        var sel = P.selector || {};
        if (!sel.type) sel.type = "path";
        var items = CAI.findItems(doc, sel);
        var maxPaths = P.max_paths || 100;
        var out = [];
        for (var i = 0; i < items.length && i < maxPaths; i++) {
            if (CAI.typeName(items[i]) !== "path") continue;
            out.push(CAI.describePathDeep(doc, ab, items[i], P.limit));
        }
        return CAI.ok({ total_matches: items.length, returned: out.length, paths: out });
    } catch (e) { return CAI.failFromException(e); }
})();
