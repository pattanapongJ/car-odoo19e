# -*- coding: utf-8 -*-
# Part of Basic Solution Co., Ltd.

from odoo import api, fields, models


class BsCarModelSpec(models.Model):
    """A single technical specification line for a car model
    (e.g. "Range (WLTP)" = "548" km). Flexible key/value so each model can
    expose its own spec sheet without schema changes; rendered on the website
    detail page and the home "featured model" snippet."""
    _name = 'bs.car.model.spec'
    _description = 'Car Model Specification'
    _order = 'model_id, sequence, id'

    model_id = fields.Many2one('bs.car.model', string='Car Model',
                               required=True, ondelete='cascade', index=True)
    name = fields.Char('Label', required=True, translate=True,
                       help='Spec name, e.g. "Range (WLTP)", "Battery", "Power".')
    value = fields.Char('Value', required=True, help='e.g. "548", "120", "202 + 160".')
    unit = fields.Char('Unit', help='e.g. "km", "kWh", "kW", "N·m". Optional.')
    sequence = fields.Integer(default=10)
    is_highlight = fields.Boolean(
        'Hero Highlight',
        help='Show this spec prominently (e.g. in the hero metrics strip).')

    display_value = fields.Char(compute='_compute_display_value')

    @api.depends('value', 'unit')
    def _compute_display_value(self):
        for rec in self:
            rec.display_value = f'{rec.value} {rec.unit}'.strip() if rec.unit else (rec.value or '')
