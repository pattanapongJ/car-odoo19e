# -*- coding: utf-8 -*-
# Part of Basic Solution Co., Ltd.

import logging
from email.utils import formataddr

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

        # A deposit (partial) payment only gets its deposit line added to the
        # order during _invoice_sale_orders → _generate_downpayment_invoices,
        # which the native payment _post_process runs AFTER this hook. Sending
        # now would attach a Sale Order PDF that is missing the deposit line
        # (the symptom: the e-mailed PDF has no deposit line, while a later UI
        # print does). So defer those orders to the _generate_downpayment_invoices
        # override below; only orders already fully paid — which never generate a
        # down payment — are safe to send right here.
        booking_orders.filtered(lambda o: o._is_paid())._bs_send_booking_payment_mail()

    def _generate_downpayment_invoices(self):
        """Send the booking "payment received" mail once the deposit line has
        been added to the order AND its down-payment invoice is posted, so the
        e-mailed documents reflect a posted invoice (with its real number) and
        not a draft.

        ``super()`` creates the deposit line + a *draft* down-payment invoice;
        the native flow only posts it later (account_payment._post_process →
        ``action_post``), after this method returns. We post it here first so
        the rendering is not draft. account_payment skips already-posted
        invoices, so this does not double-post. This is the sole step that
        creates the deposit line for a partial payment, and its only caller is
        the payment auto-invoice flow, so it is the correct (and only) place to
        send the deferred mail. See _send_payment_succeeded_for_order_mail.
        """
        invoices = super()._generate_downpayment_invoices()
        # Post the freshly-created draft down-payment invoice(s) before render.
        invoices.filtered(lambda m: m.state == 'draft').sudo().action_post()
        self.filtered(lambda o: o._is_bs_car_deposit_order())._bs_send_booking_payment_mail()
        return invoices

    def _bs_send_booking_payment_mail(self):
        """Render + send the branded bilingual payment-received mail (Sale Order
        PDF + booking contract) for each car-booking order in ``self``.

        Exception-safe: this now runs inside the deposit-invoice transaction, so
        a mail/SMTP failure must never propagate and roll back the invoice.
        Falls back to the standard payment template when the custom one is
        missing or rendering fails.
        """
        template = self.env.ref(
            'bs_car_booking_report.mail_template_sale_payment_executed_booking',
            raise_if_not_found=False,
        )
        for order in self:
            try:
                if template:
                    order._bs_send_payment_mail_with_contract(template)
                else:
                    # Custom template missing — never silently drop the notification.
                    super(SaleOrder, order)._send_payment_succeeded_for_order_mail()
            except Exception:
                _logger.warning(
                    'Car-booking payment mail failed for order %s; '
                    'falling back to standard template.', order.name, exc_info=True,
                )
                try:
                    super(SaleOrder, order)._send_payment_succeeded_for_order_mail()
                except Exception:
                    _logger.warning(
                        'Standard fallback payment mail also failed for order %s.',
                        order.name, exc_info=True,
                    )

    def _bs_send_payment_mail_with_contract(self, template):
        """Attach the configured payment-mail documents and send.

        The attachment set is built by :meth:`_bs_payment_mail_attachment_specs`
        so sub-modules (e.g. a localisation) can swap or add documents without
        copying this send logic.
        """
        self.ensure_one()
        order = self.with_user(SUPERUSER_ID) if self.env.su else self
        Attachment = order.env['ir.attachment'].sudo()
        attachments = Attachment.browse()
        for report_ref, res_ids, filename in order._bs_payment_mail_attachment_specs():
            attachments |= order._bs_render_report_attachment(report_ref, res_ids, filename)

        template.sudo().send_mail(
            order.id,
            force_send=True,
            email_values={'attachment_ids': attachments.ids},
            email_layout_xmlid='mail.mail_notification_layout_with_responsible_signature',
        )

    def _bs_payment_mail_email_from(self):
        """From-address shown to the customer for the booking payment mail.

        Display name = the website (brand) name, matching the booking
        confirmation mail (_send_booking_notification), so the sender stays
        consistent across the journey instead of flipping between the brand and
        the company legal name.
        """
        self.ensure_one()
        booking = self.bs_booking_ids[:1]
        company = (booking.website_id.company_id or self.company_id or self.env.company).sudo()
        email = company.email or self.env['ir.mail_server'].sudo()._get_default_from_address()
        brand = (booking.website_id.name if booking else False) or company.name
        if email and brand:
            return formataddr((brand, email))
        return email or self.env.user.email_formatted

    def _bs_payment_mail_sale_report_ref(self):
        """XML id of the report used for the 'sale document' attachment on the
        booking payment mail. Overridable so a localisation can swap in its own
        quotation report (the standard Sale Order PDF by default)."""
        return 'sale.action_report_saleorder'

    def _bs_payment_mail_attachment_specs(self):
        """``(report_ref, res_ids, filename)`` tuples to attach to the booking
        payment mail. Defaults to the sale document + the booking contract;
        extend in sub-modules to add or replace attachments."""
        self.ensure_one()
        specs = [(
            self._bs_payment_mail_sale_report_ref(),
            self.ids,
            '%s.pdf' % (self.name or 'order'),
        )]
        booking = self.bs_booking_ids[:1]
        if booking:
            specs.append((
                'bs_car_booking_report.report_booking_individual',
                booking.ids,
                '%s_contract.pdf' % (booking.name or 'booking'),
            ))
        return specs

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
