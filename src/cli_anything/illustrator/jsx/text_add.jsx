(function () {
    try {
        var P = CAI.parse(__PARAMS_JSON);
        var doc = CAI.resolveDoc(P);
        var ab = P.artboard || 0;
        var fontInfo = null;
        if (P.font) fontInfo = CAI.getFont(P.font, !!P.allow_font_substitute);

        var layer = null;
        if (P.layer) layer = CAI.getLayer(doc, P.layer, !!P.layer_create);

        var tf;
        var pos = CAI.toAI(doc, ab, P.x, P.y);
        if (P.kind === "area") {
            var rect = doc.pathItems.rectangle(pos[1], pos[0], P.box_w, P.box_h);
            tf = doc.textFrames.areaText(rect);
        } else {
            tf = doc.textFrames.pointText(pos);
        }
        tf.contents = String(P.contents);
        if (layer) tf.move(layer, ElementPlacement.PLACEATBEGINNING);
        var attrs = tf.textRange.characterAttributes;
        if (P.size) attrs.size = P.size;
        if (fontInfo && fontInfo.font) attrs.textFont = fontInfo.font;
        if (P.color) attrs.fillColor = CAI.rgb(P.color);
        if (P.name) tf.name = String(P.name);
        if (P.justification) {
            var j = String(P.justification).toUpperCase();
            if (j === "CENTER") tf.textRange.paragraphAttributes.justification = Justification.CENTER;
            else if (j === "RIGHT") tf.textRange.paragraphAttributes.justification = Justification.RIGHT;
            else tf.textRange.paragraphAttributes.justification = Justification.LEFT;
        }
        var desc = CAI.describeItem(doc, ab, tf);
        desc.contents_full = String(tf.contents);
        desc.font = fontInfo ? {
            requested: fontInfo.requested, resolved: fontInfo.resolved_name,
            exact: fontInfo.exact
        } : null;
        desc.font_substituted = fontInfo === null && P.font ? true
            : (fontInfo ? !fontInfo.exact : false);
        return CAI.ok(desc);
    } catch (e) { return CAI.failFromException(e); }
})();
