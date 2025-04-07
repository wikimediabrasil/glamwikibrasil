from django.db import models
from django.core.validators import RegexValidator
from django.utils.translation import gettext_lazy as _


class Institution(models.Model):
    LOCATION_CHOICES = [
        ("AC", _("Acre")),
        ("AL", _("Alagoas")),
        ("AP", _("Amapá")),
        ("AM", _("Amazonas")),
        ("BA", _("Bahia")),
        ("CE", _("Ceará")),
        ("DF", _("Distrito Federal")),
        ("ES", _("Espírito Santo")),
        ("GO", _("Goiás")),
        ("MA", _("Maranhão")),
        ("MT", _("Mato Grosso")),
        ("MS", _("Mato Grosso do Sul")),
        ("MG", _("Minas Gerais")),
        ("PA", _("Pará")),
        ("PB", _("Paraíba")),
        ("PR", _("Paraná")),
        ("PE", _("Pernambuco")),
        ("PI", _("Piauí")),
        ("RJ", _("Rio de Janeiro")),
        ("RN", _("Rio Grande do Norte")),
        ("RS", _("Rio Grande do Sul")),
        ("RO", _("Rondônia")),
        ("RR", _("Roraima")),
        ("SC", _("Santa Catarina")),
        ("SP", _("São Paulo")),
        ("SE", _("Sergipe")),
        ("TO", _("Tocantins")),
        ("BR", _("Brazil")),
        ("XX", _("International")),
    ]

    name_pt = models.CharField(_("Name in Portuguese"), max_length=500)
    name_en = models.CharField(_("Name in English"), max_length=500)
    wikidata = models.CharField(
        _("Wikidata item for the institution"),
        max_length=30,
        unique=True,
        primary_key=True,
        validators=[
            RegexValidator(
                regex=r"^Q\d+$",
                message=_("Wikidata items must be in the format 'Q123'."),
            )
        ]
    )
    website_url = models.URLField(_("Website of the institution"), blank=True)
    location = models.CharField(_("Location of the institution"), max_length=30, choices=LOCATION_CHOICES)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name_pt or self.name_en


class Glam(models.Model):
    name_pt = models.CharField(_("Name in Portuguese"), max_length=500)
    name_en = models.CharField(_("Name in English"), max_length=500)
    acronym = models.CharField(_("Acronym"), max_length=25)
    wikidata = models.CharField(
        _("Wikidata item for the partnership"),
        max_length=30,
        unique=True,
        primary_key=True,
        validators=[
            RegexValidator(
                regex=r"^Q\d+$",
                message=_("Wikidata items must be in the format 'Q123'."),
            )
        ]
    )
    website_url = models.URLField(_("GLAM page on Wikipedia"))
    category_url = models.URLField(_("GLAM category on Commons"))
    start_date = models.DateField(_("Start date for the partnership"))
    end_date = models.DateField(_("End date for the partnership"), blank=True, null=True)
    institutions = models.ManyToManyField(Institution, verbose_name=_("Institutions of this GLAM"),
                                          related_name="institution_glams")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name_pt or self.name_en
