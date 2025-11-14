from typing import Any, Callable, List
from core.validation import validate_data


class Pipeline:
    """Simple AI processing pipeline."""

    def __init__(self):
        self.steps: List[Callable] = []

    def add(self, func: Callable):
        """Add a processing step."""
        self.steps.append(func)
        return self

    def run(self, data: Any) -> Any:
        """Execute pipeline on data."""
        for step in self.steps:
            data = step(data)
        return data


# Global instance
pipeline = Pipeline()

# extract text from pdf
# extract structure from text
# validate structure of each document
# compare documents bwrtween each other and create a -diff- report
# show differences in a nice way

pipeline.add(validate_data) # takes a dict as input
