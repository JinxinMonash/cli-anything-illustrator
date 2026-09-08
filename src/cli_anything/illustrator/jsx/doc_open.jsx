(function () {
    try {
        var P = CAI.parse(__PARAMS_JSON);
        var f = new File(P.path);
        if (!f.exists) throw CAI.err("FILE_NOT_FOUND", "File not found: " + P.path);
        var doc = CAI.silently(function () { return app.open(f); });
        return CAI.ok(CAI.docInfo(doc));
    } catch (e) { return CAI.failFromException(e); }
})();
