(function () {
    try {
        var P = CAI.parse(__PARAMS_JSON);
        var doc = CAI.resolveDoc(P);
        var ab = P.artboard || 0;
        var sel = P.selector || {};
        sel.type = "text";
        var items = CAI.requireItems(doc, sel, !!P.allow_multiple);
        var U = P.updates || {};
        var fontInfo = null;
        if (U.font) fontInfo = CAI.getFont(U.font, !!U.allow_font_substitute);
        var results = [];
        for (var i = 0; i < items.length; i++) {
            var tf = items[i];
            var before = CAI.describeItem(doc, ab, tf);
            if (U.contents !== undefined && U.contents !== null) tf.contents = String(U.contents);
            var attrs = tf.textRange.characterAttributes;
            if (U.size) attrs.size = U.size;
            if (fontInfo && fontInfo.font) attrs.textFont = fontInfo.font;
            if (U.color) attrs.fillColor = CAI.rgb(U.color);
            if (U.tracking !== undefined && U.tracking !== null) attrs.tracking = U.tracking;
            if (U.leading !== undefined && U.leading !== null) {
                try { attrs.autoLeading = false; } catch (eL) {}
                attrs.leading = U.leading;
            }
            if (U.justification) {
                tf.textRange.paragraphAttributes.justification =
                    CAI.justificationFrom(U.justification);
            }
            if ((U.width !== undefined && U.width !== null) ||
                (U.height !== undefined && U.height !== null)) {
                var isArea = false;
                try { isArea = (String(tf.kind) === String(TextType.AREATEXT)); } catch (eK) {}
                if (!isArea)
                    throw CAI.err("BAD_PARAMS",
                        "width/height resize applies only to area text frames.");
                if (U.width !== undefined && U.width !== null) tf.textPath.width = U.width;
                if (U.height !== undefined && U.height !== null) tf.textPath.height = U.height;
            }
            if (U.x !== undefined && U.x !== null && U.y !== undefined && U.y !== null) {
                tf.position = CAI.toAI(doc, ab, U.x, U.y);
            }
            if (U.new_name) tf.name = String(U.new_name);
            var after = CAI.describeTextDeep(doc, ab, tf);
            results.push({ before: before, after: after });
        }
        return CAI.ok({ updated: results.length, items: results,
                        font: fontInfo ? { requested: fontInfo.requested,
                                           resolved: fontInfo.resolved_name,
                                           exact: fontInfo.exact } : null });
    } catch (e) { return CAI.failFromException(e); }
})();
