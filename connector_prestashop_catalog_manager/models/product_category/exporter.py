# -*- coding: utf-8 -*-
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html)

from slugify import slugify

from odoo import fields, _

from odoo.addons.component.core import Component
from odoo.addons.connector.components.mapper import mapping, external_to_m2o

import datetime
import logging
_logger = logging.getLogger(__name__)
try:
    from prestapyt import PrestaShopWebServiceError
except:
    _logger.debug('Cannot import from `prestapyt`')


class ProductCategoryMapper(Component):
    _name = 'prestashop.product.category.export.mapper'
    _inherit = 'translation.prestashop.export.mapper'
    _apply_on = 'prestashop.product.category'
    _model_name = 'prestashop.product.category'

    _translatable_fields = [
        ('name', 'name'),
        ('description', 'description'),
        ('meta_description', 'meta_description'),
        ('meta_keywords', 'meta_keywords'),
        ('meta_title', 'meta_title'),
    ]

    direct = [
        # ('active', 'active'),
        ('position', 'position'),
    ]

    @mapping
    def link_rewrite(self, record):
        value = {'language': []}
        records_by_lang = self._get_record_by_lang(record)
        for language_id, trans_record in records_by_lang.items():
            value['language'].append({
                'attrs': {'id': str(language_id)},
                'value': record.link_rewrite or slugify(record.name),
            })
        return {'link_rewrite': value}

    @mapping
    def active(self, record):
        return {'active': 1}

    @mapping
    def parent_id(self, record):
        if not record.parent_id:
            return {'id_parent': 2}
        category_binder = self.binder_for('prestashop.product.category')
        ext_categ_id = category_binder.to_external(
            record.parent_id.id, wrap=True
        )
        return {
            'id_parent': ext_categ_id,
        }

    @mapping
    def data_add(self, record):
        if record.create_date:
            return {'date_add': fields.Date.from_string(record.create_date).strftime('%Y-%m-%d %H:%M:%S')}
        else:
            return {'date_add': datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

    @mapping
    def data_upd(self, record):
        if record.write_date:
            return {'date_upd': fields.Date.from_string(record.write_date).strftime('%Y-%m-%d %H:%M:%S')}
        else:
            return {'date_upd': datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}


class ProductCategoryExporter(Component):
    _name = 'prestashop.product.category.exporter'
    _inherit = 'translation.prestashop.exporter'
    _apply_on = 'prestashop.product.category'
    _model_name = 'prestashop.product.category'

    _translatable_fields = {
         
        'prestashop.product.category': [
            'name',
            'description',
            'link_rewrite',
            'meta_description',
            'meta_keywords',
            'meta_title'
        ],
    }

    def _export_dependencies(self):
        """ Export the simple delivery before export lines """
        record = self.binding and self.binding.odoo_id
        if record and record.parent_id:
            self._export_dependency(record.parent_id, 'prestashop.product.category')
            
            
    def _run(self, fields=None, **kwargs):
        if self.binding.prestashop_id:
            self.binding.import_record(self.binding.backend_id, self.binding.prestashop_id)
        return super(ProductCategoryExporter, self)._run(fields=fields, **kwargs)            
