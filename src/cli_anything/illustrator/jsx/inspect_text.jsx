// Full attribute readback for matched text frames: contents, font
// name/family/style, size, tracking, leading, justification, fill colour,
// kind (point/area), bounds.
(function () {
    try {
        var P = CAI.parse(__PARAMS_JSON);
        var doc = CAI.resolveDoc(P);
        var ab = P.artboard || 0;
        var sel = P.selector || {};
        sel.type = "text";
        var items = CAI.findItems(doc, sel);
        var limit = P.limit || 200;
        var out = [];
        for (var i = 0; i < items.length && i < limit; i++) {
            out.push(CAI.describeTextDeep(doc, ab, items[i]));
        }
        return CAI.ok({ total_matches: items.length, returned: out.length, frames: out });
    } catch (e) { return CAI.failFromException(e); }
})();
