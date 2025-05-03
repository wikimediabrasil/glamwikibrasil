from django.db import models
from django.contrib.auth.models import AbstractUser
from django.utils.translation import gettext_lazy as _


class User(AbstractUser):
    full_name = models.CharField(_("Full name"), max_length=300, blank=True)

    username = models.CharField(_("Username"),
                                max_length=150,
                                unique=True,
                                blank=True,
                                help_text=_("Required. 150 characters or fewer. Letters, digits and @/./+/-/_ only."),
                                error_messages={"unique": _("A user with that username already exists."), })

    def __str__(self):
        return self.username
