"""Conservative recommendation planning: seller facts and literal search terms only."""
from dataclasses import dataclass, field
import re
from .search import search_tokens

@dataclass(frozen=True)
class RecommendationQuery:
    key: str
    node: str | None
    q: str | None = None
    facets: dict = field(default_factory=dict)


def same_search(title: str, query: str) -> bool:
    terms = set(search_tokens(query))
    return bool(terms) and terms <= set(search_tokens(title))


def recommendation_plan(node: str | None, facts: dict, query: str | None, *, detail: bool) -> list[RecommendationQuery]:
    model = str(facts.get('model') or '').strip()
    brand = str(facts.get('brand') or facts.get('make') or '').strip()
    groups = []
    if detail and model and node:
        groups.append(RecommendationQuery('same-model', node, facets={'model': model, **({'make' if 'make' in facts else 'brand': brand} if brand else {})}))
    text = model or query or ''
    # Family matching deliberately requires a recognizable literal model family.
    family = re.search(r'\b(?:galaxy\s+)?s\s?(\d{1,3})\b|\biphone\s*(\d{1,2})\b', text, re.I)
    if family and node:
        phrase = f'Samsung S{family[1]}' if family[1] else f'iPhone {family[2]}'
        groups.append(RecommendationQuery('same-family', node, q=phrase))
    if node:
        groups.append(RecommendationQuery('alternatives', node, facets={('make' if 'make' in facts else 'brand'): brand} if brand else {}))
    # An accessory only qualifies via an explicit compatibility field. Its title
    # alone does not establish that it fits a phone, computer or vehicle.
    accessory_node = None
    if node == 'mobiles/mobile-phones': accessory_node = 'mobiles/accessories'
    elif node and node.startswith('vehicles/'): accessory_node = 'vehicles/spare-parts'
    elif node and node.startswith('bikes/'): accessory_node = 'bikes/spare-parts'
    if accessory_node and model:
        groups.append(RecommendationQuery('compatible-accessories', accessory_node, facets={'compatible_model': model}))
    return groups
