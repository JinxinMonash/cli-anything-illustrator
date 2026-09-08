(function () {
    try {
        var P = CAI.parse(__PARAMS_JSON);
        var doc = CAI.resolveDoc(P);
        var ab = P.artboard || 0;
        var items = CAI.findItems(doc, P.selector || {});
        var limit = P.limit || 200;
        var out = [];
        for (var i = 0; i < items.length && i < limit; i++) {
            out.push(CAI.describeItem(doc, ab, items[i]));
        }
        return CAI.ok({ total_matches: items.length, returned: out.length, items: out });
    } catch (e) { return CAI.failFromException(e); }
})();
