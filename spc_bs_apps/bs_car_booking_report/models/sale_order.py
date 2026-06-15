# -*- coding: utf-8 -*-
# Part of Basic Solution Co., Ltd.

import logging

from odoo import SUPERUSER_ID, models

_logger = logging.getLogger(__name__)


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    # Report module is the right home for this override: it depends on
    # bs_car_booking (so _is_bs_car_deposit_order / bs_booking_ids exist) AND
    # owns the booking-contract report. Putting it in bs_car_booking would mean
    # bs_car_booking referencing a report it does not depend on (circular).
    def _send_payment_succeeded_for_order_mail(self):
        """Car-booking orders get a branded bilingual "payment received" mail
        carrying BOTH the Sale Order PDF and the booking-contract PDF.

        Ordinary sale orders are untouched — they fall through to the standard
        ``sale.mail_template_sale_payment_executed`` flow.
        """
        booking_orders = self.filtered(lambda o: o._is_bs_car_deposit_order())
        other_orders = self - booking_orders
        if other_orders:
            super(SaleOrder, other_orders)._send_payment_succeeded_for_order_mail()

        if not booking_orders:
            return

        template = self.env.ref(
            'bs_car_booking_report.mail_template_sale_payment_executed_booking',
            raise_if_not_found=False,
        )
        if not template:
            # Custom template missing — never silently drop the notification.
            return super(SaleOrder, booking_orders)._send_payment_succeeded_for_order_mail()

        for order in booking_orders:
            try:
                order._bs_send_payment_mail_with_contract(template)
            except Exception:
                _logger.warning(
                    'Car-booking payment mail failed for order %s; '
                    'falling back to standard template.', order.name, exc_info=True,
                )
                super(SaleOrder, order)._send_payment_succeeded_for_order_mail()

    def _bs_send_payment_mail_with_contract(self, template):
        """Render the Sale Order PDF + booking-contract PDF, attach both, send."""
        self.ensure_one()
        order = self.with_user(SUPERUSER_ID) if self.env.su else self
        Attachment = order.env['ir.attachment'].sudo()
        attachments = Attachment.browse()

        # 1) Sale Order PDF (same document the standard mail attaches).
        attachments |= order._bs_render_report_attachment(
            'sale.action_report_saleorder', order.ids, '%s.pdf' % (order.name or 'order'),
        )

        # 2) Booking contract PDF (rendered against the bs.car.booking record).
        booking = order.bs_booking_ids[:1]
        if booking:
            attachments |= order._bs_render_report_attachment(
                'bs_car_booking_report.report_booking_individual', booking.ids,
                '%s_contract.pdf' % (booking.name or 'booking'),
            )

        template.sudo().send_mail(
            order.id,
            force_send=True,
            email_values={'attachment_ids': attachments.ids},
            email_layout_xmlid='mail.mail_notification_layout_with_responsible_signature',
        )

    def _bs_render_report_attachment(self, report_ref, res_ids, filename):
        """Render a QWeb-PDF report to a (non-persisted-binding) ir.attachment.

        Returns an empty recordset on any rendering failure so one broken PDF
        never blocks the mail or the other attachment.
        """
        Attachment = self.env['ir.attachment'].sudo()
        report = self.env.ref(report_ref, raise_if_not_found=False)
        if not report:
            return Attachment.browse()
        try:
            pdf_content, _dummy = self.env['ir.actions.report'].sudo()._render_qweb_pdf(
                report_ref, res_ids,
            )
        except Exception:
            _logger.warning('Failed rendering report %s for %s.', report_ref, res_ids, exc_info=True)
            return Attachment.browse()
        return Attachment.create({
            'name': filename,
            'type': 'binary',
            'raw': pdf_content,
            'mimetype': 'application/pdf',
            'res_model': 'sale.order',
            'res_id': self.id,
        })
