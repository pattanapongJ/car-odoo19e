# -*- coding: utf-8 -*-
# Part of Basic Solution Co., Ltd.

from odoo import fields, models


# Curated Font Awesome icons offered in the freebie form (key = FA class, so the
# website template can use the value directly). Extend as needed.
FREEBIE_ICONS = [
    ('fa-gift', 'Gift'),
    ('fa-plug', 'Plug / charger'),
    ('fa-bolt', 'Bolt / fast charge'),
    ('fa-battery-half', 'Battery'),
    ('fa-money', 'Money / credit'),
    ('fa-shield', 'Shield / insurance'),
    ('fa-wrench', 'Wrench / service'),
    ('fa-ambulance', 'Ambulance / assistance'),
    ('fa-life-ring', 'Life ring / roadside'),
    ('fa-picture-o', 'Picture / window film'),
    ('fa-car', 'Car'),
    ('fa-key', 'Key'),
    ('fa-star', 'Star'),
    ('fa-certificate', 'Certificate / warranty'),
    ('fa-map-marker', 'Map marker'),
    ('fa-calendar-check-o', 'Calendar / maintenance'),
    ('fa-cog', 'Cog / settings'),
    ('fa-tint', 'Tint / coating'),
    ('fa-music', 'Audio'),
    ('fa-wifi', 'Connectivity'),
    ('fa-leaf', 'Eco'),
    ('fa-check-circle', 'Check'),
    ('fa-cube', 'Package'),
]


class BsCarFreebie(models.Model):
    """A complimentary item / gift offered with a car model (e.g. home charger,
    insurance, warranty). Rendered in the booking review modal so the customer
    sees what's included. Data-driven so staff curate the list per model."""
    _name = 'bs.car.freebie'
    _description = 'Car Model Freebie'
    _inherit = ['bs.car.website.scope.mixin']
    _order = 'model_id, sequence, id'
    _bs_clear_website_cache_on_write = True

    model_id = fields.Many2one('bs.car.model', string='Car Model',
                               required=True, ondelete='cascade', index=True)
    sequence = fields.Integer(default=10)
    name = fields.Char('Item', required=True, translate=True,
                       help='Gift name shown to the customer, e.g. "Home Wallbox charger".')
    note = fields.Char('Note', translate=True,
                       help='Small grey detail shown after the item, e.g. "(Type 2 / CCS2)".')
    icon = fields.Selection(
        FREEBIE_ICONS, string='Icon', default='fa-gift',
        help='Icon shown next to the gift in the review modal.')
    website_published = fields.Boolean('Published on Website', default=True,
                                       help='Untick to hide this gift on the website without deleting it.')
