# core/sink.py
#
# Sink interface.
# A Sink consumes rows and writes them to an external system or
# database. The workflow engine calls write() with batches of rows
# that survived all transforms and filters.
#
# Skills implement this by subclassing Sink and providing write().

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class Sink(ABC):
    """
    Base class for workflow sinks.

    A Sink receives a list of row dicts and writes them to a
    destination (database, external API, file, etc). Returns a
    summary dict with at minimum {"written": int}.

    Skills declare sinks in skill.toml:
        [[skill.provides]]
        type = "sink"
        name = "smartlead.push"
        class = "SmartleadSink"

    The engine instantiates the class and calls write() with the
    config from the workflow YAML's sink section.
    """

    @abstractmethod
    def write(self, rows: list[dict], **config: Any) -> dict:
        """
        Write rows to the destination.

        Args:
            rows: list of row dicts from the pipeline.
            **config: additional config from the workflow YAML sink section
                      (e.g. action="push", campaign_id="12345").

        Returns:
            Summary dict, e.g. {"written": 42, "skipped": 3}.
        """
        ...
