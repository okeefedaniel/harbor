"""
Template context processor for the signatures app.

Provides ``sig_base_template`` and ``sig_dashboard_url`` so templates can
extend the correct base template in both Harbor and standalone mode.
"""

from .compat import is_harbor


def signstreamer_context(request):
    if is_harbor():
        return {
            'sig_base_template': 'base.html',
            'sig_dashboard_url': 'dashboard',
            'signstreamer_brand': 'Harbor',
        }
    return {
        'sig_base_template': 'signstreamer/base.html',
        'sig_dashboard_url': 'signatures:packet-list',
        'signstreamer_brand': 'Manifest',
    }
