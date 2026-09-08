(function () {
    try {
        var P = CAI.parse(__PARAMS_JSON);
        var doc = CAI.resolveDoc(P);
        var ly = CAI.getLayer(doc, P.name, false);
        var U = P.updates || {};
        if (U.visible !== undefined && U.visible !== null) ly.visible = !!U.visible;
        if (U.locked !== undefined && U.locked !== null) ly.locked = !!U.locked;
        if (U.printable !== undefined && U.printable !== null) ly.printable = !!U.printable;
        if (U.new_name) ly.name = String(U.new_name);
        return CAI.ok({ name: ly.name, visible: ly.visible, locked: ly.locked,
                        printable: ly.printable });
    } catch (e) { return CAI.failFromException(e); }
})();
