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
        // Live Illustrator (observed on 27.5) RE-ASSOCIATES the open
        // document with the exported SVG file, renaming it and breaking any
        // later command that targets the original document. Capture the
        // association and restore it after the export.
        var origPath = CAI.docPath(doc);
        var f = new File(P.path);
        doc.exportFile(f, ExportType.SVG, opts);
        var reassociated = null;
        if (origPath !== "" && CAI.docPath(doc) !== origPath) {
            var back = new IllustratorSaveOptions();
            back.pdfCompatible = true;
            CAI.silently(function () { doc.saveAs(new File(origPath), back); });
            reassociated = origPath;
        } else if (origPath === "") {
            warnings.push("Document is unsaved; if Illustrator re-associated " +
                          "it with the exported SVG, save it as .ai to restore.");
        }
        return CAI.ok({ path: String(f.fsName), format: "SVG",
                        text_handling: P.text_handling || "keep",
                        reassociated_to: reassociated,
                        exists: f.exists, warnings: warnings });
    } catch (e) { return CAI.failFromException(e); }
})();
