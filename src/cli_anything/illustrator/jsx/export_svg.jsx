(function () {
    try {
        var P = CAI.parse(__PARAMS_JSON);
        var doc = CAI.resolveDoc(P);
        var opts = new ExportOptionsSVG();
        opts.embedRasterImages = (P.embed_raster === false) ? false : true;
        opts.fontSubsetting = SVGFontSubsetting.None;
        var warnings = [];
        if (P.text_handling === "outline") {
            opts.fontType = SVGFontType.OUTLINEFONT;
            warnings.push("Text outlined in the EXPORTED SVG (the open document keeps live text).");
        } else {
            opts.fontType = SVGFontType.SVGFONT;
        }
        var f = new File(P.path);
        doc.exportFile(f, ExportType.SVG, opts);
        return CAI.ok({ path: String(f.fsName), format: "SVG",
                        text_handling: P.text_handling || "keep",
                        exists: f.exists, warnings: warnings });
    } catch (e) { return CAI.failFromException(e); }
})();
