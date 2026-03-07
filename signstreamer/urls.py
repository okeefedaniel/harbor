"""SignStreamer standalone URL configuration."""
from django.contrib import admin
from django.contrib.auth.views import LoginView
from django.http import JsonResponse
from django.urls import include, path
from django.conf import settings
from django.conf.urls.static import static


def health_check(request):
    return JsonResponse({'status': 'ok'})


urlpatterns = [
    path('health/', health_check),
    path('admin/', admin.site.urls),
    path('accounts/login/', LoginView.as_view(template_name='signstreamer/login.html'), name='login'),
    path('accounts/', include('django.contrib.auth.urls')),
    path('', include('signatures.urls')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
