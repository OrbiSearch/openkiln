# core/sink.py
#
# Sink base class.
# A Sink consumes rows and writes them to an external
# system. Subclasses implement .write(rows) -> Result.
# Built-in sinks: CSV, JSON, database insert.
