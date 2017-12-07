# -*- encoding: utf-8 -*-


from odoo import models, fields, api


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    available_pos_request = fields.Boolean('Available POS request')
