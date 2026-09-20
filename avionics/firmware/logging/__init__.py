"""DATA LOGGER: schema-driven validation, timestamp handling, CSV / JSON-lines log writers and a tolerant log reader.

Always import it as `avionics.firmware.logging` (the package name matches the requested folder layout). Never put
`avionics/firmware` itself on sys.path, or this package would shadow Python's standard `logging` module.
"""
