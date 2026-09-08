/* Mock Illustrator scripting DOM for PORTABLE tests.
 *
 * Implements just enough of the ExtendScript object model to execute the
 * real JSX templates (prelude + ops) outside Illustrator: documents, layers,
 * page items, text frames, fonts, File, enums, saveAs/exportFile stubs, and
 * an SVG reader that models matplotlib exports (svg.fonttype='none').
 * State persists across processes via $MOCK_AI_STATE so multi-command CLI
 * workflows behave like one Illustrator session.
 *
 * THIS IS A MOCK: passing here is NOT evidence of live Illustrator behaviour
 * (see tests/integration + scripts/run_mac_validation.sh for that).
 */
"use strict";
const fs = require("fs");
const path = require("path");

let uuidCounter = 1000;
function nextUuid() { return String(++uuidCounter); }

// ---------------- File & colours & enums ----------------
function MockFile(p) {
    this.fsName = path.resolve(String(p));
}
Object.defineProperty(MockFile.prototype, "exists", {
    get() { return fs.existsSync(this.fsName); }
});

function RGBColor() { this.red = 0; this.green = 0; this.blue = 0; }
function CMYKColor() { this.cyan = 0; this.magenta = 0; this.yellow = 0; this.black = 0; }

const DocumentColorSpace = { RGB: "DocumentColorSpace.RGB", CMYK: "DocumentColorSpace.CMYK" };
const ElementPlacement = { PLACEATEND: "end", PLACEATBEGINNING: "begin" };
const SaveOptions = { SAVECHANGES: "save", DONOTSAVECHANGES: "nosave", PROMPTTOSAVECHANGES: "prompt" };
const ExportType = { PNG24: "png24", SVG: "svg" };
const Transformation = { TOPLEFT: "topleft", CENTER: "center", DOCUMENTORIGIN: "origin" };
const ZOrderMethod = { BRINGTOFRONT: "front", SENDTOBACK: "back" };
const Justification = { LEFT: "left", CENTER: "center", RIGHT: "right" };
const UserInteractionLevel = { DONTDISPLAYALERTS: "dont", DISPLAYALERTS: "display" };
const SVGFontSubsetting = { None: "none", GLYPHSUSED: "glyphs" };
const SVGFontType = { SVGFONT: "svgfont", OUTLINEFONT: "outline" };

function ExportOptionsPNG24() {
    this.antiAliasing = true; this.transparency = true;
    this.artBoardClipping = false; this.horizontalScale = 100; this.verticalScale = 100;
}
function ExportOptionsSVG() {
    this.embedRasterImages = false; this.fontSubsetting = SVGFontSubsetting.GLYPHSUSED;
    this.fontType = SVGFontType.SVGFONT;
}
function PDFSaveOptions() { this.preserveEditability = true; this.viewAfterSaving = false; }
function IllustratorSaveOptions() { this.pdfCompatible = true; this.embedICCProfile = false; this.compressed = false; }

function TextFont(name, family, style) { this.name = name; this.family = family; this.style = style; }

