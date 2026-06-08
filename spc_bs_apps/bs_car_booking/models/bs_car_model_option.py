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
    attribute_name = fields.Char(related='attribute_id.name', string='Attribute Name', store=True)
    attribute_sequence = fields.Integer(
        related='attribute_id.sequence', string='Attribute Sequence', store=True)
    sequence = fields.Integer(string='Option Sequence', default=10)
    price_extra = fields.Monetary('Extra Price', currency_field='currency_id',
                                  help='Additional price for this option on this model.')
    currency_id = fields.Many2one(related='model_id.currency_id')
    
    image = fields.Image(max_width=1920, max_height=1080)
    image_alt = fields.Char(translate=True)

    # --- Colour Studio (website) extensions ---------------------------------
    # Swatch colour shown on the website option button. Falls back to the
    # attribute value's native html_color (set on exterior colours) when blank.
    swatch_color = fields.Char(
        'Swatch Colour',
        help='CSS colour for the website option swatch, e.g. #111111. '
             'Leave blank to use the colour value\'s own colour.')
    # Optional second colour: when set, the website swatch is rendered as a
    # diagonal two-tone (e.g. a two-tone "Black & White" interior).
    swatch_color_2 = fields.Char(
        'Second Swatch Colour',
        help='Optional second colour. When set, the swatch is shown as a '
             'two-tone (diagonal split) of both colours.')
    # On an EXTERIOR colour line: the interior options offered with it. Lets the
    # Colour Studio reveal only the interiors available for the chosen exterior.
    # Self-referential M2M restricted (in the view) to this model's interiors.
    interior_option_ids = fields.Many2many(
        'bs.car.model.option', relation='bs_car_option_ext_int_rel',
        column1='exterior_option_id', column2='interior_option_id',
        string='Available Interiors',
        help='Interior options offered with this exterior colour. '
             'Leave empty to offer every interior configured on the model.')

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

    @api.model
    def _get_color_options(self, model, attribute_ref):
        """Option lines of ``model`` for the given attribute (by xmlid), in
        display order. Used by the Colour Studio to source exterior/interior
        swatches from the priced configurator options."""
        attr = self.env.ref(attribute_ref, raise_if_not_found=False)
        if not attr:
            return self.browse()
        model_id = model.id if hasattr(model, 'id') else int(model or 0)
        return self.sudo().search([
            ('model_id', '=', model_id),
            ('attribute_id', '=', attr.id),
        ], order='sequence, id')

    def _studio_swatch(self):
        """Resolved (primary) swatch colour for the website button."""
        self.ensure_one()
        return self.swatch_color or self.value_id.html_color or '#111111'

    def _studio_swatch_style(self):
        """CSS ``background`` for the website swatch: a solid colour, or a
        diagonal two-tone when a second colour is configured."""
        self.ensure_one()
        c1 = self._studio_swatch()
        c2 = self.swatch_color_2
        if c2:
            return f'background:linear-gradient(135deg, {c1} 0 50%, {c2} 50% 100%)'
        return f'background:{c1}'
