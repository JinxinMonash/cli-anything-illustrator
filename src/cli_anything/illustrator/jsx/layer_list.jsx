(function () {
    try {
        var P = CAI.parse(__PARAMS_JSON);
        var doc = CAI.resolveDoc(P);
        var out = [];
        for (var i = 0; i < doc.layers.length; i++) {
            var ly = doc.layers[i];
            out.push({
                index: i, name: ly.name, visible: ly.visible, locked: ly.locked,
                printable: ly.printable, page_items: ly.pageItems.length,
                text_frames: ly.textFrames.length, sublayers: ly.layers.length
            });
        }
        return CAI.ok({ count: out.length, layers: out });
    } catch (e) { return CAI.failFromException(e); }
})();
