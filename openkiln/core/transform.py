# core/transform.py
#
# Transform interface.
# A Transform processes a row and returns a modified row (or None
# to drop it). The workflow engine calls apply() for each row in
# the pipeline.
#
# Skills implement this by subclassing Transform and providing apply().

from __future__ import annotations

from abc import ABC, abstractmethod


class Transform(ABC):
    """
    Base class for workflow transforms.

    A Transform receives a row dict and returns a modified row dict.
    Return None to drop the row from the pipeline (filtering).

    Transforms are stateless per-row operations. If the transform
    calls an external API, it should handle errors gracefully and
    either return the row unchanged or return None to skip it.

    Skills declare transforms in skill.toml:
        [[skill.provides]]
        type = "transform"
        name = "orbisearch.validate"
        class = "OrbiSearchTransform"

    The engine instantiates the class once and calls apply() for
    each row from the source.
    """

    @abstractmethod
    def apply(self, row: dict) -> dict | None:
        """
        Transform a single row.

        Args:
            row: dict with string keys from the source or previous transform.

        Returns:
            Modified row dict with any new fields added, or
            None to drop this row from the pipeline.
        """
        ...
