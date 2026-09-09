// Full layer tree with per-layer item counts/types plus document summary.
(function () {
    try {
        var P = CAI.parse(__PARAMS_JSON);
        var doc = CAI.resolveDoc(P);
        function layerInfo(ly) {
            var counts = { text: 0, path: 0, group: 0, compound: 0,
                           placed: 0, raster: 0, symbol: 0, other: 0, total: 0 };
            var pts = ly.pageItems;
            for (var i = 0; i < pts.length; i++) {
                var t = CAI.typeName(pts[i]);
                if (counts[t] !== undefined) counts[t]++;
                else counts.other++;
                counts.total++;
            }
            var row = { name: ly.name, visible: ly.visible, locked: ly.locked,
                        printable: true, item_counts: counts, sublayers: [] };
            try { row.printable = ly.printable; } catch (e0) {}
            try {
                for (var s = 0; s < ly.layers.length; s++)
                    row.sublayers.push(layerInfo(ly.layers[s]));
            } catch (e1) {}
            return row;
        }
        var layers = [];
        for (var L = 0; L < doc.layers.length; L++) layers.push(layerInfo(doc.layers[L]));
        return CAI.ok({ doc: CAI.docInfo(doc), layers: layers });
    } catch (e) { return CAI.failFromException(e); }
})();
