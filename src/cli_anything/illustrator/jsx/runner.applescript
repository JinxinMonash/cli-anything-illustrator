-- cli-anything-illustrator AppleScript runner TEMPLATE.
-- __CAI_APP_NAME__ is replaced with the discovered application name (as an
-- escaped string literal) BEFORE the script is written to disk. The name must
-- be a compile-time literal: with a runtime variable in the `tell` block,
-- AppleScript cannot load Illustrator's scripting dictionary and the term
-- `do javascript` fails to resolve (first live-Mac defect, fixed in 0.9.1).
-- argv: 1 = POSIX path to a UTF-8 JSX file, 2 = timeout in seconds.
-- The JSX evaluates to a single JSON string (the result envelope), which
-- becomes this script's return value and is printed by osascript on stdout.
on run argv
    set jsxPath to item 1 of argv
    set timeoutSecs to (item 2 of argv) as integer
    set jsxFile to POSIX file jsxPath
    set jsxSrc to read jsxFile as «class utf8»
    with timeout of timeoutSecs seconds
        tell application "__CAI_APP_NAME__"
            do javascript jsxSrc
        end tell
    end timeout
end run
