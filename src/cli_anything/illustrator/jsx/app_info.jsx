(function () {
    try {
        var P = CAI.parse(__PARAMS_JSON);
        var info = {
            version: String(app.version),
            path: String(app.path),
            locale: String($.locale),
            extendscript_version: String($.version),
            open_documents: [],
            font_count: app.textFonts.length
        };
        for (var i = 0; i < app.documents.length; i++) {
            var d = app.documents[i];
            info.open_documents.push({ name: d.name, path: CAI.docPath(d), saved: d.saved });
        }
        return CAI.ok(info);
    } catch (e) { return CAI.failFromException(e); }
})();
