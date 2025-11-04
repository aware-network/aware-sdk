"""Console entrypoint for the aware-test-runner package."""

from __future__ import annotations

import sys
from typing import List, Optional

from .test_runner import main as runner_main


def main(argv: Optional[List[str]] = None) -> int:
    """CLI entry point mirroring the legacy aware-tests command."""
    return runner_main(argv)


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
