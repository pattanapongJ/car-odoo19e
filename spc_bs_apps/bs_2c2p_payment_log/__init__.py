# -*- coding: utf-8 -*-
from . import models
from . import controllers
from odoo.addons.payment import setup_provider


def post_init_hook(env):
    setup_provider(env, 'to_c_to_p')
    env['payment.provider'].search([
        ('code', '=', 'to_c_to_p'),
        ('state', 'in', ['enabled', 'test']),
    ]).write({'is_published': True})
