// cli-anything-illustrator ExtendScript prelude (ES3-compatible).
// Every operation script is appended after this prelude and must evaluate to
// a single JSON string produced by CAI.ok(...) or CAI.fail(...).
// Parameters arrive as __PARAMS_JSON, a JS string literal containing JSON
// text generated locally by json.dumps(ensure_ascii=True); user data is never
// spliced into code.

var CAI = (function () {
    var M = {};

    // ---------- JSON ----------
    M.parse = function (jsonText) {
        // jsonText is produced by this tool itself (trusted, ASCII-only).
        return eval("(" + jsonText + ")");
    };

    function escChar(c) {
        var code = c.charCodeAt(0);
        if (c === '"') return '\\"';
        if (c === "\\") return "\\\\";
        if (code === 8) return "\\b";
        if (code === 9) return "\\t";
        if (code === 10) return "\\n";
        if (code === 12) return "\\f";
        if (code === 13) return "\\r";
        var hex = code.toString(16);
        while (hex.length < 4) hex = "0" + hex;
        return "\\u" + hex;
    }

    M.str = function (s) {
        s = String(s);
        var out = '"';
        for (var i = 0; i < s.length; i++) {
            var c = s.charAt(i);
            var code = s.charCodeAt(i);
            if (c === '"' || c === "\\" || code < 32 || code > 126) {
                out += escChar(c);
            } else {
                out += c;
            }
        }
        return out + '"';
    };

    M.stringify = function (v) {
        var t = typeof v;
        if (v === null || v === undefined) return "null";
        if (t === "number") return isFinite(v) ? String(v) : "null";
        if (t === "boolean") return v ? "true" : "false";
        if (t === "string") return M.str(v);
        if (v instanceof Array) {
            var parts = [];
            for (var i = 0; i < v.length; i++) parts.push(M.stringify(v[i]));
            return "[" + parts.join(",") + "]";
        }
        if (t === "object") {
            var kv = [];
            for (var k in v) {
                if (v.hasOwnProperty && !v.hasOwnProperty(k)) continue;
                kv.push(M.str(k) + ":" + M.stringify(v[k]));
            }
            return "{" + kv.join(",") + "}";
        }
        return M.str(String(v));
    };

    // ---------- result envelope ----------
    M.ok = function (result) {
        return M.stringify({ ok: true, result: result });
    };
    M.fail = function (code, message, details) {
        var e = { code: code, message: String(message) };
        if (details !== undefined) e.details = details;
        return M.stringify({ ok: false, error: e });
    };
    M.err = function (code, message, details) {
        // throwable carrying a structured payload
        var x = new Error(String(message));
        x.caiCode = code;
        x.caiDetails = details;
        return x;
    };
    M.failFromException = function (e) {
        if (e && e.caiCode) return M.fail(e.caiCode, e.message, e.caiDetails);
        var msg = (e && e.message) ? e.message : String(e);
        var det = {};
        if (e && e.line !== undefined) det.line = e.line;
        if (e && e.fileName !== undefined) det.fileName = String(e.fileName);
        return M.fail("SCRIPT_ERROR", msg, det);
    };

    // ---------- document targeting ----------
    // P.doc: optional document name or full path. Ambiguity is an error:
    // with >1 open documents and no P.doc, the operation is refused.
    M.resolveDoc = function (P) {
        var n = app.documents.length;
        if (n === 0) throw M.err("NO_DOCUMENT", "No document is open in Illustrator.");
        var want = P && P.doc ? String(P.doc) : null;
        if (!want) {
            if (n === 1) return app.documents[0];
            var names = [];
            for (var i = 0; i < n; i++) names.push(app.documents[i].name);
            throw M.err("AMBIGUOUS_DOCUMENT",
                n + " documents are open; pass an explicit --doc name.",
                { open_documents: names });
        }
        var matches = [];
        for (var j = 0; j < n; j++) {
            var d = app.documents[j];
            var full = "";
            try { full = d.fullName ? String(d.fullName.fsName) : ""; } catch (e) { full = ""; }
            if (d.name === want || full === want) matches.push(d);
        }
        if (matches.length === 1) return matches[0];
        if (matches.length === 0) throw M.err("DOC_NOT_FOUND", "No open document named: " + want);
        throw M.err("AMBIGUOUS_DOCUMENT", "More than one open document matches: " + want);
    };

    M.docPath = function (d) {
        try { return d.fullName ? String(d.fullName.fsName) : ""; } catch (e) { return ""; }
    };

    // ---------- coordinates ----------
    // Canvas coordinates: origin at the TOP-LEFT of the target artboard
    // (index P.artboard, default 0), x to the right, y DOWNWARD, in points.
    // Illustrator's internal coordinates are y-up; artboardRect = [L, T, R, B].
    M.abRect = function (doc, abIndex) {
        var idx = (abIndex === undefined || abIndex === null) ? 0 : abIndex;
        if (idx < 0 || idx >= doc.artboards.length)
            throw M.err("BAD_PARAMS", "Artboard index out of range: " + idx);
        return doc.artboards[idx].artboardRect;
    };
    M.toAI = function (doc, abIndex, x, y) {
        var r = M.abRect(doc, abIndex);
        return [r[0] + x, r[1] - y];
    };
    M.fromAI = function (doc, abIndex, aiX, aiY) {
        var r = M.abRect(doc, abIndex);
        return [aiX - r[0], r[1] - aiY];
    };
    // visibleBounds/geometricBounds: [L, T, R, B] (y-up)
    M.canvasBounds = function (doc, abIndex, b) {
        var r = M.abRect(doc, abIndex);
        return {
            x: b[0] - r[0],
            y: r[1] - b[1],
            w: b[2] - b[0],
            h: b[1] - b[3]
        };
    };

    // ---------- items ----------
    M.typeName = function (item) {
        var t = item.typename;
        if (t === "TextFrame") return "text";
        if (t === "PathItem") return "path";
        if (t === "GroupItem") return "group";
        if (t === "PlacedItem") return "placed";
        if (t === "RasterItem") return "raster";
        if (t === "CompoundPathItem") return "compound";
        if (t === "SymbolItem") return "symbol";
        if (t === "MeshItem") return "mesh";
        if (t === "PluginItem") return "plugin";
        if (t === "GraphItem") return "graph";
        if (t === "LegacyTextItem") return "legacytext";
        return t;
    };

    M.itemUuid = function (item) {
        try { if (item.uuid !== undefined) return String(item.uuid); } catch (e) {}
        return null;
    };

    M.describeItem = function (doc, abIndex, item) {
        var d = {
            uuid: M.itemUuid(item),
            name: item.name || "",
            type: M.typeName(item),
            layer: null,
            locked: item.locked,
            hidden: item.hidden,
            bounds: null,
            parent_type: item.parent ? String(item.parent.typename) : null
        };
        try { d.layer = item.layer ? item.layer.name : null; } catch (e) {}
        try { d.bounds = M.canvasBounds(doc, abIndex, item.visibleBounds); } catch (e) {}
        if (d.type === "text") {
            try {
                var c = String(item.contents);
                d.contents = c.length > 120 ? c.substring(0, 120) + "..." : c;
            } catch (e) {}
        }
        return d;
    };

    // Selector: {uuid, name, layer, type, contains, index}
    // All present criteria must match. `contains` applies to text contents.
    M.findItems = function (doc, sel) {
        sel = sel || {};
        var out = [];
        var n = doc.pageItems.length;
        for (var i = 0; i < n; i++) {
            var it = doc.pageItems[i];
            if (sel.uuid) {
                var u = M.itemUuid(it);
                if (u === null || u !== String(sel.uuid)) continue;
            }
            if (sel.name && (it.name || "") !== String(sel.name)) continue;
            if (sel.type && M.typeName(it) !== String(sel.type)) continue;
            if (sel.layer) {
                var ln = null;
                try { ln = it.layer ? it.layer.name : null; } catch (e) { ln = null; }
                if (ln !== String(sel.layer)) continue;
            }
            if (sel.contains) {
                if (M.typeName(it) !== "text") continue;
                var c = "";
                try { c = String(it.contents); } catch (e) { c = ""; }
                if (c.indexOf(String(sel.contains)) === -1) continue;
            }
            out.push(it);
        }
        if (sel.index !== undefined && sel.index !== null) {
            var idx = sel.index;
            if (idx < 0 || idx >= out.length)
                throw M.err("SELECTOR_NO_MATCH", "Selector index out of range: " + idx +
                    " (matched " + out.length + " items)");
            return [out[idx]];
        }
        return out;
    };

    // Resolve to exactly one item unless allowMultiple.
    M.requireItems = function (doc, sel, allowMultiple) {
        var items = M.findItems(doc, sel);
        if (items.length === 0)
            throw M.err("SELECTOR_NO_MATCH", "No item matches the selector.", { selector: sel });
        if (items.length > 1 && !allowMultiple)
            throw M.err("SELECTOR_AMBIGUOUS",
                items.length + " items match; refine the selector or pass --all.",
                { match_count: items.length });
        return items;
    };

    // ---------- layers ----------
    M.getLayer = function (doc, name, createIfMissing) {
        for (var i = 0; i < doc.layers.length; i++) {
            if (doc.layers[i].name === name) return doc.layers[i];
        }
        if (createIfMissing) {
            var ly = doc.layers.add();
            ly.name = name;
            return ly;
        }
        throw M.err("LAYER_NOT_FOUND", "No layer named: " + name);
    };

    // ---------- colors & fonts ----------
    M.rgb = function (arr) {
        var c = new RGBColor();
        c.red = arr[0]; c.green = arr[1]; c.blue = arr[2];
        return c;
    };
    M.cmyk = function (arr) {
        var c = new CMYKColor();
        c.cyan = arr[0]; c.magenta = arr[1]; c.yellow = arr[2]; c.black = arr[3];
        return c;
    };

    // Returns {font, resolved_name, requested, exact} or throws FONT_NOT_FOUND.
    M.getFont = function (requested, allowSubstitute) {
        try {
            var f = app.textFonts.getByName(requested);
            return { font: f, resolved_name: String(f.name), requested: requested, exact: true };
        } catch (e) {}
        // second pass: family or family+style match (case-insensitive)
        var wanted = String(requested).toLowerCase();
        for (var i = 0; i < app.textFonts.length; i++) {
            var tf = app.textFonts[i];
            var nm = String(tf.name).toLowerCase();
            var fam = String(tf.family).toLowerCase();
            if (nm === wanted || fam === wanted ||
                (fam + "-" + String(tf.style).toLowerCase()) === wanted) {
                return { font: tf, resolved_name: String(tf.name), requested: requested, exact: false };
            }
        }
        if (allowSubstitute) return null;
        throw M.err("FONT_NOT_FOUND",
            "Font not available: " + requested +
            " (pass --allow-font-substitute to keep the application default)");
    };

    return M;
})();

