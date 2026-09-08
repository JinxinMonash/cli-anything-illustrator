(function () {
    try {
        var P = CAI.parse(__PARAMS_JSON);
        if (!P.confirm)
            throw CAI.err("CONFIRM_REQUIRED",
                "Deletion is destructive; re-run with --confirm.");
        var doc = CAI.resolveDoc(P);
        var ab = P.artboard || 0;
        var items = CAI.requireItems(doc, P.selector || {}, !!P.allow_multiple);
        var removed = [];
        for (var i = items.length - 1; i >= 0; i--) {
            removed.push(CAI.describeItem(doc, ab, items[i]));
            items[i].remove();
        }
        return CAI.ok({ deleted: removed.length, items: removed });
    } catch (e) { return CAI.failFromException(e); }
})();
