// Inventory of document gradients with their stops.
(function () {
    try {
        var P = CAI.parse(__PARAMS_JSON);
        var doc = CAI.resolveDoc(P);
        var out = [];
        for (var i = 0; i < doc.gradients.length; i++) {
            var g = doc.gradients[i];
            var stops = [];
            for (var j = 0; j < g.gradientStops.length; j++) {
                var st = g.gradientStops[j];
                var row = { offset: st.rampPoint, midpoint: st.midPoint,
                            color: CAI.describeColor(st.color), opacity: 100 };
                try { row.opacity = st.opacity; } catch (eO) {}
                stops.push(row);
            }
            out.push({ name: String(g.name),
                       type: (String(g.type) === String(GradientType.RADIAL)) ? "radial" : "linear",
                       stop_count: stops.length, stops: stops });
        }
        return CAI.ok({ gradients_defined: out.length, gradients: out });
    } catch (e) { return CAI.failFromException(e); }
})();
