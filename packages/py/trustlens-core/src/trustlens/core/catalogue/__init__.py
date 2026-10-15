"""Versioned marketplace taxonomy. No network, AI inference or verification bypasses."""
from __future__ import annotations

import json
import math
import re
from datetime import date
from importlib.resources import files
from typing import Any

from trustlens.core.domain.errors import ValidationError

CATALOGUE = json.loads(files(__package__).joinpath('categories.json').read_text(encoding='utf-8'))
NODES = {node['id']: node for node in CATALOGUE['nodes']}
SCHEMAS = CATALOGUE['schemas']


def category_node(node_id: str | None, *, leaf: bool = False) -> dict[str, Any] | None:
    if node_id is None:
        return None
    node = NODES.get(node_id)
    if not node or (leaf and not node['selectable']):
        raise ValidationError('Choose a supported final category.', field='categoryNodeId')
    return node


def descendants(node_id: str) -> list[str]:
    category_node(node_id)
    return [key for key in NODES if key == node_id or key.startswith(node_id + '/')]


def field_key(value: str) -> str:
    return re.sub(r'[^a-z0-9]', '', value.casefold())


def category_fields(node_id: str | None) -> list[dict[str, Any]]:
    node = category_node(node_id)
    return SCHEMAS[node['schema']] if node else []


def typed_attributes(node_id: str | None, attributes: dict[str, str]) -> dict[str, Any]:
    """Derive typed filters from the SAME confirmed cards displayed on the listing.

    Unknown freeform cards are retained by callers. Never infer missing condition,
    expiry, authenticity, ownership or variant facts from a title or photograph.
    """
    if node_id is None:
        return {}
    node = category_node(node_id, leaf=True)
    result: dict[str, Any] = {}
    for field in SCHEMAS[node['schema']]:
        matches = [v.strip() for k, v in attributes.items()
                   if field_key(k) in {field_key(field['label']), field_key(field['key'])} and v.strip()]
        if len(set(matches)) > 1:
            raise ValidationError(f"Confirm one value for {field['label']}.", field='attributes')
        if not matches:
            continue
        value: Any = matches[0]
        if field['type'] == 'number':
            unit = field.get('unit')
            pattern = r'\s*(\d+(?:\.\d+)?)\s*'
            if unit:
                pattern = r'\s*(\d+(?:\.\d+)?)\s*(?:' + re.escape(unit) + r')?\s*'
            match = re.fullmatch(pattern, value, re.I)
            if not match:
                raise ValidationError(f"Enter a numeric {field['label']}" + (f' in {unit}.' if unit else '.'), field='attributes')
            value = float(match[1])
            if not math.isfinite(value) or value < field.get('min', 0) or value > field.get('max', 100000000):
                raise ValidationError(f"{field['label']} is outside the allowed range.", field='attributes')
            if field['key'] in {'year','bedrooms','bathrooms','pieces','count','gears','shutter'} and not value.is_integer():
                raise ValidationError(f"{field['label']} must be a whole number.", field='attributes')
        elif field['type'] == 'select':
            match = next((x for x in field['options'] if x.casefold() == value.casefold()), None)
            if match is None:
                raise ValidationError(f"Choose a supported {field['label']} value.", field='attributes')
            value = match
        elif field['type'] == 'date':
            try:
                value = date.fromisoformat(value).isoformat()
            except ValueError as exc:
                raise ValidationError(f"Use YYYY-MM-DD for {field['label']}; leave unknown dates blank.", field='attributes') from exc
        elif len(value) > 160:
            raise ValidationError('Keep each specification under 160 characters.', field='attributes')
        result[field['key']] = value
    if result.get('opened') and result.get('expiry') and result['opened'] > result['expiry']:
        raise ValidationError('Opening date is after expiry; confirm these dates.', field='attributes')
    return result


def required_category_details(node_id: str | None, data: dict[str, Any]) -> list[str]:
    return [f['label'] for f in category_fields(node_id) if f.get('required') and data.get(f['key']) in (None, '')]


def media_policy(node_id: str | None) -> str:
    node = category_node(node_id)
    return node['policy'] if node else 'physical'


def validate_facets(node_id: str | None, facets: dict[str, Any] | None) -> dict[str, Any]:
    if not facets:
        return {}
    if not node_id or len(facets) > 12:
        raise ValidationError('Choose a category before filtering specifications.', field='facets')
    # Parent categories allow the union of their descendants' declared fields.
    fields = {f['key']: f for id in descendants(node_id) for f in category_fields(id)}
    result = {}
    for key, value in facets.items():
        field = fields.get(key)
        if field is None:
            raise ValidationError('Unsupported specification filter.', field='facets')
        if isinstance(value, dict):
            if field['type'] != 'number' or not value or set(value) - {'min', 'max'}:
                raise ValidationError('Only numeric specifications support ranges.', field='facets')
            if any(type(v) not in (float, int) or not math.isfinite(v) or v < field.get('min', 0) or v > field.get('max', 100000000) for v in value.values()):
                raise ValidationError('Specification range is invalid.', field='facets')
            if value.get('min', 0) > value.get('max', 100000000):
                raise ValidationError('Minimum cannot exceed maximum.', field='facets')
        elif type(value) not in (str, float, int) or len(str(value)) > 160:
            raise ValidationError('Specification filter is invalid.', field='facets')
        elif field['type'] == 'number' and (type(value) not in (float, int) or not math.isfinite(value)):
            raise ValidationError('Use a numeric specification filter.', field='facets')
        elif field['type'] == 'select' and value not in field['options']:
            raise ValidationError('Choose a supported specification option.', field='facets')
        result[key] = value
    return result
