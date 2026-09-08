(function () {
    try {
        var P = CAI.parse(__PARAMS_JSON);
        var doc = CAI.resolveDoc(P);
        var ab = (P.artboard === undefined || P.artboard === null) ? 0 : P.artboard;
        if (ab < 0 || ab >= doc.artboards.length)
            throw CAI.err("BAD_PARAMS", "Artboard index out of range: " + ab);
        doc.artboards.setActiveArtboardIndex(ab);
        var opts = new ExportOptionsPNG24();
        opts.antiAliasing = true;
        opts.transparency = (P.transparent === false) ? false : true;
        opts.artBoardClipping = true;
        var scale = (P.dpi || 72) / 72 * 100;
        opts.horizontalScale = scale;
        opts.verticalScale = scale;
        var f = new File(P.path);
        doc.exportFile(f, ExportType.PNG24, opts);
        return CAI.ok({ path: String(f.fsName), format: "PNG", dpi: P.dpi || 72,
                        artboard: ab, exists: f.exists });
    } catch (e) { return CAI.failFromException(e); }
})();
