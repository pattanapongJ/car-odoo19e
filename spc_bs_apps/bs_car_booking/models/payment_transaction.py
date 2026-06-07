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

        The native sale portal payment route only sets ``sale_order_ids`` on the
        transaction. Without this link the booking-specific post-processing would
        never run for a real browser payment.
        """
        Booking = self.env['bs.car.booking'].sudo()
        for tx in self:
            if tx.booking_id:
                continue
            sale_orders = tx.sale_order_ids or tx.source_transaction_id.sale_order_ids
            if not sale_orders:
                continue
            booking = Booking.search([('sale_order_id', 'in', sale_orders.ids)], limit=1)
            if booking:
                tx.write({'booking_id': booking.id})
        return True

    def _post_process(self):
        """Drive the car-booking deposit flow on top of the native sale logic.

        Sequence for a paid deposit transaction:
          1. Force-confirm the booking's sale order (dealer deposit always
             confirms the order, regardless of the prepayment threshold) so
             that the native ``sale`` post-processing generates and posts the
             down-payment (deposit) invoice and reconciles the payment.
          2. Let ``super()`` run (sale + account_payment): invoice creation,
             posting, account.payment creation and reconciliation.
          3. Sync the booking status/deposit.
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

        res = super()._post_process()

        for tx in booked:
            try:
                tx.booking_id.sudo()._on_deposit_paid(tx)
            except Exception as e:  # noqa: BLE001 - never break payment post-processing
                _logger.warning('Booking %s post-payment sync failed: %s',
                                tx.booking_id.name, str(e))
        return res
