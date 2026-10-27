from django import forms


class CargarArchivoForm(forms.Form):
    archivo = forms.FileField(
        label='Archivo (CSV, XLSX, JSON o PDF)',
        help_text='Tamaño máximo: 50 MB. Los PDF se registran pero no se procesan.',
    )

    def clean_archivo(self):
        archivo = self.cleaned_data['archivo']
        extension = archivo.name.rsplit('.', 1)[-1].lower()
        if extension not in ('csv', 'xlsx', 'xls', 'json', 'pdf'):
            raise forms.ValidationError(
                'Extensión no permitida. Usa CSV, XLSX, JSON o PDF.'
            )
        if archivo.size > 50 * 1024 * 1024:
            raise forms.ValidationError('El archivo supera los 50 MB.')
        return archivo