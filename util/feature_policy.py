"""Shared predictor allowlists and later-outcome exclusions."""

from fnmatch import fnmatchcase
import hashlib
import json
from pathlib import Path


POLICY_PATH = Path(__file__).with_suffix(".json")
POLICY = json.loads(POLICY_PATH.read_text())


def validate_features(features, scope="independent_baseline"):
    if scope not in POLICY["scopes"]:
        raise ValueError(f"Unknown feature scope: {scope}")
    if not features or len(features) != len(set(features)):
        raise ValueError("Predictors must be nonempty and contain no duplicate names.")
    allowed = set()
    for group in POLICY["scopes"][scope]:
        allowed.update(POLICY["groups"][group])
    blocked = []
    for feature in features:
        name = feature.lower()
        if name in POLICY["deny_exact"] or any(fnmatchcase(name, pattern) for pattern in POLICY["deny_patterns"]):
            blocked.append(feature)
    if blocked:
        raise ValueError(f"Forbidden outcome/metadata predictors: {', '.join(blocked)}")
    unknown = sorted(set(features) - allowed)
    if unknown:
        raise ValueError(f"Predictors not approved for {scope}: {', '.join(unknown)}")
    return {"policy_version": POLICY["version"],
            "policy_sha256": hashlib.sha256(POLICY_PATH.read_bytes()).hexdigest(),
            "scope": scope, "features": list(features),
            "scope_note": POLICY["scope_notes"][scope], "deployment_approved": False}
