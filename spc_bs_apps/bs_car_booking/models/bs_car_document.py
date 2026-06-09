# -*- coding: utf-8 -*-
# Part of Basic Solution Co., Ltd.

from odoo import fields, models


class BsCarDocumentType(models.Model):
    """Admin-configurable document a customer must provide at booking.
    `applies_to` + `required` drive what the funnel asks for per customer type."""
    _name = 'bs.car.document.type'
    _description = 'Customer Document Type'
    _order = 'sequence, id'

    name = fields.Char('Document', required=True, translate=True)
    code = fields.Char('Code')
    applies_to = fields.Selection([
        ('individual', 'Individual'),
        ('company', 'Company'),
        ('both', 'Both'),
    ], string='Applies To', default='both', required=True,
        help='Which customer type must provide this document.')
    required = fields.Boolean('Required', default=True)
    sequence = fields.Integer('Sequence', default=10)
    active = fields.Boolean('Active', default=True)
    help_text = fields.Char('Hint', translate=True,
                            help='Short guidance shown under the upload field.')

    def _matches(self, customer_type):
        """True if this document type applies to the given customer type."""
        self.ensure_one()
        return self.applies_to in ('both', customer_type)


class BsCarBookingDocument(models.Model):
    """A file uploaded by the customer for one document type on a booking."""
    _name = 'bs.car.booking.document'
    _description = 'Booking Customer Document'
    _order = 'sequence, id'

    booking_id = fields.Many2one('bs.car.booking', string='Booking',
                                 required=True, ondelete='cascade', index=True)
    document_type_id = fields.Many2one('bs.car.document.type', string='Document Type',
                                       required=True, ondelete='restrict')
    name = fields.Char(related='document_type_id.name', store=True, string='Document')
    sequence = fields.Integer(related='document_type_id.sequence', store=True)
    # attachment=True keeps the binary in ir.attachment (private, access-controlled).
    attachment = fields.Binary('File', attachment=True, required=True)
    filename = fields.Char('Filename')
    uploaded_date = fields.Datetime('Uploaded', default=fields.Datetime.now, readonly=True)
