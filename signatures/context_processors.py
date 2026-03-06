"""
Template context processor for the signatures app.

Provides ``sig_base_template`` and ``sig_dashboard_url`` so templates can
extend the correct base template in both Grantify and standalone mode.
"""

from .compat import is_grantify


def signflow_context(request):
    if is_grantify():
        return {
            'sig_base_template': 'base.html',
            'sig_dashboard_url': 'dashboard',
            'signflow_brand': 'Grantify',
        }
    return {
        'sig_base_template': 'signflow/base.html',
        'sig_dashboard_url': 'signatures:packet-list',
        'signflow_brand': 'SignFlow',
    }
