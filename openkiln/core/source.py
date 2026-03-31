# core/source.py
#
# Source base class.
# A Source produces rows of data from an external system
# or file. Subclasses implement .read() -> Iterator[Row].
# Built-in sources: CSV, JSON, database query.
