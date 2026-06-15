# -*- coding: utf-8 -*-
# Part of Basic Solution Co., Ltd.
#
# contact_person was removed from bs.car.booking. Existing stored views still
# reference it, and during the upgrade the base booking form is re-validated
# BEFORE its inheriting view is reloaded from the new XML — so the stale child
# still carries <field name="contact_person"/> and view validation fails.
#
# Drop the stale views here (pre-migration, before views reload):
#   * backend views on bs.car.booking  -> recreated clean from this module's XML
#   * website-specific (COW) copies     -> fall back to the updated generic view
# The module-owned generic QWeb template is left untouched; it is QWeb (not
# validated against model fields) and gets refreshed from the new XML on load.


def migrate(cr, version):
    if not version:
        return
    cr.execute("""
        DELETE FROM ir_ui_view
        WHERE arch_db::text LIKE '%contact_person%'
          AND (model = 'bs.car.booking' OR website_id IS NOT NULL)
    """)
