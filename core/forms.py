from django import forms


class BootstrapModelForm(forms.ModelForm):
    """Applies Bootstrap 5 CSS classes to every field automatically."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name, field in self.fields.items():
            widget = field.widget
            if name == "color":
                widget.attrs.setdefault("type", "color")
                widget.attrs.setdefault("class", "form-control form-control-color")
            elif isinstance(widget, forms.CheckboxInput):
                widget.attrs.setdefault("class", "form-check-input")
            elif isinstance(widget, (forms.Select, forms.SelectMultiple)):
                widget.attrs.setdefault("class", "form-select")
            else:
                widget.attrs.setdefault("class", "form-control")
