from django import forms
from django.core.validators import MinValueValidator, MaxValueValidator
from django.contrib.admin.widgets import AdminDateWidget
from .models import Project

class PayForm(forms.Form):
    amount = forms.IntegerField(validators=[MinValueValidator(0)])
    donor = forms.SlugField(required=False)


class ProjectForm(forms.ModelForm):
    description = forms.CharField(widget=forms.Textarea(attrs={'rows': 20, 'cols': 120}))
    weight = forms.IntegerField(validators=[MinValueValidator(0), MaxValueValidator(100)])
    threshold = forms.IntegerField(validators=[MinValueValidator(0)], required=False)
    limit = forms.IntegerField(validators=[MinValueValidator(0)], required=False)
    expiration_time = forms.DateField(widget=AdminDateWidget, required=False)

    class Meta:
        model = Project
        fields = '__all__'

    def clean_weight(self):
        weight = self.cleaned_data['weight']

        try:
            parent = self.instance.parent
            title = self.instance.title
        except:
            parent = self.cleaned_data['parent']
            title = self.cleaned_data['title']

        if parent is not None:
            siblings = parent.get_children().exclude(pk=title)

            total_weight = weight
            for node in siblings:
                total_weight += int(node.weight)

            weight_available = 100 - (total_weight - weight)

            if total_weight > 100:
                raise forms.ValidationError('Maximum weight exceeded, select a number less than or equal to ' + str(weight_available))

        return weight


class ProjectFormUser(ProjectForm):
    class Meta(ProjectForm.Meta):
        exclude = ['parent', 'state']

    def __init__(self, *args, **kwargs):
        if 'parent' in kwargs:
            parent = kwargs.pop('parent')
            super(ProjectForm, self).__init__(*args, **kwargs)
            self.instance.parent = parent
        else:
            super(ProjectForm, self).__init__(*args, **kwargs)

        # Bootstrap style on fields
        for visible in self.visible_fields():
            visible.field.widget.attrs['class'] = 'form-control form-control-sm'
