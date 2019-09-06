# -*- coding: utf-8 -*-
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html)


from ...unit.auto_matching_importer import AutoMatchingImporter
from ...backend import prestashop


@prestashop
class CountryImporter(AutoMatchingImporter):
    _model_name = 'prestashop.res.country'
    _erp_field = 'code'
    _ps_field = 'iso_code'

    def _compare_function(self, ps_val, erp_val, ps_dict, erp_dict):
        if len(erp_val) == len(ps_val)  and \
                erp_val.lower() == ps_val.lower():
            return True
        return False
