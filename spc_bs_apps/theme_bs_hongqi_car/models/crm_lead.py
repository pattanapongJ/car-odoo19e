# -*- coding: utf-8 -*-
# Part of Basic Solution Co., Ltd.

from odoo import models


# Contact-page topic (the form's `name` radio) → lead tag. Mapped by xmlid so
# renaming a tag in the backend does not break the stamping.
TOPIC_TAG_XMLIDS = {
    'Request E-Catalog': 'theme_bs_hongqi_car.crm_tag_contact_catalog',
    'Dealership Application': 'theme_bs_hongqi_car.crm_tag_contact_dealer',
    'Job Application': 'theme_bs_hongqi_car.crm_tag_contact_job',
}


class CrmLead(models.Model):
    _inherit = 'crm.lead'

    def website_form_input_filter(self, request, values):
        """Stamp the contact-page topic tag SERVER-SIDE. Client-sent tag_ids
        are dropped unconditionally: a hidden input is trivially tampered
        with, and tags drive sales routing/reporting."""
        values = super().website_form_input_filter(request, values)
        values.pop('tag_ids', None)
        xmlid = TOPIC_TAG_XMLIDS.get((values.get('name') or '').strip())
        if xmlid:
            tag = self.env.ref(xmlid, raise_if_not_found=False)
            if tag:
                values['tag_ids'] = [(4, tag.id)]
        return values
