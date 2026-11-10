"""Small JSON-lines log writer shared by the streaming scripts."""

from datetime import datetime, timezone
import json
from pathlib import Path
import uuid


def write_event(path, event_type, **fields):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    event = {"@timestamp": datetime.now(timezone.utc).isoformat(),
             "log_id": uuid.uuid4().hex, "event_type": event_type, **fields}
    with path.open("a") as stream:
        stream.write(json.dumps(event, allow_nan=False) + "\n")
    return event
