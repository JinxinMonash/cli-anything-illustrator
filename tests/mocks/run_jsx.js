/* Executes a JSX op file against the mock Illustrator DOM.
 * argv: runner.applescript path (ignored), jsx path, app name, timeout. */
"use strict";
const fs = require("fs");
const vm = require("vm");
const path = require("path");
const mock = require(path.join(__dirname, "mock_illustrator.js"));

const mode = process.env.MOCK_OSASCRIPT_MODE || "ok";
if (mode === "denied") {
    process.stderr.write("execution error: Not authorized to send Apple events to Adobe Illustrator. (-1743)\n");
    process.exit(1);
}
if (mode === "appmissing") {
    process.stderr.write("execution error: Can't get application \"Adobe Illustrator\". (-2700)\n");
    process.exit(1);
}
if (mode === "nosession") {
    process.stderr.write("execution error: Adobe Illustrator got an error: connection is invalid. (-609)\n");
    process.exit(1);
}
if (mode === "timeout") {
    setInterval(() => {}, 1000); // hang until killed
} else if (mode === "garbage") {
    process.stdout.write("not json at all\n");
    process.exit(0);
} else {
    const jsxPath = process.argv[3];
    const src = fs.readFileSync(jsxPath, "utf8");
    mock.installGlobals(globalThis);
    mock.loadState();
    let result;
    try {
        result = vm.runInThisContext(src, { filename: jsxPath });
    } catch (e) {
        process.stderr.write("execution error: " + (e && e.message) + "\n");
        process.exit(1);
    }
    mock.saveState();
    process.stdout.write(String(result) + "\n");
}
