# ruff: noqa
"""Entry point: wires login and formatting together."""

import os
import json as j
from auth import verify_password
from utils.helpers import fmt
import missing_module  # not in the repo: no edge
import app  # imports itself: no edge


def main(user, password):
    if verify_password(user, password):
        return fmt(user["name"])
