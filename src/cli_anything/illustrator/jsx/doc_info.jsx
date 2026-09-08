(function () {
    try {
        var P = CAI.parse(__PARAMS_JSON);
        var doc = CAI.resolveDoc(P);
        return CAI.ok(CAI.docInfo(doc));
    } catch (e) { return CAI.failFromException(e); }
})();
