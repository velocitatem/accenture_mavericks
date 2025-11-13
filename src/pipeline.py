from typing import Any, Callable, List


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
