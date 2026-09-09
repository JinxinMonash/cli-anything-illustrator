// Unique fill/stroke colours in use across paths and text frames, with
// usage counts. Gradient paints are reported by gradient name.
(function () {
    try {
        var P = CAI.parse(__PARAMS_JSON);
        var doc = CAI.resolveDoc(P);
        var reg = {};
        var order = [];
        function addColor(cd, slot) {
            var key = CAI.stringify(cd);
            if (!reg[key]) {
                reg[key] = { color: cd, fill_count: 0, stroke_count: 0, text_count: 0 };
                order.push(key);
            }
            reg[key][slot]++;
        }
        var i;
        for (i = 0; i < doc.pathItems.length; i++) {
            var p = doc.pathItems[i];
            if (p.filled) addColor(CAI.describeColor(p.fillColor), "fill_count");
            if (p.stroked) addColor(CAI.describeColor(p.strokeColor), "stroke_count");
        }
        for (i = 0; i < doc.textFrames.length; i++) {
            var cd = null;
            try {
                cd = CAI.describeColor(
                    doc.textFrames[i].textRange.characterAttributes.fillColor);
            } catch (e0) { cd = null; }
            if (cd) addColor(cd, "text_count");
        }
        var out = [];
        for (i = 0; i < order.length; i++) out.push(reg[order[i]]);
        return CAI.ok({ unique_colors: out.length, colors: out });
    } catch (e) { return CAI.failFromException(e); }
})();
