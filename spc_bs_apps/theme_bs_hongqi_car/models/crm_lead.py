# -*- coding: utf-8 -*-
# Part of Basic Solution Co., Ltd.

from odoo import _, models
from odoo.exceptions import ValidationError


# Contact-page topic (the form's `name` radio) → lead tag. Mapped by xmlid so
# renaming a tag in the backend does not break the stamping.
TOPIC_TAG_XMLIDS = {
    'Dealership Application': 'theme_bs_hongqi_car.crm_tag_contact_dealer',
    'Job Application': 'theme_bs_hongqi_car.crm_tag_contact_job',
    'Other': 'theme_bs_hongqi_car.crm_tag_contact_other',
}


class CrmLead(models.Model):
    _inherit = 'crm.lead'

    def website_form_input_filter(self, request, values):
        """Contact-page submissions, recognised by their topic:
        - PDPA consent is enforced SERVER-SIDE (client validation is
          trivially bypassed with a direct POST, and consent is a legal
          requirement, not a UX nicety);
        - the topic tag is stamped server-side — client-sent tag_ids are
          dropped unconditionally (tags drive sales routing/reporting)."""
        values = super().website_form_input_filter(request, values)
        values.pop('tag_ids', None)
        topic = (values.get('name') or '').strip()
        xmlid = TOPIC_TAG_XMLIDS.get(topic)
        if xmlid:
            if request.params.get('Privacy Consent') != 'Accepted':
                raise ValidationError(_('Please accept the Privacy Policy to continue.'))
            tag = self.env.ref(xmlid, raise_if_not_found=False)
            if tag:
                values['tag_ids'] = [(4, tag.id)]
            # "Other" topic: the user's message replaces the generic description.
            if topic == 'Other':
                msg = (request.params.get('contact_message') or '').strip()
                if not msg:
                    raise ValidationError(_('Please describe your inquiry for "Other" topic.'))
                values['description'] = msg
        return values
