// Define (or replace) a named document gradient with explicit stops.
(function () {
    try {
        var P = CAI.parse(__PARAMS_JSON);
        var doc = CAI.resolveDoc(P);
        if (!P.name) throw CAI.err("BAD_PARAMS", "Gradient name is required.");
        var stops = P.stops;
        if (!stops || stops.length < 2)
            throw CAI.err("BAD_PARAMS", "A gradient needs at least 2 stops.");
        var i;
        for (i = 0; i < stops.length; i++) {
            var s0 = stops[i];
            if (!s0 || !s0.color || s0.color.length < 3)
                throw CAI.err("BAD_PARAMS", "stops[" + i + "].color must be [r,g,b].");
            if (s0.offset === undefined || s0.offset === null ||
                s0.offset < 0 || s0.offset > 100)
                throw CAI.err("BAD_PARAMS", "stops[" + i + "].offset must be 0..100.");
        }
        var existing = null;
        for (i = 0; i < doc.gradients.length; i++) {
            if (String(doc.gradients[i].name) === String(P.name)) { existing = doc.gradients[i]; break; }
        }
        if (existing && !P.replace)
            throw CAI.err("GRADIENT_EXISTS", "Gradient already defined: " + P.name +
                          " (pass replace=true to redefine).");
        var g = existing ? existing : doc.gradients.add();
        g.name = String(P.name);
        g.type = (String(P.type).toLowerCase() === "radial")
            ? GradientType.RADIAL : GradientType.LINEAR;
        while (g.gradientStops.length < stops.length) g.gradientStops.add();
        while (g.gradientStops.length > stops.length) {
            var last = g.gradientStops[g.gradientStops.length - 1];
            var okRemove = false;
            try { last.remove(); okRemove = true; } catch (eR) {}
            if (!okRemove)
                throw CAI.err("BAD_PARAMS", "Cannot reduce the stop count of existing gradient: " + P.name);
        }
        var out = [];
        for (i = 0; i < stops.length; i++) {
            var st = g.gradientStops[i];
            st.rampPoint = stops[i].offset;
            if (stops[i].midpoint !== undefined && stops[i].midpoint !== null)
                st.midPoint = stops[i].midpoint;
            st.color = CAI.rgb(stops[i].color);
            if (stops[i].opacity !== undefined && stops[i].opacity !== null) {
                try { st.opacity = stops[i].opacity; } catch (eO) {}
            }
            var row = { offset: st.rampPoint, midpoint: st.midPoint,
                        color: CAI.describeColor(st.color), opacity: 100 };
            try { row.opacity = st.opacity; } catch (eO2) {}
            out.push(row);
        }
        return CAI.ok({ name: String(g.name),
                        type: (String(g.type) === String(GradientType.RADIAL)) ? "radial" : "linear",
                        stops: out, replaced: !!existing,
                        gradients_defined: doc.gradients.length });
    } catch (e) { return CAI.failFromException(e); }
})();
