// Import artwork into a target document.
// mode "editable": opens the source (SVG/AI/PDF/EPS) as a temporary document
//   and duplicates its content into a named group -> real editable paths/text.
// mode "linked": adds a PlacedItem (link). NOT editable vector content.
(function () {
    try {
        var P = CAI.parse(__PARAMS_JSON);
        var doc = CAI.resolveDoc(P);   // resolve target BEFORE opening source
        var ab = P.artboard || 0;
        var f = new File(P.source);
        if (!f.exists) throw CAI.err("FILE_NOT_FOUND", "Source not found: " + P.source);
        var layer = P.layer ? CAI.getLayer(doc, P.layer, true) : doc.activeLayer;
        if (layer.locked) throw CAI.err("OP_FAILED", "Target layer is locked: " + layer.name);
        var warnings = [];
        var desc;

        if (P.mode === "linked") {
            var pl = doc.placedItems.add();
            pl.file = f;
            if (P.name) pl.name = String(P.name);
            pl.move(layer, ElementPlacement.PLACEATBEGINNING);
            if (P.x !== undefined && P.x !== null) {
                var tp = CAI.toAI(doc, ab, P.x, P.y);
                var vb = pl.visibleBounds;
                pl.translate(tp[0] - vb[0], tp[1] - vb[1]);
            }
            warnings.push("Placed as a LINKED item: content is not editable vector artwork in this document.");
            desc = CAI.describeItem(doc, ab, pl);
            desc.editable = false;
        } else {
            var srcDoc = CAI.silently(function () { return app.open(f); });
            var srcInfo = {
                text_frames: srcDoc.textFrames.length,
                raster_items: srcDoc.rasterItems.length,
                placed_items: srcDoc.placedItems.length,
                symbol_items: srcDoc.symbolItems.length,
                legacy_text_items: srcDoc.legacyTextItems.length,
                path_items: srcDoc.pathItems.length
            };
            var fontsUsed = {};
            for (var tI = 0; tI < srcDoc.textFrames.length; tI++) {
                var fn = "(mixed or unknown)";
                try { fn = String(srcDoc.textFrames[tI].textRange.characterAttributes.textFont.name); }
                catch (e) {}
                fontsUsed[fn] = true;
            }
            var grp = layer.groupItems.add();
            if (P.name) grp.name = String(P.name);
            // duplicate direct children of each source layer, topmost first;
            // PLACEATEND preserves relative z-order
            var copied = 0;
            for (var li = 0; li < srcDoc.layers.length; li++) {
                var sly = srcDoc.layers[li];
                var direct = [];
                for (var pi = 0; pi < sly.pageItems.length; pi++) {
                    var cand = sly.pageItems[pi];
                    if (cand.parent === sly) direct.push(cand);
                }
                for (var di = 0; di < direct.length; di++) {
                    direct[di].duplicate(grp, ElementPlacement.PLACEATEND);
                    copied++;
                }
            }
            srcDoc.close(SaveOptions.DONOTSAVECHANGES);
            if (copied === 0) {
                grp.remove();
                throw CAI.err("OP_FAILED", "No items were imported from: " + P.source);
            }
            if (P.x !== undefined && P.x !== null) {
                var tp2 = CAI.toAI(doc, ab, P.x, P.y);
                var vb2 = grp.visibleBounds;
                grp.translate(tp2[0] - vb2[0], tp2[1] - vb2[1]);
            }
            if (srcInfo.raster_items > 0)
                warnings.push(srcInfo.raster_items + " raster item(s) imported: raster content is not editable vector artwork.");
            if (srcInfo.placed_items > 0)
                warnings.push(srcInfo.placed_items + " linked/placed item(s) in source.");
            if (srcInfo.legacy_text_items > 0)
                warnings.push(srcInfo.legacy_text_items + " legacy text item(s) in source.");
            if (srcInfo.text_frames === 0 && srcInfo.path_items > 0)
                warnings.push("Source contains no live text frames; any visible text is already outlined in the source.");
            desc = CAI.describeItem(doc, ab, grp);
            desc.editable = true;
            desc.items_copied = copied;
            desc.source_summary = srcInfo;
            var fu = [];
            for (var k in fontsUsed) fu.push(k);
            desc.source_fonts = fu;
        }
        desc.warnings = warnings;
        return CAI.ok(desc);
    } catch (e) { return CAI.failFromException(e); }
})();
