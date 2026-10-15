"""Regression: public legacy phones remain discoverable without relaxing access guards."""
from types import SimpleNamespace
from sqlalchemy import create_engine, select, cast, String
from sqlalchemy.dialects import postgresql
from trustlens.db.repositories import SqlListingRepository
from trustlens.db import models as m


def query(node):
    return SqlListingRepository(SimpleNamespace())._public_query_base(category=None, q=None, category_node_id=node)


def test_legacy_phone_leaf_membership_executes_with_typed_category_exclusions():
    engine = create_engine('sqlite://')
    with engine.begin() as connection:
        connection.exec_driver_sql('CREATE TABLE listings (id TEXT, category TEXT, category_node_id TEXT)')
        connection.exec_driver_sql('INSERT INTO listings VALUES (?, ?, ?)', [
            ('legacy-phone', 'mobiles', None),
            ('typed-phone', 'mobiles', 'mobiles/mobile-phones'),
            ('typed-accessory', 'mobiles', 'mobiles/accessories/chargers'),
            ('typed-tablet', 'computers', 'mobiles/tablets'),
            ('legacy-computer', 'computers', None),
            ('unclassified', 'other', None),
        ])
        condition = query('mobiles/mobile-phones')._where_criteria[-1]
        found = set(connection.execute(select(cast(m.ListingModel.id, String)).where(condition)).scalars())
        # The UUID result processor is not involved in this raw membership check.
        assert found == {'legacy-phone', 'typed-phone'}


def test_specific_tablets_and_cars_do_not_guess_legacy_membership():
    for node in ['mobiles/tablets', 'vehicles/cars']:
        condition = query(node)._where_criteria[-1]
        sql = str(condition.compile(dialect=postgresql.dialect(), compile_kwargs={'literal_binds': True}))
        assert 'category_node_id IN' in sql
        assert 'category_node_id IS NULL' not in sql


def test_phone_fallback_is_inside_existing_public_visibility_guards():
    sql = str(query('mobiles/mobile-phones').compile(dialect=postgresql.dialect(), compile_kwargs={'literal_binds': True}))
    for guard in ['listings.status', 'listings.deleted_at IS NULL', 'seller_profiles.deleted_at IS NULL',
                  'identity_status', 'phone_status', 'email_status', 'is_flagged', 'photo', 'profile']:
        assert guard in sql
    assert "category_node_id IS NULL AND listings.category = 'mobiles'" in sql
    assert "AND (listings.category_node_id IN" in sql
