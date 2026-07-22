#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from proof_factory import review_inbox


if __name__ == "__main__":
    print(json.dumps(review_inbox.process(review_inbox.configured_client()), ensure_ascii=False))
