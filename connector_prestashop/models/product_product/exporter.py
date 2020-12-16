# -*- coding: utf-8 -*-
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html)

from odoo.addons.component.core import Component
from odoo import fields


class CombinationInventoryExporter(Component):
    _name = 'prestashop.product.combination.inventory.exporter'
    _inherit = 'prestashop.product.template.inventory.exporter'
    _apply_on = 'prestashop.product.combination'

    _usage = 'inventory.exporter'

    def get_filter(self, product):
        return {
            'filter[id_product]': product.main_template_id.prestashop_id,
            'filter[id_product_attribute]': product.prestashop_id,
        }

    def get_quantity_vals(self, product):
        datas = {
            'quantity': int(product.quantity),
            'out_of_stock': int(product.main_template_id.out_of_stock),
        }
        
        if product.next_available_date :
            next_available_date = product.next_available_date
            if isinstance(next_available_date, str):
                next_available_date = fields.Date.from_string(product.next_available_date)
           
            datas.update({
                'available_date_attribute': next_available_date.strftime('%Y-%m-%d')
                })

        
        return datas