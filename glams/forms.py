import datetime

from django import forms
from .models import Institution, Glam


class InstitutionForm(forms.ModelForm):
    class Meta:
        model = Institution
        fields = ["name_pt", "name_en", "wikidata", "website_url", "location"]
        widgets = {
            "name_pt": forms.TextInput(attrs={'class': 'form_field'}),
            "name_en": forms.TextInput(attrs={'class': 'form_field'}),
            "wikidata": forms.TextInput(attrs={'class': 'form_field'}),
            "website_url": forms.URLInput(attrs={'class': 'form_field'}),
            "location": forms.Select(attrs={'class': 'form_field'}),
        }


class GlamForm(forms.ModelForm):
    class Meta:
        model = Glam
        fields = ["name_pt", "name_en", "acronym", "wikidata", "website_url", "category_url", "start_date", "end_date",
                  "institutions"]

        widgets = {
            "name_pt": forms.TextInput(attrs={'class': 'form_field', 'required': True}),
            "name_en": forms.TextInput(attrs={'class': 'form_field', 'required': True}),
            "acronym": forms.TextInput(attrs={'class': 'form_field', 'required': True}),
            "wikidata": forms.TextInput(attrs={'class': 'form_field', 'required': True}),
            "website_url": forms.URLInput(attrs={'class': 'form_field', 'required': True}),
            "category_url": forms.URLInput(attrs={'class': 'form_field', 'required': True}),
            "start_date": forms.DateTimeInput(attrs={'type': 'date', 'max': datetime.datetime.today(), 'class': 'form_field', 'required': True}),
            "end_date": forms.DateTimeInput(attrs={'type': 'date', 'max': datetime.datetime.today(), 'class': 'form_field'}),
            "institutions": forms.SelectMultiple(attrs={'class': 'form_field', 'required': True}),
        }
