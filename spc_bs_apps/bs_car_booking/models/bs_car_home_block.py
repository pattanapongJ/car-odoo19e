# -*- coding: utf-8 -*-
# Part of Basic Solution Co., Ltd.

from odoo import api, fields, models


class BsCarHomeBlock(models.Model):
    """Backend-managed home page layout: an ordered list of sections, each
    optionally bound to a specific car model. The /showroom page renders these
    in order — so a multi-model home is curated entirely from the back office
    (pick model + reorder), with no website-builder drag-and-drop."""
    _name = 'bs.car.home.block'
    _description = 'Home Page Section'
    _order = 'sequence, id'

    name = fields.Char('Label', help='Internal label for this section.')
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
    block_type = fields.Selection([
        ('featured_hero', 'Featured Hero'),
        ('model_stage', 'Model Stage'),
        ('color_studio', 'Colour Studio'),
        ('heritage', 'Brand Heritage'),
        ('gallery', 'Model Gallery'),
        ('specs', 'Model Specifications'),
        ('highlights', 'Highlights'),
        ('cabin_story', 'Cabin Story'),
        ('lineup', 'Model Lineup'),
        ('browse', 'Browse Tiles'),
        ('stats', 'Stats Strip'),
        ('arrivals', 'Latest Arrivals'),
        ('offers', 'Offers & Promotions'),
        ('stories', 'Latest Stories'),
        ('finance', 'Finance Calculator'),
        ('dealers', 'Dealer Locator'),
    ], string='Section Type', required=True, default='featured_hero')
    model_id = fields.Many2one(
        'bs.car.model', string='Car Model', ondelete='set null',
        help='Model shown in this section (hero / gallery / specs). '
             'Leave empty to use the model flagged "Featured on Home". '
             'The Lineup section ignores this and lists all published models.')

    @api.depends('block_type', 'model_id')
    def _compute_display_name(self):
        types = dict(self._fields['block_type'].selection)
        for rec in self:
            label = types.get(rec.block_type, rec.block_type)
            if rec.model_id:
                label = f'{label} — {rec.model_id.name}'
            rec.display_name = rec.name or label
