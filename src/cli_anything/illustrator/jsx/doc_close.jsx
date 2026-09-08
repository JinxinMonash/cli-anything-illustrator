(function () {
    try {
        var P = CAI.parse(__PARAMS_JSON);
        var doc = CAI.resolveDoc(P);
        var name = doc.name;
        if (!doc.saved && P.mode !== "discard" && P.mode !== "save")
            throw CAI.err("UNSAVED_CHANGES",
                "Document '" + name + "' has unsaved changes; pass --save or --discard-changes.");
        if (P.mode === "save") {
            if (CAI.docPath(doc) === "")
                throw CAI.err("UNSAVED_CHANGES",
                    "Document '" + name + "' has never been saved; use doc save-as first.");
            doc.close(SaveOptions.SAVECHANGES);
        } else {
            doc.close(SaveOptions.DONOTSAVECHANGES);
        }
        return CAI.ok({ closed: name, remaining_documents: app.documents.length });
    } catch (e) { return CAI.failFromException(e); }
})();
