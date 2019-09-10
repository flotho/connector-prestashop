# -*- coding: utf-8 -*-
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html)

from openerp.addons.connector.unit.mapper import ImportMapper, mapping, only_create
from ...unit.importer import TranslatableRecordImporter, DirectBatchImporter
from ...backend import prestashop


@prestashop
class SaleOrderStateMapper(ImportMapper):
    _model_name = 'prestashop.sale.order.state'

    direct = [
        ('name', 'name'),
    ]

    @mapping
    def backend_id(self, record):
        return {'backend_id': self.backend_record.id}

    @mapping
    def company_id(self, record):
        return {'company_id': self.backend_record.company_id.id}
    
    @only_create
    @mapping
    def openerp_id(self, record):
        """ Will bind the product attribute to an existing one with the same name """
        name = record['name']
        ps_id = record['id']
            
        state = self.env['sale.order.state'].search(
            [('name', '=', name),
             ])
        if not state.id:
            ps_state = self.env['prestashop.sale.order.state'].search(
                [('openerp_id', '=', ps_id )])
            state = ps_state.openerp_id 
        if state.id :
                return {'openerp_id': state.id}                    
        else:
            return {}


@prestashop
class SaleOrderStateImporter(TranslatableRecordImporter):
    """ Import one translatable record """
    _model_name = [
        'prestashop.sale.order.state',
    ]

    _translatable_fields = {
        'prestashop.sale.order.state': [
            'name',
        ],
    }


@prestashop
class SaleOrderStateBatchImporter(DirectBatchImporter):
    _model_name = 'prestashop.sale.order.state'