// ---------------- items ----------------
class Item {
    constructor(typename) {
        this.typename = typename;
        this.name = "";
        this.locked = false;
        this.hidden = false;
        this.opacity = 100;
        this.uuid = nextUuid();
        this.parentRef = null;
        this._b = [0, 0, 0, 0]; // [L, T, R, B] y-up
        this.clipping = false;
        this.filled = false; this.stroked = false;
        this.fillColor = null; this.strokeColor = null; this.strokeWidth = 1;
    }
    get parent() { return this.parentRef; }
    get layer() {
        let p = this.parentRef;
        while (p && p.typename !== "Layer") p = p.parentRef || null;
        return p;
    }
    get visibleBounds() { return this._bounds(); }
    get geometricBounds() { return this._bounds(); }
    _bounds() { return this._b.slice(); }
    get position() { const b = this._bounds(); return [b[0], b[1]]; }
    set position(pt) {
        const b = this._bounds();
        this.translate(pt[0] - b[0], pt[1] - b[1]);
    }
    translate(dx, dy) { this._b = [this._b[0] + dx, this._b[1] + dy, this._b[2] + dx, this._b[3] + dy]; }
    _scaleAbout(ox, oy, s) {
        this._b = [ox + (this._b[0] - ox) * s, oy + (this._b[1] - oy) * s,
                   ox + (this._b[2] - ox) * s, oy + (this._b[3] - oy) * s];
        this.strokeWidth *= s;
    }
    resize(sx, sy, cp, cfp, cfg, csp, lw, about) {
        const b = this._bounds();
        this._scaleAbout(b[0], b[1], sx / 100);
    }
    _container(target) {
        if (target instanceof Layer) return target.items;
        if (target instanceof Group) return target.children;
        throw new Error("bad move target");
    }
    _detach() {
        if (!this.parentRef) return;
        const arr = (this.parentRef instanceof Layer) ? this.parentRef.items : this.parentRef.children;
        const i = arr.indexOf(this);
        if (i >= 0) arr.splice(i, 1);
    }
    move(target, placement) {
        this._detach();
        const arr = this._container(target);
        if (placement === ElementPlacement.PLACEATBEGINNING) arr.unshift(this); else arr.push(this);
        this.parentRef = target;
        return this;
    }
    duplicate(target, placement) {
        const clone = this._clone();
        const arr = this._container(target);
        if (placement === ElementPlacement.PLACEATBEGINNING) arr.unshift(clone); else arr.push(clone);
        clone.parentRef = target;
        return clone;
    }
    _clone() {
        const c = new this.constructor();
        Object.assign(c, this, { uuid: nextUuid(), parentRef: null });
        c._b = this._b.slice();
        return c;
    }
    remove() { this._detach(); this.parentRef = null; }
    zOrder(method) {
        const arr = (this.parentRef instanceof Layer) ? this.parentRef.items : this.parentRef.children;
        const i = arr.indexOf(this);
        arr.splice(i, 1);
        if (method === ZOrderMethod.BRINGTOFRONT) arr.unshift(this); else arr.push(this);
    }
}

class PathItem extends Item {
    constructor() { super("PathItem"); }
    setEntirePath(pts) {
        const xs = pts.map(p => p[0]), ys = pts.map(p => p[1]);
        this._b = [Math.min(...xs), Math.max(...ys), Math.max(...xs), Math.min(...ys)];
    }
}
class CompoundPathItem extends Item { constructor() { super("CompoundPathItem"); } }
class RasterItem extends Item { constructor() { super("RasterItem"); } }
class SymbolItem extends Item { constructor() { super("SymbolItem"); } }
class PlacedItem extends Item {
    constructor() { super("PlacedItem"); this._file = null; }
    get file() {
        if (!this._file || !this._file.exists) throw new Error("missing link");
        return this._file;
    }
    set file(f) {
        this._file = f;
        this._b = [0, 100, 100, 0];
        const dims = trySvgDims(f.fsName);
        if (dims) this._b = [0, dims.h, dims.w, 0];
    }
}
class TextFrame extends Item {
    constructor() {
        super("TextFrame");
        this._contents = "";
        this._anchor = [0, 0];
        this._kind = "point";
        const self = this;
        this._attrs = { size: 12, textFont: appFonts[0], fillColor: new RGBColor() };
        this._para = { justification: Justification.LEFT };
        this.textRange = {
            get characterAttributes() { return self._attrs; },
            get paragraphAttributes() { return self._para; }
        };
    }
    get contents() { return this._contents; }
    set contents(v) { this._contents = String(v); this._reflow(); }
    _reflow() {
        const w = Math.max(4, this._contents.length * this._attrs.size * 0.55);
        const h = this._attrs.size * 1.2;
        if (this._kind === "point") {
            this._b = [this._anchor[0], this._anchor[1] + this._attrs.size,
                       this._anchor[0] + w, this._anchor[1] + this._attrs.size - h];
        }
    }
    translate(dx, dy) { super.translate(dx, dy); this._anchor = [this._anchor[0] + dx, this._anchor[1] + dy]; }
    _clone() {
        const c = super._clone();
        c._contents = this._contents;
        c._anchor = this._anchor.slice();
        c._attrs = Object.assign({}, this._attrs);
        c._para = Object.assign({}, this._para);
        const self2 = c;
        c.textRange = {
            get characterAttributes() { return self2._attrs; },
            get paragraphAttributes() { return self2._para; }
        };
        return c;
    }
}
class Group extends Item {
    constructor() { super("GroupItem"); this.children = []; }
    _bounds() {
        if (!this.children.length) return [0, 0, 0, 0];
        const bs = this.children.map(c => c._bounds());
        return [Math.min(...bs.map(b => b[0])), Math.max(...bs.map(b => b[1])),
                Math.max(...bs.map(b => b[2])), Math.min(...bs.map(b => b[3]))];
    }
    translate(dx, dy) { this.children.forEach(c => c.translate(dx, dy)); }
    _scaleAbout(ox, oy, s) {
        this.children.forEach(c => {
            c._scaleAbout(ox, oy, s);
            if (c instanceof TextFrame) c._attrs.size *= s;
        });
    }
    resize(sx) { const b = this._bounds(); this._scaleAbout(b[0], b[1], sx / 100); }
    get pageItems() { return this.children.slice(); }
    _clone() {
        const c = new Group();
        Object.assign(c, { name: this.name, locked: this.locked, hidden: this.hidden,
                           opacity: this.opacity, uuid: nextUuid(), parentRef: null });
        c.children = this.children.map(ch => { const k = ch._clone(); k.parentRef = c; return k; });
        return c;
    }
}

