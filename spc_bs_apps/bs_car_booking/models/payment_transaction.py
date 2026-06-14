# -*- coding: utf-8 -*-
# Part of Basic Solution Co., Ltd.

import logging

from odoo import api, fields, models

_logger = logging.getLogger(__name__)


class PaymentTransaction(models.Model):
    _inherit = 'payment.transaction'

    booking_id = fields.Many2one('bs.car.booking', string='Car Booking', readonly=True,
                                 help='Linked car booking for this deposit payment.')

    @api.model_create_multi
    def create(self, vals_list):
        transactions = super().create(vals_list)
        transactions.sudo()._link_booking_from_sale_orders()
        return transactions

    def _link_booking_from_sale_orders(self):
        """Attach website booking transactions created through the sale payment route.

        Priority: sale_order_ids (native payment_sale link) → reference → source.

        Demo/provider edge case: some providers do NOT populate sale_order_ids
        before _post_process runs (the transaction is created first, linked to
        the sale order later). In that case the transaction reference normally
        IS the sale order name (S00067), so we fall back to a name search.
        """
        Booking = self.env['bs.car.booking'].sudo()
        Order = self.env['sale.order'].sudo()
        for tx in self:
            if tx.booking_id:
                continue
            sale_orders = tx.sale_order_ids or tx.source_transaction_id.sale_order_ids
            if not sale_orders and tx.reference:
                # Company filter: sale sequences restart per company, so two
                # companies can both own an "S00067" — never cross-match.
                sale_orders = Order.search([
                    ('name', '=', tx.reference),
                    ('company_id', '=', tx.company_id.id),
                ], limit=1)
            if not sale_orders:
                continue
            booking = Booking.search([('sale_order_id', 'in', sale_orders.ids)], limit=1)
            if booking:
                tx.write({'booking_id': booking.id})
        return True

    def _post_process(self):
        """Drive the car-booking deposit flow on top of the native sale logic.

        Sequence for a paid deposit transaction:
          1. Force-confirm the booking's sale order.
          2. ``super()._post_process()`` — invoice, payment, PDF — wrapped in
             a savepoint so a non-critical failure (e.g. Thai QR-code on the
             invoice PDF) does NOT roll back the booking confirmation.
          3. Sync booking status/deposit.
        """
        self.sudo()._link_booking_from_sale_orders()
        self.invalidate_recordset(['booking_id'])
        booked = self.filtered(
            lambda t: t.state == 'done'
            and t.booking_id
            and t.booking_id.state == 'payment_pending'
        )
        for tx in booked:
            order = tx.booking_id.sale_order_id.sudo()
            if order and order.state in ('draft', 'sent'):
                order.with_context(send_email=False).action_confirm()

        savepoint = self.env.cr.savepoint()
        try:
            res = super()._post_process()
        except Exception:
            savepoint.rollback()
            _logger.warning(
                'Invoice post-processing failed for tx %s — booking sync continues.',
                self.reference, exc_info=True,
            )
            res = True

        for tx in booked:
            try:
                tx.booking_id.sudo()._on_deposit_paid(tx)
            except Exception:
                _logger.warning('Booking %s post-payment sync failed.',
                                tx.booking_id.name, exc_info=True)
        return res
