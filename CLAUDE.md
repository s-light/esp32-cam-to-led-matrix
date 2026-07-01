# Notes for Claude Code

## Researching CircuitPython board pinouts

When comparing pin mappings between CircuitPython boards (e.g. to check
whether an example targeting one board will run on another), fetch the raw
`pins.c` and `mpconfigboard.h` directly from the `adafruit/circuitpython`
GitHub repo (`ports/espressif/boards/<board_id>/`) instead of relying on
`WebFetch`'s summarized output.

`WebFetch` runs the page through a smaller model before returning it, and on
at least one occasion it implied a board exposed a pin name (`SSCB_I2C`) that
wasn't actually present in the board's pins table. Pulling the raw file with
`curl`/`Bash` and reading it directly avoids that failure mode.
