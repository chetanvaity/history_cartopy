"""Shared utilities for history_cartopy."""

import logging
import yaml

logger = logging.getLogger('history_cartopy.core')


def load_data(gazetteer_path, manifest_path):
    """
    Load gazetteer and manifest YAML files.

    Args:
        gazetteer_path: Path to the gazetteer YAML file
        manifest_path: Path to the map manifest YAML file

    Returns:
        (gazetteer, manifest) tuple
    """
    with open(gazetteer_path, 'r') as f:
        gazetteer = yaml.safe_load(f)['locations']

    with open(manifest_path, 'r') as f:
        manifest = yaml.safe_load(f)

    return gazetteer, manifest


def get_offsets(item):
    """
    Extract x/y offsets from a YAML item.

    Args:
        item: Dict containing optional 'offset' key

    Returns:
        (x_offset, y_offset) tuple, defaults to (0, 0)
    """
    offset = item.get('offset', [0, 0])
    return offset[0], offset[1]