// ---------- shared helpers (appended) ----------
CAI.docInfo = function (doc) {
    var info = {
        name: doc.name,
        path: CAI.docPath(doc),
        saved: doc.saved,
        width: doc.width,
        height: doc.height,
        color_space: String(doc.documentColorSpace),
        artboards: doc.artboards.length,
        layers: doc.layers.length,
        page_items: doc.pageItems.length,
        text_frames: doc.textFrames.length,
        placed_items: doc.placedItems.length,
        raster_items: doc.rasterItems.length,
        active: false
    };
    try { info.active = (app.activeDocument === doc); } catch (e) {}
    var abs = [];
    for (var i = 0; i < doc.artboards.length; i++) {
        var r = doc.artboards[i].artboardRect;
        abs.push({ index: i, name: doc.artboards[i].name,
                   width: r[2] - r[0], height: r[1] - r[3] });
    }
    info.artboard_list = abs;
    return info;
};

// ---------- expanded object model helpers ----------
// Stroke cap / join names <-> ExtendScript enums.
CAI.strokeCapFrom = function (s) {
    var v = String(s).toLowerCase();
    if (v === "butt") return StrokeCap.BUTTENDCAP;
    if (v === "round") return StrokeCap.ROUNDENDCAP;
    if (v === "projecting" || v === "square") return StrokeCap.PROJECTINGENDCAP;
    throw CAI.err("BAD_PARAMS", "Unknown stroke cap: " + s + " (use butt|round|projecting)");
};
CAI.strokeCapName = function (v) {
    var s = String(v);
    if (s === String(StrokeCap.BUTTENDCAP)) return "butt";
    if (s === String(StrokeCap.ROUNDENDCAP)) return "round";
    if (s === String(StrokeCap.PROJECTINGENDCAP)) return "projecting";
    return s;
};
CAI.strokeJoinFrom = function (s) {
    var v = String(s).toLowerCase();
    if (v === "miter") return StrokeJoin.MITERENDJOIN;
    if (v === "round") return StrokeJoin.ROUNDENDJOIN;
    if (v === "bevel") return StrokeJoin.BEVELENDJOIN;
    throw CAI.err("BAD_PARAMS", "Unknown stroke join: " + s + " (use miter|round|bevel)");
};
CAI.strokeJoinName = function (v) {
    var s = String(v);
    if (s === String(StrokeJoin.MITERENDJOIN)) return "miter";
    if (s === String(StrokeJoin.ROUNDENDJOIN)) return "round";
    if (s === String(StrokeJoin.BEVELENDJOIN)) return "bevel";
    return s;
};
CAI.justificationFrom = function (s) {
    var v = String(s).toLowerCase();
    if (v === "left") return Justification.LEFT;
    if (v === "center" || v === "centre") return Justification.CENTER;
    if (v === "right") return Justification.RIGHT;
    throw CAI.err("BAD_PARAMS", "Unknown justification: " + s + " (use left|center|right)");
};
CAI.justificationName = function (v) {
    var s = String(v);
    if (s === String(Justification.LEFT)) return "left";
    if (s === String(Justification.CENTER)) return "center";
    if (s === String(Justification.RIGHT)) return "right";
    return s;
};

