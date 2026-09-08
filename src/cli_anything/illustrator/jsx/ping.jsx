(function () {
    try {
        var P = CAI.parse(__PARAMS_JSON);
        return CAI.ok({ pong: true, echo: P.echo === undefined ? null : P.echo,
                        version: String(app.version) });
    } catch (e) { return CAI.failFromException(e); }
})();
