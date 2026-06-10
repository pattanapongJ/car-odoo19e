# -*- coding: utf-8 -*-
# Part of Basic Solution Co., Ltd.

from odoo import fields, models


class BsCarWebsiteSection(models.Model):
    _inherit = 'bs.car.website.section'

    theme_variant = fields.Selection(
        selection_add=[('hongqi_heritage', 'Hongqi Thailand Cover')],
        ondelete={'hongqi_heritage': 'set default'},
    )
