# -*- coding: utf-8 -*-
# Part of Basic Solution Co., Ltd.

from odoo import api, fields, models


class BsCarVariant(models.Model):
    _name = 'bs.car.variant'
    _description = 'Car Standard Package'
    _order = 'model_id, sequence, name'

    name = fields.Char(required=True, translate=True)
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
    model_id = fields.Many2one('bs.car.model', string='Car Model', required=True, ondelete='cascade')
    brand_id = fields.Many2one(related='model_id.brand_id', store=True)
    
    # Legacy package detail fields retained for compatibility; options/pricing
    # is the source of truth for colors, interiors, and wheels.
    exterior_color = fields.Char('Exterior Color')
    exterior_color_code = fields.Char('Color Hex Code', help='e.g. #FF0000')
    interior_color = fields.Char('Interior Color')
    wheel_type = fields.Char('Wheel Type')
    
    # Pricing
    price = fields.Monetary('Price', currency_field='currency_id',
                            help='Price for this booking package')
    currency_id = fields.Many2one(related='model_id.currency_id')
    price_over_base = fields.Monetary('Price Over Base', currency_field='currency_id',
                                      compute='_compute_price_over_base', store=True)
    
    # Specifications specific to the package
    range_km = fields.Integer('Range (km)', help='Leave empty to use model default')
    acceleration = fields.Float('0-100 km/h (s)', digits=(3, 1))
    top_speed = fields.Integer('Top Speed (km/h)')

    # Inventory
    available_qty = fields.Integer('Available Units', default=0)
    estimated_delivery_days = fields.Integer('Estimated Delivery (days)', default=30,
                                             help='Estimated days until delivery')
    
    # Website
    website_published = fields.Boolean('Published on Website', default=True)

    @api.depends('price', 'model_id.base_price')
    def _compute_price_over_base(self):
        for rec in self:
            base = rec.model_id.base_price or 0
            rec.price_over_base = (rec.price or 0) - base
