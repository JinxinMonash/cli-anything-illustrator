(function () {
    try {
        var P = CAI.parse(__PARAMS_JSON);
        var doc = CAI.resolveDoc(P);
        var f = new File(P.path);
        var opts = new IllustratorSaveOptions();
        opts.pdfCompatible = (P.pdf_compatible === false) ? false : true;
        opts.embedICCProfile = true;
        opts.compressed = true;
        CAI.silently(function () { doc.saveAs(f, opts); });
        var info = CAI.docInfo(doc);
        info.saved_to = String(f.fsName);
        return CAI.ok(info);
    } catch (e) { return CAI.failFromException(e); }
})();