class Layer {
    constructor(name) {
        this.typename = "Layer";
        this.name = name || "Layer 1";
        this.visible = true; this.locked = false; this.printable = true;
        this.items = [];   // direct children, index 0 = front
        this.parentRef = null;
        const self = this;
        this.groupItems = {
            add() { const g = new Group(); g.parentRef = self; self.items.unshift(g); return g; }
        };
    }
    _descend(list, out) {
        for (const it of list) { out.push(it); if (it instanceof Group) this._descend(it.children, out); }
        return out;
    }
    get pageItems() { return this._descend(this.items, []); }
    get textFrames() { return this.pageItems.filter(i => i.typename === "TextFrame"); }
    get layers() { return []; }
    remove() {
        const i = this._doc.layerList.indexOf(this);
        if (i >= 0) this._doc.layerList.splice(i, 1);
    }
}

// ---------------- document ----------------
let untitledCounter = 0;

class Document {
    constructor(cs, w, h) {
        this.typename = "Document";
        this.name = "Untitled-" + (++untitledCounter);
        this.fullNameFile = null;
        this.saved = false; // Illustrator: false == has unsaved changes
        this.documentColorSpace = cs || DocumentColorSpace.RGB;
        this.layerList = [];
        this.artboardList = [{ name: "Artboard 1", artboardRect: [0, h || 792, w || 612, 0] }];
        this._activeAb = 0;
        const ly = new Layer("Layer 1");
        ly._doc = this;
        this.layerList.push(ly);
        this.activeLayer = ly;
    }
    get fullName() { return this.fullNameFile; }
    get width() { const r = this.artboardList[0].artboardRect; return r[2] - r[0]; }
    get height() { const r = this.artboardList[0].artboardRect; return r[1] - r[3]; }
    get layers() {
        const arr = this.layerList.slice();
        const self = this;
        arr.add = function () {
            const ly = new Layer("Layer " + (self.layerList.length + 1));
            ly._doc = self;
            self.layerList.unshift(ly);
            return ly;
        };
        return arr;
    }
    get artboards() {
        const arr = this.artboardList.slice();
        const self = this;
        arr.setActiveArtboardIndex = function (i) { self._activeAb = i; };
        return arr;
    }
    _all() { const out = []; for (const ly of this.layerList) ly._descend(ly.items, out); return out; }
    get pageItems() { return this._all(); }
    get pathItems() {
        const arr = this._all().filter(i => i.typename === "PathItem");
        const self = this;
        function put(item) { item.parentRef = self.activeLayer; self.activeLayer.items.unshift(item); return item; }
        arr.rectangle = (top, left, w, h) => { const p = new PathItem(); p._b = [left, top, left + w, top - h]; return put(p); };
        arr.roundedRectangle = (top, left, w, h) => arr.rectangle(top, left, w, h);
        arr.ellipse = (top, left, w, h) => arr.rectangle(top, left, w, h);
        arr.polygon = (cx, cy, r) => { const p = new PathItem(); p._b = [cx - r, cy + r, cx + r, cy - r]; return put(p); };
        arr.star = (cx, cy, r) => { const p = new PathItem(); p._b = [cx - r, cy + r, cx + r, cy - r]; return put(p); };
        arr.add = () => put(new PathItem());
        return arr;
    }
    get textFrames() {
        const arr = this._all().filter(i => i.typename === "TextFrame");
        const self = this;
        arr.pointText = (pos) => {
            const t = new TextFrame();
            t._kind = "point"; t._anchor = [pos[0], pos[1]]; t._reflow();
            t.parentRef = self.activeLayer; self.activeLayer.items.unshift(t);
            return t;
        };
        arr.areaText = (rectPath) => {
            const t = new TextFrame();
            t._kind = "area"; t._b = rectPath._bounds();
            rectPath.remove();
            t.parentRef = self.activeLayer; self.activeLayer.items.unshift(t);
            return t;
        };
        return arr;
    }
    get placedItems() {
        const arr = this._all().filter(i => i.typename === "PlacedItem");
        const self = this;
        arr.add = () => { const p = new PlacedItem(); p.parentRef = self.activeLayer; self.activeLayer.items.unshift(p); return p; };
        return arr;
    }
    get rasterItems() { return this._all().filter(i => i.typename === "RasterItem"); }
    get compoundPathItems() { return this._all().filter(i => i.typename === "CompoundPathItem"); }
    get symbolItems() { return this._all().filter(i => i.typename === "SymbolItem"); }
    get legacyTextItems() { return []; }
    get swatches() { return []; }

