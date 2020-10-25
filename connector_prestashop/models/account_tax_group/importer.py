# -*- coding: utf-8 -*-
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html)

from odoo.addons.connector.components.mapper import (
    mapping,
    only_create,
)
from odoo.addons.component.core import Component

import logging
_logger = logging.getLogger(__name__)

class TaxGroupMapper(Component):
    _name = 'prestashop.account.tax.group.import.mapper'
    _inherit = 'prestashop.import.mapper'
    _apply_on = 'prestashop.account.tax.group'

    _model_name = 'prestashop.account.tax.group'

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
    def odoo_id(self, record):
        tax_group = self.env['account.tax.group'].search([
            ('name', '=', record['name'])
        ])
        if tax_group:
            return {'odoo_id': tax_group.id}


class TaxGroupImporter(Component):
    _name = 'prestashop.account.tax.group.importer'
    _inherit = 'prestashop.importer'
    _apply_on = 'prestashop.account.tax.group'

#     _model_name = 'prestashop.account.tax.group'


    def _has_to_skip(self):
        """ Return True if the import can be skipped """
        skip =  not self.prestashop_record.get('active', False) or self.prestashop_record.get('deleted', False)
        _logger.debug("Taxes group %s has to be skipped because of its states %s ?" % (self.prestashop_record, skip))
        return skip
       

class TaxGroupBatchImporter(Component):
    _name = 'prestashop.account.tax.group.direct.batch.importer'
    _inherit = 'prestashop.direct.batch.importer'
    _apply_on = 'prestashop.account.tax.group'

#     _model_name = 'prestashop.account.tax.group'
