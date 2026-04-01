# core/source.py
#
# Source interface.
# A Source reads data from a skill's database or an external system
# and yields rows as dicts. The workflow engine calls read() to pull
# data into the pipeline.
#
# Skills implement this by subclassing Source and providing read().

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Iterator


class Source(ABC):
    """
    Base class for workflow data sources.

    A Source yields rows of data as dicts. Each row must have at
    minimum a "record_id" key (linking to core.db records.id) and
    the fields the downstream transforms/sinks expect.

    Skills declare sources in skill.toml:
        [[skill.provides]]
        type = "source"
        name = "crm.contacts"
        class = "CrmSource"

    The engine instantiates the class and calls read() with the
    config from the workflow YAML's source section.
    """

    @abstractmethod
    def read(self, **config: Any) -> Iterator[dict]:
        """
        Yield rows of data as dicts.

        Config comes from the workflow YAML source section:
            source:
              skill: crm
              type: contacts
              filter:
                segment: gtm-agencies

        The skill receives type, filter, and any other keys as kwargs.
        Yield dicts with string keys and simple values (str, int, float, bool, None).
        Must include "record_id" in each row.
        """
        ...
