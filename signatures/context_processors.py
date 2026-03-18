"""
Template context processor for the signatures app.

Provides ``sig_base_template`` and ``sig_dashboard_url`` so templates can
extend the correct base template in both Beacon and standalone mode.
"""

from .compat import is_beacon


def signstreamer_context(request):
    if is_beacon():
        return {
            'sig_base_template': 'base.html',
            'sig_dashboard_url': 'dashboard',
            'signstreamer_brand': 'Beacon',
        }
    return {
        'sig_base_template': 'signstreamer/base.html',
        'sig_dashboard_url': 'signatures:packet-list',
        'signstreamer_brand': 'Manifest',
    }
