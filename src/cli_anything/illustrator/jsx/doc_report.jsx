// Integrity report for scientific-figure review: fonts in use, links,
// rasters, clipping masks, locked/hidden content, legacy text.
(function () {
    try {
        var P = CAI.parse(__PARAMS_JSON);
        var doc = CAI.resolveDoc(P);
        var rep = CAI.docInfo(doc);

        var fonts = {};
        var unavailable = [];
        for (var i = 0; i < doc.textFrames.length; i++) {
            var nm = "(mixed or unknown)";
            try { nm = String(doc.textFrames[i].textRange.characterAttributes.textFont.name); }
            catch (e) {}
            fonts[nm] = (fonts[nm] || 0) + 1;
        }
        var fontList = [];
        for (var k in fonts) {
            var avail = true;
            try { app.textFonts.getByName(k); } catch (e) { avail = false; }
            fontList.push({ font: k, text_frames: fonts[k], available_in_app: avail });
            if (!avail) unavailable.push(k);
        }

        var links = [];
        for (var p = 0; p < doc.placedItems.length; p++) {
            var pl = doc.placedItems[p];
            var row = { name: pl.name || "", missing: false, file: null };
            try { row.file = String(pl.file.fsName); }
            catch (e) { row.missing = true; }
            links.push(row);
        }

        var clipCount = 0;
        for (var c = 0; c < doc.pathItems.length; c++) {
            try { if (doc.pathItems[c].clipping) clipCount++; } catch (e) {}
        }

        var lockedLayers = [], hiddenLayers = [];
        for (var L = 0; L < doc.layers.length; L++) {
            if (doc.layers[L].locked) lockedLayers.push(doc.layers[L].name);
            if (!doc.layers[L].visible) hiddenLayers.push(doc.layers[L].name);
        }

        var ed = {
            text_frames: doc.textFrames.length,
            path_items: doc.pathItems.length,
            raster_items: doc.rasterItems.length,
            placed_items: doc.placedItems.length,
            gradients_defined: 0,
            clipping_groups: 0,
            locked_items: 0,
            hidden_items: 0
        };
        try { ed.gradients_defined = doc.gradients.length; } catch (eg) {}
        var allPI = doc.pageItems;
        for (var q = 0; q < allPI.length; q++) {
            if (allPI[q].locked) ed.locked_items++;
            if (allPI[q].hidden) ed.hidden_items++;
            try {
                if (String(allPI[q].typename) === "GroupItem" && allPI[q].clipped)
                    ed.clipping_groups++;
            } catch (eq) {}
        }
        rep.editability = ed;

        rep.fonts_used = fontList;
        rep.fonts_unavailable = unavailable;
        rep.placed_links = links;
        rep.clipping_paths = clipCount;
        rep.locked_layers = lockedLayers;
        rep.hidden_layers = hiddenLayers;
        rep.legacy_text_items = doc.legacyTextItems.length;
        rep.compound_paths = doc.compoundPathItems.length;
        rep.symbol_items = doc.symbolItems.length;
        rep.warnings = [];
        if (unavailable.length > 0)
            rep.warnings.push("Fonts referenced by text frames are not available: " + unavailable.join(", "));
        for (var w = 0; w < links.length; w++)
            if (links[w].missing) rep.warnings.push("Placed item with missing link: " + (links[w].name || "(unnamed)"));
        if (doc.rasterItems.length > 0)
            rep.warnings.push(doc.rasterItems.length + " raster item(s): not editable vector content.");
        if (doc.legacyTextItems.length > 0)
            rep.warnings.push(doc.legacyTextItems.length + " legacy text item(s): not editable until converted.");
        return CAI.ok(rep);
    } catch (e) { return CAI.failFromException(e); }
})();
