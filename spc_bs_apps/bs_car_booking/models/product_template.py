# -*- coding: utf-8 -*-
# Part of Basic Solution Co., Ltd.

from odoo import fields, models


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    # Back-link to the marketing/catalog record. The website funnel reads
    # specs/gallery/hero from bs.car.model while pricing & configuration come
    # from this product.template + its attribute lines.
    bs_car_model_id = fields.Many2one(
        'bs.car.model', string='Car Model (Catalog)',
        ondelete='set null', index=True, copy=False,
        help='Marketing/catalog record this configurable car product belongs to.')
