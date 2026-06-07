# -*- coding: utf-8 -*-
# Part of Basic Solution Co., Ltd.

from odoo import api, fields, models


class BsCarModelOption(models.Model):
    """A selectable, priced option for a car model (color, interior, wheels,
    add-on...). Each line maps to a native product.attribute.value plus the
    extra price for THIS model. On product generation these become
    product.template.attribute.value records with price_extra set."""
    _name = 'bs.car.model.option'
    _description = 'Car Model Option'
    _order = 'attribute_sequence, sequence, id'

    model_id = fields.Many2one('bs.car.model', string='Car Model',
                               required=True, ondelete='cascade', index=True)
    value_id = fields.Many2one('product.attribute.value', string='Option',
                               required=True, ondelete='cascade')
    attribute_id = fields.Many2one('product.attribute', related='value_id.attribute_id',
                                   string='Attribute', store=True, index=True)
    attribute_sequence = fields.Integer(
        related='attribute_id.sequence', string='Attribute Sequence', store=True)
    sequence = fields.Integer(string='Option Sequence', default=10)
    price_extra = fields.Monetary('Extra Price', currency_field='currency_id',
                                  help='Additional price for this option on this model.')
    currency_id = fields.Many2one(related='model_id.currency_id')

    _model_value_uniq = models.Constraint(
        'UNIQUE(model_id, value_id)',
        'This option is already configured for this car model.',
    )

    @api.depends('value_id', 'attribute_id')
    def _compute_display_name(self):
        for rec in self:
            attr = rec.attribute_id.name or ''
            val = rec.value_id.name or ''
            rec.display_name = f'{attr}: {val}' if attr else val
