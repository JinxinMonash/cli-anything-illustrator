-- cli-anything-illustrator AppleScript runner.
-- argv: 1 = POSIX path to a UTF-8 JSX file, 2 = Illustrator application name,
--       3 = timeout in seconds.
-- Reads the JSX source and evaluates it inside Illustrator via the
-- scripting-dictionary command "do javascript". The JSX is expected to
-- evaluate to a single JSON string (the result envelope), which becomes
-- this script's return value and is printed by osascript on stdout.
on run argv
    set jsxPath to item 1 of argv
    set appName to item 2 of argv
    set timeoutSecs to (item 3 of argv) as integer
    set jsxFile to POSIX file jsxPath
    set jsxSrc to read jsxFile as «class utf8»
    with timeout of timeoutSecs seconds
        tell application appName
            do javascript jsxSrc
        end tell
    end timeout
end run
