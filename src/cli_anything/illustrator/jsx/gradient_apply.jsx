// Apply a named document gradient to selector-matched items as a
// GradientColor (fill by default, or stroke), with angle and optional
// origin (canvas coords) / length.
(function () {
    try {
        var P = CAI.parse(__PARAMS_JSON);
        var doc = CAI.resolveDoc(P);
        var ab = P.artboard || 0;
        if (!P.gradient) throw CAI.err("BAD_PARAMS", "gradient (name) is required.");
        var g = CAI.getGradient(doc, P.gradient);
        var items = CAI.requireItems(doc, P.selector || {}, !!P.allow_multiple);
        var target = (String(P.target).toLowerCase() === "stroke") ? "stroke" : "fill";
        var angle = (P.angle === undefined || P.angle === null) ? 0 : P.angle;
        var results = [];
        for (var i = 0; i < items.length; i++) {
            var paths = CAI.collectPaths(items[i], []);
            if (paths.length === 0)
                throw CAI.err("BAD_PARAMS", "Selector matched an item with no paintable paths: " +
                              CAI.typeName(items[i]));
            for (var j = 0; j < paths.length; j++) {
                var gc = new GradientColor();
                gc.gradient = g;
                gc.angle = angle;
                if (P.origin) gc.origin = CAI.toAI(doc, ab, P.origin[0], P.origin[1]);
                if (P.length !== undefined && P.length !== null) gc.length = P.length;
                if (target === "fill") { paths[j].fillColor = gc; paths[j].filled = true; }
                else { paths[j].strokeColor = gc; paths[j].stroked = true; }
            }
            var d = CAI.describeItem(doc, ab, items[i]);
            d.paths_painted = paths.length;
            results.push(d);
        }
        return CAI.ok({ gradient: String(g.name), target: target, angle: angle,
                        origin: P.origin || null,
                        length: (P.length === undefined) ? null : P.length,
                        updated: results.length, items: results });
    } catch (e) { return CAI.failFromException(e); }
})();
