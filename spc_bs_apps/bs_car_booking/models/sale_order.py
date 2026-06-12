# -*- coding: utf-8 -*-
# Part of Basic Solution Co., Ltd.

from odoo import fields, models
from odoo.tools import format_date, formatLang
from odoo.tools.translate import _


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    # Reverse link to the booking(s) backing this order — used to scope the
    # "Down Payment" → "Deposit" relabelling to car-booking orders only, so
    # ordinary sale orders/invoices keep Odoo's standard wording.
    bs_booking_ids = fields.One2many('bs.car.booking', 'sale_order_id', string='Car Bookings')

    def _is_bs_car_deposit_order(self):
        """True when this order backs a car booking (its down payment is a
        booking *deposit*)."""
        self.ensure_one()
        return bool(self.bs_booking_ids)

    def _prepare_down_payment_section_line(self, **optional_values):
        """Rename the invoice down-payment *section* to "Deposits" for car
        bookings (the SO section name is driven by
        ``sale.order.line._get_downpayment_description``)."""
        vals = super()._prepare_down_payment_section_line(**optional_values)
        if 'name' not in optional_values and self._is_bs_car_deposit_order():
            vals['name'] = _("Deposits")
        return vals


class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    def _get_downpayment_description(self):
        """Use "Deposit" wording on car-booking order lines (covers both the
        down-payment line and the down-payment section line)."""
        if self.order_id._is_bs_car_deposit_order():
            return self._get_bs_deposit_description()
        return super()._get_downpayment_description()

    def _get_bs_deposit_description(self):
        """Deposit-worded mirror of the standard ``_get_downpayment_description``."""
        self.ensure_one()
        if self.display_type:
            return _("Deposits")

        dp_state = self._get_downpayment_state()
        name = _("Deposit")
        if dp_state == 'draft':
            name = _(
                "Deposit: %(date)s (Draft)",
                date=format_date(self.env, self.create_date.date()),
            )
        elif dp_state == 'cancel':
            name = _("Deposit (Cancelled)")
        else:
            invoice = self._get_invoice_lines().filtered(
                lambda aml: aml.quantity >= 0
            ).move_id.filtered(lambda move: move.move_type == 'out_invoice')
            if len(invoice) == 1 and invoice.payment_reference and invoice.invoice_date:
                name = _(
                    "Deposit (ref: %(reference)s on %(date)s)",
                    reference=invoice.payment_reference,
                    date=format_date(self.env, invoice.invoice_date),
                )
        return name


class SaleAdvancePaymentInv(models.TransientModel):
    _inherit = 'sale.advance.payment.inv'

    def _prepare_down_payment_invoice_line_values(self, order, so_line, account):
        """Relabel the down-payment *invoice* line to "Deposit" for car bookings."""
        vals = super()._prepare_down_payment_invoice_line_values(order, so_line, account)
        if order._is_bs_car_deposit_order():
            self = self.with_context(lang=order._get_lang())
            if self.advance_payment_method == 'percentage':
                vals['name'] = self.env._("Deposit of %s%%", formatLang(self.env, self.amount))
            else:
                vals['name'] = self.env._("Deposit")
        return vals
