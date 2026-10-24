"""Validate the prepared Blueprint against Render's current public JSON schema."""

import json
from pathlib import Path
from urllib.request import urlopen

import jsonschema
import yaml


def validate(blueprint, schema):
    validator = jsonschema.validators.validator_for(schema)
    validator.check_schema(schema)
    validator(schema).validate(blueprint)


if __name__ == "__main__":
    root = Path(__file__).resolve().parents[1]
    with urlopen("https://render.com/schema/render.yaml.json", timeout=20) as response:
        raw = response.read(1_048_577)
    if len(raw) > 1_048_576:
        raise SystemExit("Render schema exceeded the accepted size.")
    schema = json.loads(raw)
    for path in (root / "render.yaml", root / "deploy/render.persistent.yaml"):
        validate(yaml.safe_load(path.read_text()), schema)
    print("Render Blueprint passes the current public JSON schema. No cloud resources were created.")
