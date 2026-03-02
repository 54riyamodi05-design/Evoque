from django.core.management.base import BaseCommand
from django.contrib.auth.models import User

from core.models import UserProfile


class Command(BaseCommand):
    help = "Create missing UserProfile rows for existing users."

    def handle(self, *args, **options):
        created_count = 0

        for user in User.objects.all().iterator():
            _, created = UserProfile.objects.get_or_create(
                user=user,
                defaults={
                    'role': 'ADMIN' if (user.is_superuser or user.is_staff) else 'CUSTOMER',
                    'phone': '',
                },
            )
            if created:
                created_count += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"Backfill complete. Created {created_count} UserProfile record(s)."
            )
        )
