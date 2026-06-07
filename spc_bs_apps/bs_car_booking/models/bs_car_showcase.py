# -*- coding: utf-8 -*-
# Part of Basic Solution Co., Ltd.

from odoo import api, fields, models


class BsCarShowcaseItem(models.Model):
    """Editorial home-page content tied to a car model.

    This keeps the Hongqi-style campaign sections data-driven: model stage
    slides, exterior/interior colour studio images, highlight cards and the
    cabin story band can all be curated from the back office.
    """
    _name = 'bs.car.showcase.item'
    _description = 'Car Showcase Item'
    _order = 'model_id, item_type, sequence, id'

    name = fields.Char(required=True, translate=True)
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
    website_published = fields.Boolean('Published on Website', default=True)
    model_id = fields.Many2one('bs.car.model', required=True, ondelete='cascade', index=True)
    item_type = fields.Selection([
        ('stage', 'Model Stage Slide'),
        ('exterior', 'Exterior Colour'),
        ('interior', 'Interior Theme'),
        ('highlight', 'Highlight Card'),
        ('cabin', 'Cabin Story'),
    ], required=True, default='highlight', index=True)

    subtitle = fields.Char(translate=True)
    description = fields.Html(translate=True, sanitize_attributes=True)
    image = fields.Image(max_width=1920, max_height=1080)
    image_alt = fields.Char(translate=True)
    swatch_color = fields.Char(
        'Swatch Colour',
        help='CSS colour used by exterior/interior option buttons, e.g. #111111.')
    cta_label = fields.Char('Button Label', translate=True)
    cta_url = fields.Char('Button Link')

    @api.model
    def _get_website_items(self, model, item_type, limit=None):
        model_id = model.id if hasattr(model, 'id') else int(model or 0)
        domain = [
            ('model_id', '=', model_id),
            ('item_type', '=', item_type),
            ('active', '=', True),
            ('website_published', '=', True),
        ]
        return self.sudo().search(domain, order='sequence, id', limit=limit)


class BsCarStory(models.Model):
    """Brand/editorial stories surfaced on the showroom home page."""
    _name = 'bs.car.story'
    _description = 'Car Brand Story'
    _order = 'sequence, publish_date desc, id desc'

    name = fields.Char('Headline', required=True, translate=True)
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
    website_published = fields.Boolean('Published on Website', default=True)
    publish_date = fields.Date()
    location = fields.Char(translate=True,
                           help='Dateline location shown with the date, e.g. "Changchun, China".')
    subtitle = fields.Char(translate=True)
    excerpt = fields.Text(translate=True)
    body = fields.Html(translate=True, sanitize_attributes=True)
    image = fields.Image(max_width=1920, max_height=1080)
    model_id = fields.Many2one('bs.car.model', ondelete='set null')
    cta_label = fields.Char('Button Label', translate=True, default='Read story')
    cta_url = fields.Char('Button Link')

    def _get_website_url(self):
        self.ensure_one()
        return '/story/%s' % self.id

    def _resolve_cta_url(self):
        self.ensure_one()
        if self.cta_url:
            return self.cta_url
        if self.model_id:
            return '/car/%s' % self.model_id.id
        return False

    @api.model
    def _get_website_stories(self, model_id=None, limit=3):
        domain = [('active', '=', True), ('website_published', '=', True)]
        if model_id:
            domain += ['|', ('model_id', '=', int(model_id)), ('model_id', '=', False)]
        return self.sudo().search(domain, order='sequence, publish_date desc, id desc', limit=limit)
