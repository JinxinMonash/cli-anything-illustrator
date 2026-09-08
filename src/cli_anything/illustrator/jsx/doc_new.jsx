(function () {
    try {
        var P = CAI.parse(__PARAMS_JSON);
        var cs = (String(P.color_mode).toUpperCase() === "CMYK")
            ? DocumentColorSpace.CMYK : DocumentColorSpace.RGB;
        var doc = app.documents.add(cs, P.width, P.height);
        if (P.artboard_name) doc.artboards[0].name = String(P.artboard_name);
        if (P.base_layer_name) doc.layers[0].name = String(P.base_layer_name);
        return CAI.ok(CAI.docInfo(doc));
    } catch (e) { return CAI.failFromException(e); }
})();
