# -*- coding: utf-8 -*-
# Part of Basic Solution Co., Ltd.

from odoo import api, fields, models


class BsCarOffer(models.Model):
    """A time-boxed promotional offer surfaced on the showroom home and car
    detail pages. Validity is date-driven, so a campaign goes live and expires
    on its own — the back office curates the whole thing (no builder editing)."""
    _name = 'bs.car.offer'
    _description = 'Promotional Offer'
    _inherit = ['website.published.multi.mixin', 'bs.car.website.scope.mixin']
    _order = 'sequence, id'
    _bs_clear_website_cache_on_write = True

    name = fields.Char('Headline', required=True, translate=True,
                       help='Main promo line, e.g. "0% APR for 36 months".')
    subtitle = fields.Char('Subtitle', translate=True)
    description = fields.Html('Description', translate=True, sanitize_attributes=True)
    badge = fields.Char('Badge', translate=True,
                        help='Short tag shown on the card, e.g. "Limited time".')
    image = fields.Image('Image', max_width=1920, max_height=1080)
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
    company_id = fields.Many2one(
        'res.company', string='Company', default=lambda self: self.env.company,
        index=True, help='Leave empty to share this offer across companies.')

    def _default_is_published(self):
        return True

    date_start = fields.Date('Starts On',
                             help='Leave empty to start immediately.')
    date_end = fields.Date('Ends On',
                           help='Leave empty for an open-ended offer.')
    is_live = fields.Boolean('Live Now', compute='_compute_is_live',
                             help='Currently within its validity window and published.')

    model_id = fields.Many2one('bs.car.model', string='Car Model',
                               ondelete='set null',
                               help='Optional — links the call-to-action to this model.')
    cta_label = fields.Char('Button Label', translate=True, default='Learn more')
    cta_url = fields.Char('Button Link',
                          help='Optional. Defaults to the linked model\'s page when set.')

    @api.depends('date_start', 'date_end', 'active', 'website_published')
    def _compute_is_live(self):
        today = fields.Date.context_today(self)
        for rec in self:
            ok = rec.active and rec.website_published
            if ok and rec.date_start and rec.date_start > today:
                ok = False
            if ok and rec.date_end and rec.date_end < today:
                ok = False
            rec.is_live = ok

    def _resolve_cta_url(self):
        """The effective CTA link: explicit URL, else the model page, else None."""
        self.ensure_one()
        if self.cta_url:
            return self.cta_url
        if self.model_id:
            return '/car/%s' % self.model_id.id
        return False

    @api.model
    def _get_active_offers(self, model_id=None):
        """Currently-valid, published offers (date window honoured in SQL).

        When ``model_id`` is given, returns offers for that model plus
        model-agnostic (global) offers — used on a car's detail page.
        """
        today = fields.Date.context_today(self)
        domain = [
            ('active', '=', True),
            ('website_published', '=', True),
            '|', ('date_start', '=', False), ('date_start', '<=', today),
            '|', ('date_end', '=', False), ('date_end', '>=', today),
        ]
        if model_id:
            domain += ['|', ('model_id', '=', int(model_id)), ('model_id', '=', False)]
        return self.sudo().search(domain + self._public_scope_domain(), order='sequence, id')