    saveAs(file, opts) {
        if (opts instanceof PDFSaveOptions) {
            fs.writeFileSync(file.fsName, "%PDF-1.6 mock\n" + JSON.stringify({ mock: true, doc: serializeDoc(this) }));
        } else {
            fs.writeFileSync(file.fsName, "%!MOCK-AI\n" + JSON.stringify(serializeDoc(this)));
        }
        this.fullNameFile = file;
        this.name = path.basename(file.fsName);
        this.saved = true;
    }
    exportFile(file, type, opts) {
        if (type === ExportType.PNG24) {
            fs.writeFileSync(file.fsName, Buffer.concat([
                Buffer.from([0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a]),
                Buffer.from("MOCKPNG scale=" + (opts ? opts.horizontalScale : 100))]));
        } else {
            fs.writeFileSync(file.fsName,
                '<svg xmlns="http://www.w3.org/2000/svg"><!-- MOCK export fontType=' +
                (opts ? String(opts.fontType) : "?") + ' --></svg>');
        }
    }
    close(saveOpt) {
        if (saveOpt === SaveOptions.SAVECHANGES && this.fullNameFile) this.saveAs(this.fullNameFile, new IllustratorSaveOptions());
        const i = appDocuments.indexOf(this);
        if (i >= 0) appDocuments.splice(i, 1);
    }
}

