(function () {
    try {
        CAI.parse(__PARAMS_JSON);
        var out = [];
        for (var i = 0; i < app.documents.length; i++) {
            var d = app.documents[i];
            var row = { index: i, name: d.name, path: CAI.docPath(d), saved: d.saved, active: false };
            try { row.active = (app.activeDocument === d); } catch (e) {}
            out.push(row);
        }
        return CAI.ok({ count: out.length, documents: out });
    } catch (e) { return CAI.failFromException(e); }
})();
