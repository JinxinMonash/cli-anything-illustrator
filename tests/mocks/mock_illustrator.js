/* Mock Illustrator scripting DOM for PORTABLE tests.
 *
 * Implements just enough of the ExtendScript object model to execute the
 * real JSX templates (prelude + ops) outside Illustrator: documents, layers,
 * page items, path points (anchors/handles), compound paths, clipping
 * groups, gradients, text frames with character/paragraph attributes, fonts,
 * File, enums, saveAs/exportFile stubs, and an SVG reader that models
 * matplotlib exports (svg.fonttype='none').
 * State persists across processes via $MOCK_AI_STATE so multi-command CLI
 * workflows behave like one Illustrator session.
 *
 * Mock approximations (documented, asserted only to bbox precision):
 *  - Path bounds are the hull of anchors+handles, not true Bezier extremes.
 *  - Rotation transforms path points exactly; for non-path items it rotates
 *    the bounding-box corners and takes the new bbox.
 *  - doc.pageItems descends into compound paths (real AI exposes members
 *    via doc.pathItems only).
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

function RGBColor() { this.typename = "RGBColor"; this.red = 0; this.green = 0; this.blue = 0; }
function CMYKColor() { this.typename = "CMYKColor"; this.cyan = 0; this.magenta = 0; this.yellow = 0; this.black = 0; }
function GrayColor() { this.typename = "GrayColor"; this.gray = 0; }
function NoColor() { this.typename = "NoColor"; }
function GradientColor() {
    this.typename = "GradientColor";
    this.gradient = null;
    this.angle = 0;
    this.origin = [0, 0];
    this.length = 100;
    this.hiliteAngle = 0;
    this.hiliteLength = 0;
}

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
const StrokeCap = {
    BUTTENDCAP: "StrokeCap.BUTTENDCAP",
    ROUNDENDCAP: "StrokeCap.ROUNDENDCAP",
    PROJECTINGENDCAP: "StrokeCap.PROJECTINGENDCAP",
};
const StrokeJoin = {
    MITERENDJOIN: "StrokeJoin.MITERENDJOIN",
    ROUNDENDJOIN: "StrokeJoin.ROUNDENDJOIN",
    BEVELENDJOIN: "StrokeJoin.BEVELENDJOIN",
};
const PointType = { SMOOTH: "PointType.SMOOTH", CORNER: "PointType.CORNER" };
const GradientType = { LINEAR: "GradientType.LINEAR", RADIAL: "GradientType.RADIAL" };
const TextType = {
    POINTTEXT: "TextType.POINTTEXT",
    AREATEXT: "TextType.AREATEXT",
    PATHTEXT: "TextType.PATHTEXT",
};

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

// ---------------- gradients ----------------
class GradientStop {
    constructor(owner, ramp) {
        this.typename = "GradientStop";
        this._owner = owner;
        this.rampPoint = ramp;
        this.midPoint = 50;
        this.color = new RGBColor();
        this.opacity = 100;
    }
    remove() {
        const i = this._owner._stops.indexOf(this);
        if (i >= 0) this._owner._stops.splice(i, 1);
    }
}
class Gradient {
    constructor(name) {
        this.typename = "Gradient";
        this.name = name || "";
        this.type = GradientType.LINEAR;
        this._stops = [new GradientStop(this, 0), new GradientStop(this, 100)];
        this._stops[1].color.red = 255;
        this._stops[1].color.green = 255;
        this._stops[1].color.blue = 255;
    }
    get gradientStops() {
        const arr = this._stops.slice();
        const self = this;
        arr.add = () => { const s = new GradientStop(self, 100); self._stops.push(s); return s; };
        return arr;
    }
}

// ---------------- path points ----------------
class PathPoint {
    constructor(owner, anchor) {
        this._o = owner;
        this._anchor = [anchor[0], anchor[1]];
        this._left = [anchor[0], anchor[1]];
        this._right = [anchor[0], anchor[1]];
        this._type = PointType.CORNER;
    }
    get anchor() { return this._anchor.slice(); }
    set anchor(v) { this._anchor = [v[0], v[1]]; this._o._recalcFromPts(); }
    get leftDirection() { return this._left.slice(); }
    set leftDirection(v) { this._left = [v[0], v[1]]; this._o._recalcFromPts(); }
    get rightDirection() { return this._right.slice(); }
    set rightDirection(v) { this._right = [v[0], v[1]]; this._o._recalcFromPts(); }
    get pointType() { return this._type; }
    set pointType(v) { this._type = v; }
}

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
    _corners() {
        const b = this._bounds();
        return [[b[0], b[1]], [b[2], b[1]], [b[2], b[3]], [b[0], b[3]]];
    }
    // Apply a point mapping to the item geometry (bbox corners by default).
    _applyPointTransform(f) {
        const cs = this._corners().map(c => f(c[0], c[1]));
        const xs = cs.map(c => c[0]), ys = cs.map(c => c[1]);
        this._b = [Math.min(...xs), Math.max(...ys), Math.max(...xs), Math.min(...ys)];
    }
    translate(dx, dy) { this._applyPointTransform((x, y) => [x + dx, y + dy]); }
    _origin(about) {
        const b = this._bounds();
        if (about === Transformation.CENTER) return [(b[0] + b[2]) / 2, (b[1] + b[3]) / 2];
        return [b[0], b[1]]; // historical mock default: top-left
    }
    _applyScale(o, kx, ky) {
        this._applyPointTransform((x, y) => [o[0] + (x - o[0]) * kx, o[1] + (y - o[1]) * ky]);
    }
    _scaleStrokes(s) { this.strokeWidth *= s; }
    resize(sx, sy, cp, cfp, cfg, csp, lw, about) {
        if (sy === undefined || sy === null) sy = sx;
        const o = this._origin(about);
        this._applyScale(o, sx / 100, sy / 100);
        const lwp = (lw === undefined || lw === null) ? sx : lw;
        this._scaleStrokes(lwp / 100);
    }
    rotate(angle, cp, cfp, cfg, csp, about) {
        const o = this._origin(about === undefined ? Transformation.CENTER : about);
        const rad = angle * Math.PI / 180;
        const cos = Math.cos(rad), sin = Math.sin(rad);
        this._applyPointTransform((x, y) => [
            o[0] + (x - o[0]) * cos - (y - o[1]) * sin,
            o[1] + (x - o[0]) * sin + (y - o[1]) * cos,
        ]);
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
        // Live-Illustrator fidelity (found on 27.5): cross-document
        // duplicate() into a GroupItem raises PARM (1346458189 'MRAP').
        // Only documents and layers are valid cross-document targets.
        if (target && target.typename === "GroupItem") {
            const myDoc = this._document ? this._document() : null;
            const tgtDoc = target._document ? target._document() : null;
            if (myDoc && tgtDoc && myDoc !== tgtDoc) {
                throw new Error("an Illustrator error occurred: 1346458189 ('MRAP')");
            }
        }
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
    _document() {
        let p = this.parentRef;
        while (p && p.typename !== "Document") p = p.parentRef || p.parentDoc || null;
        return p;
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
    constructor() {
        super("PathItem");
        this._pts = [];
        this.closed = false;
        this.strokeCap = StrokeCap.BUTTENDCAP;
        this.strokeJoin = StrokeJoin.MITERENDJOIN;
        this.strokeDashes = [];
        this.strokeDashOffset = 0;
        this.strokeMiterLimit = 4;
    }
    setEntirePath(pts) {
        this._pts = pts.map(p => new PathPoint(this, p));
        this._recalcFromPts();
    }
    get pathPoints() {
        const arr = this._pts.slice();
        const self = this;
        arr.add = () => { const pp = new PathPoint(self, [0, 0]); self._pts.push(pp); return pp; };
        return arr;
    }
    _recalcFromPts() {
        if (!this._pts.length) return;
        const xs = [], ys = [];
        for (const p of this._pts) {
            xs.push(p._anchor[0], p._left[0], p._right[0]);
            ys.push(p._anchor[1], p._left[1], p._right[1]);
        }
        this._b = [Math.min(...xs), Math.max(...ys), Math.max(...xs), Math.min(...ys)];
    }
    _applyPointTransform(f) {
        if (this._pts.length) {
            for (const p of this._pts) {
                p._anchor = f(p._anchor[0], p._anchor[1]);
                p._left = f(p._left[0], p._left[1]);
                p._right = f(p._right[0], p._right[1]);
            }
            this._recalcFromPts();
        } else {
            super._applyPointTransform(f);
        }
    }
    _clone() {
        const c = super._clone();
        c._pts = this._pts.map(p => {
            const pp = new PathPoint(c, p._anchor);
            pp._left = p._left.slice();
            pp._right = p._right.slice();
            pp._type = p._type;
            return pp;
        });
        c.strokeDashes = this.strokeDashes.slice();
        return c;
    }
}
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
        this._attrs = {
            size: 12, textFont: appFonts[0], fillColor: new RGBColor(),
            tracking: 0, leading: 14.4, autoLeading: true,
        };
        this._para = { justification: Justification.LEFT };
        this.textRange = {
            get characterAttributes() { return self._attrs; },
            get paragraphAttributes() { return self._para; }
        };
    }
    get contents() { return this._contents; }
    set contents(v) { this._contents = String(v); this._reflow(); }
    get kind() { return this._kind === "area" ? TextType.AREATEXT : TextType.POINTTEXT; }
    get textPath() {
        const self = this;
        return {
            get width() { return self._b[2] - self._b[0]; },
            set width(w) { self._b[2] = self._b[0] + w; },
            get height() { return self._b[1] - self._b[3]; },
            set height(h) { self._b[3] = self._b[1] - h; },
        };
    }
    _reflow() {
        const w = Math.max(4, this._contents.length * this._attrs.size * 0.55);
        const h = this._attrs.size * 1.2;
        if (this._kind === "point") {
            this._b = [this._anchor[0], this._anchor[1] + this._attrs.size,
                       this._anchor[0] + w, this._anchor[1] + this._attrs.size - h];
        }
    }
    _applyPointTransform(f) {
        super._applyPointTransform(f);
        this._anchor = f(this._anchor[0], this._anchor[1]);
    }
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
    constructor() { super("GroupItem"); this.children = []; this.clipped = false; }
    _bounds() {
        if (!this.children.length) return [0, 0, 0, 0];
        if (this.clipped) {
            const cl = this.children.find(c => c.clipping);
            if (cl) return cl._bounds();
        }
        const bs = this.children.map(c => c._bounds());
        return [Math.min(...bs.map(b => b[0])), Math.max(...bs.map(b => b[1])),
                Math.max(...bs.map(b => b[2])), Math.min(...bs.map(b => b[3]))];
    }
    _applyPointTransform(f) { this.children.forEach(c => c._applyPointTransform(f)); }
    _applyScale(o, kx, ky) {
        this.children.forEach(c => {
            c._applyScale(o, kx, ky);
            if (c instanceof TextFrame) c._attrs.size *= (kx + ky) / 2;
        });
    }
    _scaleStrokes(s) { this.children.forEach(c => c._scaleStrokes(s)); }
    get pageItems() { return this.children.slice(); }
    _clone() {
        const c = new this.constructor();
        Object.assign(c, { name: this.name, locked: this.locked, hidden: this.hidden,
                           opacity: this.opacity, clipped: this.clipped,
                           uuid: nextUuid(), parentRef: null });
        c.children = this.children.map(ch => { const k = ch._clone(); k.parentRef = c; return k; });
        return c;
    }
}
class CompoundPathItem extends Group {
    constructor() { super(); this.typename = "CompoundPathItem"; }
    get pathItems() { return this.children.filter(c => c.typename === "PathItem"); }
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
        this.compoundPathItems = {
            add() { const c = new CompoundPathItem(); c.parentRef = self; self.items.unshift(c); return c; }
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
        this.gradientList = [];
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
    get gradients() {
        const arr = this.gradientList.slice();
        const self = this;
        arr.add = function () {
            const g = new Gradient("Unnamed gradient " + (self.gradientList.length + 1));
            self.gradientList.push(g);
            return g;
        };
        arr.getByName = function (n) {
            const g = self.gradientList.find(x => x.name === n);
            if (!g) throw new Error("no such element");
            return g;
        };
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
function serColor(c) {
    if (!c) return null;
    if (c.typename === "GradientColor") {
        return { k: "gradient", name: c.gradient ? c.gradient.name : null,
                 angle: c.angle, origin: c.origin, length: c.length };
    }
    if (c.typename === "CMYKColor") return { k: "cmyk", v: [c.cyan, c.magenta, c.yellow, c.black] };
    if (c.typename === "GrayColor") return { k: "gray", v: c.gray };
    if (c.typename === "NoColor") return { k: "none" };
    return { k: "rgb", v: [c.red || 0, c.green || 0, c.blue || 0] };
}
function desColor(d, gmap) {
    if (!d) return null;
    if (d.k === "gradient") {
        const gc = new GradientColor();
        gc.gradient = (gmap && gmap[d.name]) || new Gradient(d.name);
        gc.angle = d.angle || 0;
        gc.origin = d.origin || [0, 0];
        if (d.length !== undefined && d.length !== null) gc.length = d.length;
        return gc;
    }
    if (d.k === "cmyk") {
        const c = new CMYKColor();
        [c.cyan, c.magenta, c.yellow, c.black] = d.v;
        return c;
    }
    if (d.k === "gray") { const g = new GrayColor(); g.gray = d.v; return g; }
    if (d.k === "none") return new NoColor();
    const r = new RGBColor();
    [r.red, r.green, r.blue] = d.v;
    return r;
}
function serializeItem(it) {
    const base = { t: it.typename, name: it.name, uuid: it.uuid, b: it._b,
                   locked: it.locked, hidden: it.hidden, opacity: it.opacity,
                   clipping: it.clipping, strokeWidth: it.strokeWidth,
                   filled: it.filled, stroked: it.stroked,
                   fill: serColor(it.fillColor), stroke: serColor(it.strokeColor) };
    if (it instanceof TextFrame) {
        base.contents = it._contents; base.anchor = it._anchor; base.kind = it._kind;
        base.size = it._attrs.size; base.font = it._attrs.textFont ? it._attrs.textFont.name : null;
        base.tracking = it._attrs.tracking; base.leading = it._attrs.leading;
        base.autoLeading = it._attrs.autoLeading;
        base.tfill = serColor(it._attrs.fillColor);
        base.justification = it._para.justification;
    }
    if (it instanceof PathItem) {
        base.closed = it.closed;
        base.pts = it._pts.map(p => ({ a: p._anchor, l: p._left, r: p._right, pt: p._type }));
        base.cap = it.strokeCap; base.join = it.strokeJoin;
        base.dashes = it.strokeDashes; base.dashOffset = it.strokeDashOffset;
        base.miter = it.strokeMiterLimit;
    }
    if (it instanceof Group) {
        base.children = it.children.map(serializeItem);
        base.clipped = it.clipped;
    }
    if (it instanceof PlacedItem) base.file = it._file ? it._file.fsName : null;
    return base;
}
function deserializeItem(d, gmap) {
    let it;
    if (d.t === "TextFrame") {
        it = new TextFrame();
        it._contents = d.contents || ""; it._anchor = d.anchor || [0, 0]; it._kind = d.kind || "point";
        it._attrs.size = d.size || 12;
        it._attrs.textFont = appFonts.find(f => f.name === d.font) || appFonts[0];
        it._attrs.tracking = d.tracking || 0;
        it._attrs.leading = (d.leading === undefined || d.leading === null) ? 14.4 : d.leading;
        it._attrs.autoLeading = (d.autoLeading === undefined) ? true : d.autoLeading;
        if (d.tfill) it._attrs.fillColor = desColor(d.tfill, gmap);
        if (d.justification) it._para.justification = d.justification;
    } else if (d.t === "GroupItem" || d.t === "CompoundPathItem") {
        it = (d.t === "CompoundPathItem") ? new CompoundPathItem() : new Group();
        it.clipped = !!d.clipped;
        it.children = (d.children || []).map(c => { const k = deserializeItem(c, gmap); k.parentRef = it; return k; });
    } else if (d.t === "PlacedItem") {
        it = new PlacedItem();
        if (d.file) it._file = new MockFile(d.file);
    } else if (d.t === "RasterItem") { it = new RasterItem(); }
    else if (d.t === "SymbolItem") { it = new SymbolItem(); }
    else {
        it = new PathItem();
        it.closed = !!d.closed;
        if (d.pts) {
            it._pts = d.pts.map(q => {
                const pp = new PathPoint(it, q.a);
                pp._left = q.l.slice(); pp._right = q.r.slice();
                pp._type = q.pt || PointType.CORNER;
                return pp;
            });
        }
        if (d.cap) it.strokeCap = d.cap;
        if (d.join) it.strokeJoin = d.join;
        if (d.dashes) it.strokeDashes = d.dashes.slice();
        if (d.dashOffset !== undefined && d.dashOffset !== null) it.strokeDashOffset = d.dashOffset;
        if (d.miter !== undefined && d.miter !== null) it.strokeMiterLimit = d.miter;
    }
    Object.assign(it, { name: d.name, uuid: d.uuid, locked: d.locked, hidden: d.hidden,
                        opacity: d.opacity, clipping: d.clipping, strokeWidth: d.strokeWidth,
                        filled: d.filled, stroked: d.stroked });
    it.fillColor = desColor(d.fill, gmap);
    it.strokeColor = desColor(d.stroke, gmap);
    it._b = d.b;
    if (parseInt(d.uuid, 10) > uuidCounter) uuidCounter = parseInt(d.uuid, 10);
    return it;
}
function serializeGradient(g) {
    return {
        name: g.name, type: g.type,
        stops: g._stops.map(s => ({ ramp: s.rampPoint, mid: s.midPoint,
                                    color: serColor(s.color), opacity: s.opacity })),
    };
}
function deserializeGradient(d) {
    const g = new Gradient(d.name);
    g.type = d.type || GradientType.LINEAR;
    g._stops = (d.stops || []).map(s => {
        const st = new GradientStop(g, s.ramp);
        st.midPoint = (s.mid === undefined || s.mid === null) ? 50 : s.mid;
        st.color = desColor(s.color) || new RGBColor();
        st.opacity = (s.opacity === undefined || s.opacity === null) ? 100 : s.opacity;
        return st;
    });
    if (g._stops.length < 2) {
        g._stops = [new GradientStop(g, 0), new GradientStop(g, 100)];
    }
    return g;
}
function serializeDoc(doc) {
    return {
        name: doc.name, path: doc.fullNameFile ? doc.fullNameFile.fsName : null,
        saved: doc.saved, cs: doc.documentColorSpace,
        artboards: doc.artboardList,
        gradients: doc.gradientList.map(serializeGradient),
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
    doc.gradientList = (d.gradients || []).map(deserializeGradient);
    const gmap = {};
    for (const g of doc.gradientList) gmap[g.name] = g;
    doc.layerList = d.layers.map(l => {
        const ly = new Layer(l.name);
        ly._doc = doc;
        ly.visible = l.visible; ly.locked = l.locked; ly.printable = l.printable;
        ly.items = l.items.map(i => { const it = deserializeItem(i, gmap); it.parentRef = ly; return it; });
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
            app, $, File: MockFile, RGBColor, CMYKColor, GrayColor, NoColor,
            GradientColor, TextFont,
            DocumentColorSpace, ElementPlacement, SaveOptions, ExportType,
            Transformation, ZOrderMethod, Justification, UserInteractionLevel,
            SVGFontSubsetting, SVGFontType, StrokeCap, StrokeJoin, PointType,
            GradientType, TextType, ExportOptionsPNG24, ExportOptionsSVG,
            PDFSaveOptions, IllustratorSaveOptions,
        });
    },
    loadState, saveState,
};
