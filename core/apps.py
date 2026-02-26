from django.apps import AppConfig


class CoreConfig(AppConfig):
    name = 'core'

    def ready(self):
        from allauth.account.signals import user_signed_up

        def on_user_signed_up(sender, request, user, **kwargs):
            from core.notifications import notify_new_user_registered
            notify_new_user_registered(user)

        user_signed_up.connect(on_user_signed_up)
