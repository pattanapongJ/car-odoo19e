# -*- coding: utf-8 -*-
# Part of Basic Solution Co., Ltd.

import re

from odoo import api, fields, models


NUMBER_RE = re.compile(r'\d+(?:\.\d+)?')


class BsCarModelSpec(models.Model):
    """A single technical specification line for a car model
    (e.g. "Range (WLTP)" = "548" km). Flexible key/value so each model can
    expose its own spec sheet without schema changes; rendered on the website
    detail page and the home "featured model" snippet."""
    _name = 'bs.car.model.spec'
    _description = 'Car Model Specification'
    _inherit = ['bs.car.website.scope.mixin']
    _order = 'model_id, sequence, id'
    _bs_clear_website_cache_on_write = True

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

    @api.model
    def _spec_number(self, value):
        match = NUMBER_RE.search(value or '')
        return float(match.group(0)) if match else 0.0

    def _sync_models_performance_cache(self, models):
        """Keep model numeric fields in sync with the data-driven spec sheet.

        The website still needs numeric fields for filters, cards, sorting, and
        variant fallback values. Editors should maintain specs only; these
        cached fields are derived from recognizable spec labels.
        """
        for model in models.sudo():
            vals = {
                'range_km': 0,
                'acceleration': 0.0,
                'top_speed': 0,
            }
            for spec in model.spec_ids.sorted(lambda s: (s.sequence, s.id)):
                label = (spec.name or '').lower()
                number = self._spec_number(spec.value)
                if not number:
                    continue
                if not vals['range_km'] and 'range' in label:
                    vals['range_km'] = int(round(number))
                elif not vals['acceleration'] and (
                    'accel' in label or ('0' in label and '100' in label)
                ):
                    vals['acceleration'] = number
                elif not vals['top_speed'] and 'top' in label and 'speed' in label:
                    vals['top_speed'] = int(round(number))
            write_vals = {
                field: value for field, value in vals.items()
                if model[field] != value
            }
            if write_vals:
                model.write(write_vals)

    def _sync_model_performance_cache(self):
        self._sync_models_performance_cache(self.mapped('model_id'))

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        records._sync_model_performance_cache()
        return records

    def write(self, vals):
        result = super().write(vals)
        if {'name', 'value', 'unit', 'sequence', 'model_id'} & set(vals):
            self._sync_model_performance_cache()
        return result

    def unlink(self):
        models = self.mapped('model_id')
        result = super().unlink()
        self._sync_models_performance_cache(models)
        return result