// ---------------- serialization (state across processes) ----------------
function serializeItem(it) {
    const base = { t: it.typename, name: it.name, uuid: it.uuid, b: it._b,
                   locked: it.locked, hidden: it.hidden, opacity: it.opacity,
                   clipping: it.clipping, strokeWidth: it.strokeWidth,
                   filled: it.filled, stroked: it.stroked };
    if (it instanceof TextFrame) {
        base.contents = it._contents; base.anchor = it._anchor; base.kind = it._kind;
        base.size = it._attrs.size; base.font = it._attrs.textFont ? it._attrs.textFont.name : null;
    }
    if (it instanceof Group) base.children = it.children.map(serializeItem);
    if (it instanceof PlacedItem) base.file = it._file ? it._file.fsName : null;
    return base;
}
function deserializeItem(d) {
    let it;
    if (d.t === "TextFrame") {
        it = new TextFrame();
        it._contents = d.contents || ""; it._anchor = d.anchor || [0, 0]; it._kind = d.kind || "point";
        it._attrs.size = d.size || 12;
        it._attrs.textFont = appFonts.find(f => f.name === d.font) || appFonts[0];
    } else if (d.t === "GroupItem") {
        it = new Group();
        it.children = (d.children || []).map(c => { const k = deserializeItem(c); k.parentRef = it; return k; });
    } else if (d.t === "PlacedItem") {
        it = new PlacedItem();
        if (d.file) it._file = new MockFile(d.file);
    } else if (d.t === "RasterItem") { it = new RasterItem(); }
    else if (d.t === "CompoundPathItem") { it = new CompoundPathItem(); }
    else { it = new PathItem(); }
    Object.assign(it, { name: d.name, uuid: d.uuid, locked: d.locked, hidden: d.hidden,
                        opacity: d.opacity, clipping: d.clipping, strokeWidth: d.strokeWidth,
                        filled: d.filled, stroked: d.stroked });
    it._b = d.b;
    if (parseInt(d.uuid, 10) > uuidCounter) uuidCounter = parseInt(d.uuid, 10);
    return it;
}
function serializeDoc(doc) {
    return {
        name: doc.name, path: doc.fullNameFile ? doc.fullNameFile.fsName : null,
        saved: doc.saved, cs: doc.documentColorSpace,
        artboards: doc.artboardList,
        layers: doc.layerList.map(ly => ({
            name: ly.name, visible: ly.visible, locked: ly.locked, printable: ly.printable,
            items: ly.items.map(serializeItem)
        })),
        active: doc === app.activeDocument
    };
}
function deserializeDoc(d) {
    const doc = new Document(d.cs, 612, 792);
    untitledCounter--; // don't consume numbering for restored docs
    doc.name = d.name;
    doc.saved = d.saved;
    doc.fullNameFile = d.path ? new MockFile(d.path) : null;
    doc.artboardList = d.artboards;
    doc.layerList = d.layers.map(l => {
        const ly = new Layer(l.name);
        ly._doc = doc;
        ly.visible = l.visible; ly.locked = l.locked; ly.printable = l.printable;
        ly.items = l.items.map(i => { const it = deserializeItem(i); it.parentRef = ly; return it; });
        return ly;
    });
    doc.activeLayer = doc.layerList.find(l => !l.locked) || doc.layerList[0];
    return doc;
}

// ---------------- SVG reader (models matplotlib svg.fonttype='none') ------
function trySvgDims(p) {
    try {
        const src = fs.readFileSync(p, "utf8");
        return svgDims(src);
    } catch (e) { return null; }
}
function svgDims(src) {
    const mw = src.match(/<svg[^>]*\bwidth="([\d.]+)(pt|px)?"/);
    const mh = src.match(/<svg[^>]*\bheight="([\d.]+)(pt|px)?"/);
    if (mw && mh) return { w: parseFloat(mw[1]), h: parseFloat(mh[1]) };
    const vb = src.match(/viewBox="[\d.\-]+ [\d.\-]+ ([\d.]+) ([\d.]+)"/);
    if (vb) return { w: parseFloat(vb[1]), h: parseFloat(vb[2]) };
    return null;
}
function openSvg(fsName) {
    const src = fs.readFileSync(fsName, "utf8");
    const dims = svgDims(src) || { w: 300, h: 200 };
    const doc = new Document(DocumentColorSpace.RGB, dims.w, dims.h);
    doc.name = path.basename(fsName);
    doc.saved = true;
    const ly = doc.layerList[0];
    const full = [0, dims.h, dims.w, 0];
    const shapeRe = /<(path|rect|circle|ellipse|line|polyline|polygon)\b/g;
    let m, nShapes = 0;
    while ((m = shapeRe.exec(src)) !== null) nShapes++;
    for (let i = 0; i < nShapes; i++) {
        const p = new PathItem();
        p._b = full.slice(); p.parentRef = ly; ly.items.push(p);
    }
    const textRe = /<text\b[^>]*>([\s\S]*?)<\/text>/g;
    while ((m = textRe.exec(src)) !== null) {
        const t = new TextFrame();
        t._contents = m[1].replace(/<[^>]+>/g, "").trim();
        t._b = [0, 12, Math.max(4, t._contents.length * 6), 0];
        t._anchor = [0, 0];
        t.parentRef = ly; ly.items.push(t);
    }
    const imgRe = /<image\b/g;
    while ((m = imgRe.exec(src)) !== null) {
        const r = new RasterItem(); r._b = full.slice(); r.parentRef = ly; ly.items.push(r);
    }
    return doc;
}

