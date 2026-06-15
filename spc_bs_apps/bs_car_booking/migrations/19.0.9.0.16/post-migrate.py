# -*- coding: utf-8 -*-
# Part of Basic Solution Co., Ltd.
#
# The `contact_person` field was merged into `customer_name`: the person's
# name now lives in customer_name for BOTH customer types (individual = the
# customer; company = the authorised contact person). This migration moves
# existing company bookings' contact_person value into customer_name before
# the orphan column is dropped, so no data is lost.


def migrate(cr, version):
    if not version:
        return

    # The field is already gone from the model, but Odoo leaves the DB column
    # in place. Only migrate if the column still exists.
    cr.execute("""
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'bs_car_booking' AND column_name = 'contact_person'
    """)
    if not cr.fetchone():
        return

    # Copy the contact person's name into customer_name for company bookings
    # that don't already have one. Individuals already store it in customer_name.
    cr.execute("""
        UPDATE bs_car_booking
        SET customer_name = contact_person
        WHERE customer_type = 'company'
          AND COALESCE(NULLIF(TRIM(customer_name), ''), '') = ''
          AND COALESCE(NULLIF(TRIM(contact_person), ''), '') <> ''
    """)

    # Drop the now-orphan column to keep the schema clean.
    cr.execute("ALTER TABLE bs_car_booking DROP COLUMN contact_person")
