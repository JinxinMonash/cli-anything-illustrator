(function () {
    try {
        var P = CAI.parse(__PARAMS_JSON);
        var contains = P.contains ? String(P.contains).toLowerCase() : null;
        var limit = P.limit || 100;
        var out = [];
        var total = app.textFonts.length;
        for (var i = 0; i < total && out.length < limit; i++) {
            var tf = app.textFonts[i];
            var nm = String(tf.name), fam = String(tf.family), st = String(tf.style);
            if (contains &&
                nm.toLowerCase().indexOf(contains) === -1 &&
                fam.toLowerCase().indexOf(contains) === -1) continue;
            out.push({ name: nm, family: fam, style: st });
        }
        return CAI.ok({ total_installed: total, returned: out.length, fonts: out });
    } catch (e) { return CAI.failFromException(e); }
})();
