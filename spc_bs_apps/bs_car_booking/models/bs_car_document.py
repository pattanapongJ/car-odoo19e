# -*- coding: utf-8 -*-
# Part of Basic Solution Co., Ltd.

from odoo import api, fields, models


class BsCarDocumentType(models.Model):
    """Admin-configurable document a customer must provide at booking.
    `applies_to` + `required` drive what the funnel asks for per customer type."""
    _name = 'bs.car.document.type'
    _description = 'Customer Document Type'
    _order = 'sequence, id'

    name = fields.Char('Document', required=True, translate=True)
    company_id = fields.Many2one(
        'res.company', string='Company', default=lambda self: self.env.company,
        index=True, help='Leave empty to share this document type across companies.')
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
    name = fields.Char(related='document_type_id.name', string='Document')
    sequence = fields.Integer(related='document_type_id.sequence', store=True)
    # attachment=True keeps the binary in ir.attachment (private, access-controlled).
    attachment = fields.Binary('File', attachment=True, required=True)
    filename = fields.Char('Filename')
    uploaded_date = fields.Datetime('Uploaded', default=fields.Datetime.now, readonly=True)
    # Mirror of this file linked to the parent booking so it also shows in the
    # booking's chatter attachment box. Lifecycle-managed (created/updated/removed
    # alongside this line) so no orphaned PII is ever left behind — PDPA-safe.
    booking_attachment_id = fields.Many2one('ir.attachment', string='Booking Attachment',
                                            copy=False, readonly=True, ondelete='set null')

    def _sync_booking_attachment(self):
        """Keep a booking-level ir.attachment mirror in sync with this line so
        uploaded documents are visible from the booking's attachment box."""
        Attachment = self.env['ir.attachment'].sudo()
        for rec in self:
            if not rec.attachment or not rec.booking_id:
                if rec.booking_attachment_id:
                    rec.booking_attachment_id.sudo().unlink()
                continue
            vals = {
                'name': rec.filename or rec.name or 'document',
                'datas': rec.attachment,
                'res_model': 'bs.car.booking',
                'res_id': rec.booking_id.id,
            }
            if rec.booking_attachment_id:
                rec.booking_attachment_id.sudo().write(vals)
            else:
                # Assigning the m2o triggers write() but without a mirrored key,
                # so it does not re-enter the sync (no recursion).
                rec.booking_attachment_id = Attachment.create(vals)

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        records._sync_booking_attachment()
        return records

    def write(self, vals):
        res = super().write(vals)
        if {'attachment', 'filename', 'booking_id'} & vals.keys():
            self._sync_booking_attachment()
        return res

    def unlink(self):
        self.booking_attachment_id.sudo().unlink()
        return super().unlink()
