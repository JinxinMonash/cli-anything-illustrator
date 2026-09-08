(function () {
    try {
        var P = CAI.parse(__PARAMS_JSON);
        var doc = CAI.resolveDoc(P);
        for (var i = 0; i < doc.layers.length; i++) {
            if (doc.layers[i].name === P.name) {
                if (P.existing_ok) return CAI.ok({ name: P.name, created: false, index: i });
                throw CAI.err("LAYER_EXISTS", "Layer already exists: " + P.name);
            }
        }
        var ly = doc.layers.add();
        ly.name = P.name;
        return CAI.ok({ name: ly.name, created: true, index: 0, layer_count: doc.layers.length });
    } catch (e) { return CAI.failFromException(e); }
})();