// Structured description of any paint value.
CAI.describeColor = function (c) {
    if (c === null || c === undefined) return { type: "none" };
    var t = "";
    try { t = String(c.typename); } catch (e) { t = ""; }
    if (t === "RGBColor") return { type: "rgb", rgb: [c.red, c.green, c.blue] };
    if (t === "CMYKColor") return { type: "cmyk", cmyk: [c.cyan, c.magenta, c.yellow, c.black] };
    if (t === "GrayColor") return { type: "gray", gray: c.gray };
    if (t === "NoColor") return { type: "none" };
    if (t === "GradientColor") {
        var g = { type: "gradient", gradient: null, angle: 0 };
        try { g.gradient = String(c.gradient.name); } catch (e1) {}
        try { g.angle = c.angle; } catch (e2) {}
        return g;
    }
    if (t === "SpotColor") {
        var sp = { type: "spot", name: null };
        try { sp.name = String(c.spot.name); } catch (e3) {}
        return sp;
    }
    if (t === "PatternColor") return { type: "pattern" };
    return { type: t !== "" ? t : "unknown" };
};

// Look up a document gradient by name.
CAI.getGradient = function (doc, name) {
    var want = String(name);
    for (var i = 0; i < doc.gradients.length; i++) {
        if (String(doc.gradients[i].name) === want) return doc.gradients[i];
    }
    var names = [];
    for (var j = 0; j < doc.gradients.length; j++) names.push(String(doc.gradients[j].name));
    throw CAI.err("GRADIENT_NOT_FOUND", "No gradient named: " + want,
                  { defined_gradients: names });
};

