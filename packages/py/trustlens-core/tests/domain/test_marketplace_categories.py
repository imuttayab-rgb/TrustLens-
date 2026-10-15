"""Regression coverage and test support for test marketplace categories."""
import pytest
from dataclasses import replace
from datetime import UTC, datetime
from uuid import uuid4
from trustlens.core.catalogue import CATALOGUE, NODES, typed_attributes, required_category_details, validate_facets
from trustlens.core.catalogue.search import search_tokens
from trustlens.core.application.services.listing_publication import listing_media_missing
from trustlens.core.domain.entities import Listing
from trustlens.core.domain.enums import ListingStatus, ListingSource
from trustlens.core.domain.errors import ValidationError


def listing(**kw):
    return Listing(id=uuid4(),seller_id=uuid4(),title='Synthetic listing',description='Synthetic details',status=ListingStatus.DRAFT,source=ListingSource.MANUAL,created_at=datetime.now(UTC),**kw)


def test_registry_covers_reference_and_extensions_without_orphans():
    assert len(CATALOGUE['nodes']) == 732
    assert len(NODES) == 732
    assert len([n for n in NODES.values() if not n['parentId']]) == 14
    for n in NODES.values():
        assert n['parentId'] is None or n['parentId'] in NODES
        assert n['schema'] in CATALOGUE['schemas']
        assert n['selectable'] == (not any(c['parentId']==n['id'] for c in NODES.values()))
    for name in ['cosmetics','skincare']:
        assert NODES['fashion-beauty/'+name]['schema']=='cosmetics'


def test_cards_are_the_only_source_of_typed_facts():
    data=typed_attributes('mobiles/mobile-phones',{'RAM':'8 GB','Storage':'256GB','PTA status':'Non-PTA','Known faults':'Screen replaced; Face ID not working'})
    assert data=={'ram':8.0,'storage':256.0,'pta':'Non-PTA','faults':'Screen replaced; Face ID not working'}
    assert typed_attributes('fashion-beauty/skincare',{'Brand':'Test brand'})=={'brand':'Test brand'}
    assert 'expiry' not in typed_attributes('fashion-beauty/skincare',{'Brand':'Test brand'})


@pytest.mark.parametrize('attrs',[{'Battery health':'101%'},{'RAM':'8 or 12 GB'},{'PTA status':'Yes, probably'},{'RAM':'8GB','ram':'12GB'}])
def test_bad_or_conflicting_phone_values_are_rejected(attrs):
    with pytest.raises(ValidationError):typed_attributes('mobiles/mobile-phones',attrs)


@pytest.mark.parametrize('attrs',[{'Expiry date':'2026-02-30'},{'Expiry date':'never expires'},{'Opened on':'2026-06-01','Expiry date':'2026-05-01'}])
def test_expiry_is_not_guessed_or_normalized_to_a_different_date(attrs):
    with pytest.raises(ValidationError):typed_attributes('fashion-beauty/skincare',attrs)


def test_old_listings_keep_physical_media_gates():
    assert listing_media_missing(listing(),0)==['photo','video','location']
    assert listing_media_missing(listing(category_node_id='mobiles/mobile-phones'),0)==['photo','video','location']


def test_nonphysical_exception_is_category_scoped_and_still_requires_details():
    node=next(n for n in NODES.values() if n['schema']=='job' and n['selectable'])
    ad=listing(category_node_id=node['id'],category_data={},city=None)
    assert listing_media_missing(ad,0)==['location','category_details']
    values={'role':'Math tutor','employer':'Synthetic employer','employment':'Part-time','work_mode':'On-site'}
    assert not listing_media_missing(replace(ad,city='Lahore',category_data=values),0)
    assert listing_media_missing(replace(ad,category_node_id=None),0)==['photo','video','location']


def test_units_and_required_property_details_are_explicit():
    node='property-sale/houses'
    assert required_category_details(node,{'area':5})==['Area unit']
    assert typed_attributes(node,{'Area':'5','Area unit':'Marla'})=={'area':5.0,'area_unit':'Marla'}
    with pytest.raises(ValidationError):typed_attributes(node,{'Area':'5 kanal','Area unit':'Marla'})


def test_filter_validation_rejects_unknown_keys_nonfinite_and_reversed_ranges():
    assert validate_facets('vehicles/cars',{'year':{'min':2020},'make':'Toyota'})
    for filters in [{'password':'x'},{'year':{'min':2030,'max':2020}},{'mileage':{'min':float('nan')}},{'year':{'sql':'DROP'}}]:
        with pytest.raises(ValidationError):validate_facets('vehicles/cars',filters)


def test_plus_tokens_and_literals():
    assert search_tokens('Samsung S 21+')==['samsung','s21','plus']
    assert search_tokens('Samsung S21 Plus')==['samsung','s21','plus']
    assert search_tokens('%_')==[]
