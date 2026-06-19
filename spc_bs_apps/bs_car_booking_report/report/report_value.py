# -*- coding: utf-8 -*-
from num2words import num2words
from odoo import api, models


class BookingContractReport(models.AbstractModel):
    _name = 'report.bs_car_booking_report.report_booking_individual_document'
    _description = 'Car Booking Contract Report'

    @api.model
    def _get_report_values(self, docids, data=None):
        docs = self.env['bs.car.booking'].browse(docids)
        return {
            'doc_ids': docids,
            'doc_model': 'bs.car.booking',
            'docs': docs,
            'data': data,
            'amount_to_text_th': self._amount_to_text_th,
            'option_values_th': self._option_values_th,
        }

    def _option_values_th(self, record):
        values = record.option_value_ids.with_context(lang='th_TH')
        if values:
            return ', '.join(values.mapped('name'))
        # fallback: dynamic-variant attributes stored on the resolved product variant
        if record.product_id:
            values = record.product_id.product_template_attribute_value_ids.filtered(
                lambda v: v.attribute_id.name != 'Standard Package'
            ).with_context(lang='th_TH')
            return ', '.join(values.mapped('name'))
        return ''

    def _amount_to_text_th(self, amount):
        try:
            satang = round((float(amount) % 1) * 100)
            baht = int(amount)
            if satang == 0:
                return num2words(baht, lang='th', to='currency')
            baht_text = num2words(baht, lang='th')
            satang_text = num2words(satang, lang='th')
            return '%sบาท%sสตางค์' % (baht_text, satang_text)
        except Exception:
            return ''