// Collect every PathItem reachable from an item (path itself, members of a
// compound path, recursive contents of a group).
CAI.collectPaths = function (item, out) {
    var t = CAI.typeName(item);
    if (t === "path") { out.push(item); return out; }
    if (t === "compound") {
        for (var i = 0; i < item.pathItems.length; i++) out.push(item.pathItems[i]);
        return out;
    }
    if (t === "group") {
        var kids = item.pageItems;
        for (var j = 0; j < kids.length; j++) CAI.collectPaths(kids[j], out);
    }
    return out;
};

// Deep path descriptor: anchors/handles in CANVAS coordinates, paint, stroke
// style. `limit` caps the number of anchors returned (default 1000).
CAI.describePathDeep = function (doc, abIndex, p, limit) {
    var d = CAI.describeItem(doc, abIndex, p);
    var cap = (limit === undefined || limit === null) ? 1000 : limit;
    d.closed = false;
    try { d.closed = !!p.closed; } catch (e0) {}
    var n = 0;
    try { n = p.pathPoints.length; } catch (e1) { n = 0; }
    d.anchor_count = n;
    var anchors = [];
    for (var i = 0; i < n && i < cap; i++) {
        var pp = p.pathPoints[i];
        var row = {
            anchor: CAI.fromAI(doc, abIndex, pp.anchor[0], pp.anchor[1]),
            left: CAI.fromAI(doc, abIndex, pp.leftDirection[0], pp.leftDirection[1]),
            right: CAI.fromAI(doc, abIndex, pp.rightDirection[0], pp.rightDirection[1]),
            type: "corner"
        };
        try {
            if (String(pp.pointType) === String(PointType.SMOOTH)) row.type = "smooth";
        } catch (e2) {}
        anchors.push(row);
    }
    d.anchors = anchors;
    d.anchors_truncated = n > cap;
    d.fill = p.filled ? CAI.describeColor(p.fillColor) : { type: "none" };
    d.stroke = p.stroked ? CAI.describeColor(p.strokeColor) : { type: "none" };
    d.stroke_width = p.strokeWidth;
    d.opacity = p.opacity;
    d.cap = null; d.join = null; d.dash = []; d.dash_offset = 0; d.miter_limit = null;
    try { d.cap = CAI.strokeCapName(p.strokeCap); } catch (e3) {}
    try { d.join = CAI.strokeJoinName(p.strokeJoin); } catch (e4) {}
    try {
        var dd = p.strokeDashes;
        var arr = [];
        for (var k = 0; k < dd.length; k++) arr.push(dd[k]);
        d.dash = arr;
    } catch (e5) {}
    try { d.dash_offset = p.strokeDashOffset; } catch (e6) {}
    try { d.miter_limit = p.strokeMiterLimit; } catch (e7) {}
    try { d.clipping = !!p.clipping; } catch (e8) {}
    return d;
};

