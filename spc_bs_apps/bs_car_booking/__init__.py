# -*- coding: utf-8 -*-
# Part of Basic Solution Co., Ltd.

from . import models
from . import controllers


def post_init_hook(env):
    """Enable automatic invoicing so deposit (down-payment) invoices are
    generated and reconciled automatically when a deposit payment succeeds."""
    env['ir.config_parameter'].sudo().set_param('sale.automatic_invoice', 'True')
