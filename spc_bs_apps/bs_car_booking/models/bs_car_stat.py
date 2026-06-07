# -*- coding: utf-8 -*-
# Part of Basic Solution Co., Ltd.

import re

from odoo import api, fields, models


class BsCarStat(models.Model):
    """A single big-number shown in the home "Stats strip". Hybrid: either a
    hand-entered marketing figure (e.g. "12,400+ delivered") or a value
    computed live from the data (model/dealer/booking counts, max range)."""
    _name = 'bs.car.stat'
    _description = 'Showroom Statistic'
    _order = 'sequence, id'

    name = fields.Char('Label', required=True, translate=True,
                       help='Caption under the number, e.g. "Cars delivered".')
    source = fields.Selection([
        ('manual', 'Manual value'),
        ('models_count', 'Published models'),
        ('dealers_count', 'Showrooms'),
        ('brands_count', 'Brands'),
        ('bookings_count', 'Bookings placed'),
        ('max_range', 'Max range (km)'),
    ], string='Value Source', default='manual', required=True,
       help='Manual = type the figure yourself; the others are computed live.')
    value = fields.Char('Manual Value',
                        help='Used when Source is Manual, e.g. "12,400+" or "98%".')
    unit = fields.Char('Unit', translate=True,
                       help='Shown after the value with spacing, e.g. "km", "min".')
    icon = fields.Char('Icon', help='Font Awesome class, e.g. "fa-car", "fa-bolt".')
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
    website_published = fields.Boolean('Published on Website', default=True)

    # Animation target (plain integer) + fail-safe formatted text + trailing
    # symbol parsed from a manual value (e.g. the "+" in "12,400+").
    count_target = fields.Char(compute='_compute_value')
    count_display = fields.Char(compute='_compute_value')
    value_suffix = fields.Char(compute='_compute_value')
    display_value = fields.Char('Resolved Value', compute='_compute_value')

    @api.depends('source', 'value', 'unit')
    def _compute_value(self):
        for rec in self:
            if rec.source == 'manual':
                raw = (rec.value or '').strip()
                target = re.sub(r'[^\d]', '', raw) or '0'
                m = re.match(r'[\d\s,\.]+(.*)$', raw)
                suffix = (m.group(1).strip() if m else '')
            else:
                target = str(rec._compute_count())
                suffix = ''
            rec.count_target = target
            rec.count_display = '{:,}'.format(int(target))
            rec.value_suffix = suffix
            rec.display_value = (rec.count_display + suffix
                                 + (' ' + rec.unit if rec.unit else ''))

    def _compute_count(self):
        self.ensure_one()
        env = self.env
        published = [('website_published', '=', True), ('active', '=', True)]
        if self.source == 'models_count':
            return env['bs.car.model'].sudo().search_count(published)
        if self.source == 'dealers_count':
            return env['bs.car.dealer'].sudo().search_count(published)
        if self.source == 'brands_count':
            return env['bs.car.brand'].sudo().search_count([('active', '=', True)])
        if self.source == 'bookings_count':
            return env['bs.car.booking'].sudo().search_count([])
        if self.source == 'max_range':
            m = env['bs.car.model'].sudo().search(
                published, order='range_km desc', limit=1)
            return m.range_km or 0
        return 0

    @api.model
    def _get_website_stats(self):
        return self.sudo().search(
            [('active', '=', True), ('website_published', '=', True)],
            order='sequence, id')