// Text frame descriptor with full character/paragraph attributes.
CAI.describeTextDeep = function (doc, abIndex, tf) {
    var d = CAI.describeItem(doc, abIndex, tf);
    d.contents_full = "";
    try { d.contents_full = String(tf.contents); } catch (e0) {}
    var attrs = null;
    try { attrs = tf.textRange.characterAttributes; } catch (e1) {}
    d.size = null; d.font = null; d.tracking = null;
    d.leading = null; d.auto_leading = null;
    if (attrs) {
        try { d.size = attrs.size; } catch (e2) {}
        try {
            d.font = { name: String(attrs.textFont.name),
                       family: String(attrs.textFont.family),
                       style: String(attrs.textFont.style) };
        } catch (e3) {}
        try { d.tracking = attrs.tracking; } catch (e4) {}
        try { d.leading = attrs.leading; } catch (e5) {}
        try { d.auto_leading = attrs.autoLeading; } catch (e6) {}
        try { d.fill = CAI.describeColor(attrs.fillColor); } catch (e7) {}
    }
    d.justification = null;
    try {
        d.justification = CAI.justificationName(
            tf.textRange.paragraphAttributes.justification);
    } catch (e8) {}
    d.kind = "point";
    try { if (String(tf.kind) === String(TextType.AREATEXT)) d.kind = "area"; } catch (e9) {}
    return d;
};

// Run fn with UI alerts suppressed (e.g. missing-font dialogs on open),
// restoring the previous interaction level afterwards.
CAI.silently = function (fn) {
    var prev = null;
    try { prev = app.userInteractionLevel; } catch (e) {}
    try { app.userInteractionLevel = UserInteractionLevel.DONTDISPLAYALERTS; } catch (e) {}
    try {
        return fn();
    } finally {
        if (prev !== null) {
            try { app.userInteractionLevel = prev; } catch (e) {}
        }
    }
};
