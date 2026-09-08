// PDF delivery copy. Illustrator's saveAs(PDF) re-associates the open
// document with the PDF file, so afterwards we save the document back to its
// original .ai path to restore the association (non-destructive policy:
// requires the document to have been saved as .ai first).
(function () {
    try {
        var P = CAI.parse(__PARAMS_JSON);
        var doc = CAI.resolveDoc(P);
        var origPath = CAI.docPath(doc);
        if (origPath === "" && !P.allow_unsaved)
            throw CAI.err("UNSAVED_CHANGES",
                "Save the document as .ai first (doc save-as) so its file association can be restored after PDF export.");
        var opts = new PDFSaveOptions();
        opts.preserveEditability = (P.editable === false) ? false : true;
        opts.viewAfterSaving = false;
        var f = new File(P.path);
        doc.saveAs(f, opts);
        var reassociated = false;
        if (origPath !== "") {
            var back = new IllustratorSaveOptions();
            back.pdfCompatible = true;
            doc.saveAs(new File(origPath), back);
            reassociated = true;
        }
        return CAI.ok({ path: String(f.fsName), format: "PDF",
                        preserve_editability: opts.preserveEditability,
                        reassociated_to: reassociated ? origPath : null,
                        exists: f.exists });
    } catch (e) { return CAI.failFromException(e); }
})();