// ---------------- app ----------------
const appFonts = [
    new TextFont("Helvetica", "Helvetica", "Regular"),
    new TextFont("Helvetica-Bold", "Helvetica", "Bold"),
    new TextFont("ArialMT", "Arial", "Regular"),
    new TextFont("Arial-BoldMT", "Arial", "Bold"),
    new TextFont("MyriadPro-Regular", "Myriad Pro", "Regular"),
];
appFonts.getByName = function (n) {
    const f = this.find(x => x.name === n);
    if (!f) throw new Error("no such element");
    return f;
};

const appDocuments = [];
let activeDoc = null;

const app = {
    version: "29.5.0",
    path: "/Applications/Adobe Illustrator MOCK/Adobe Illustrator.app",
    userInteractionLevel: UserInteractionLevel.DISPLAYALERTS,
    get documents() {
        const arr = appDocuments.slice();
        arr.add = (cs, w, h) => {
            const d = new Document(cs, w, h);
            appDocuments.push(d);
            activeDoc = d;
            return d;
        };
        return arr;
    },
    get activeDocument() {
        if (!activeDoc) throw new Error("no active document");
        return activeDoc;
    },
    set activeDocument(d) { activeDoc = d; },
    get textFonts() { return appFonts; },
    open(file) {
        const p = file.fsName;
        if (!fs.existsSync(p)) throw new Error("File not found: " + p);
        let doc;
        const head = fs.readFileSync(p).slice(0, 200).toString("utf8");
        if (head.startsWith("%!MOCK-AI")) {
            const data = JSON.parse(fs.readFileSync(p, "utf8").split("\n").slice(1).join("\n"));
            doc = deserializeDoc(data);
            doc.fullNameFile = new MockFile(p);
            doc.name = path.basename(p);
            doc.saved = true;
        } else if (p.toLowerCase().endsWith(".svg")) {
            doc = openSvg(p);
        } else {
            doc = new Document(DocumentColorSpace.RGB, 300, 200);
            doc.name = path.basename(p);
            doc.saved = true;
            const q = new PathItem(); q._b = [0, 200, 300, 0];
            q.parentRef = doc.layerList[0]; doc.layerList[0].items.push(q);
        }
        appDocuments.push(doc);
        activeDoc = doc;
        return doc;
    },
};

const $ = { locale: "en_US", version: "4.5.5 (mock)" };

// ---------------- state persistence ----------------
const STATE = process.env.MOCK_AI_STATE;
function loadState() {
    if (!STATE || !fs.existsSync(STATE)) return;
    const data = JSON.parse(fs.readFileSync(STATE, "utf8"));
    uuidCounter = data.uuidCounter || uuidCounter;
    untitledCounter = data.untitledCounter || 0;
    for (const d of data.documents || []) {
        const doc = deserializeDoc(d);
        appDocuments.push(doc);
        if (d.active) activeDoc = doc;
    }
    if (!activeDoc && appDocuments.length) activeDoc = appDocuments[appDocuments.length - 1];
}
function saveState() {
    if (!STATE) return;
    fs.writeFileSync(STATE, JSON.stringify({
        uuidCounter, untitledCounter,
        documents: appDocuments.map(serializeDoc),
    }));
}

module.exports = {
    installGlobals(g) {
        Object.assign(g, {
            app, $, File: MockFile, RGBColor, CMYKColor, TextFont,
            DocumentColorSpace, ElementPlacement, SaveOptions, ExportType,
            Transformation, ZOrderMethod, Justification, UserInteractionLevel,
            SVGFontSubsetting, SVGFontType, ExportOptionsPNG24, ExportOptionsSVG,
            PDFSaveOptions, IllustratorSaveOptions,
        });
    },
    loadState, saveState,
};
