from django import forms

from core.custom_forms import FormularioBase

from .models import Usuario


class LoginForm(forms.Form):
    username = forms.CharField(label='Usuario', max_length=150,
                               widget=forms.TextInput(attrs={'autofocus': 'autofocus',
                                                             'placeholder': 'Usuario'}))
    password = forms.CharField(label='Contraseña',
                               widget=forms.PasswordInput(attrs={'placeholder': 'Contraseña'}))


class PerfilForm(FormularioBase):
    class Meta:
        model = Usuario
        fields = ('first_name', 'last_name', 'email', 'cedula', 'telefono', 'foto')
        labels = {
            'first_name': 'Nombres',
            'last_name': 'Apellidos',
            'email': 'Correo electrónico',
            'cedula': 'Cédula',
            'telefono': 'Teléfono',
            'foto': 'Foto',
        }


class CambiarClaveForm(forms.Form):
    clave_actual = forms.CharField(label='Contraseña actual', widget=forms.PasswordInput)
    clave_nueva = forms.CharField(label='Contraseña nueva', widget=forms.PasswordInput, min_length=8)
    clave_confirmacion = forms.CharField(label='Repetir contraseña nueva', widget=forms.PasswordInput)

    def clean(self):
        datos = super().clean()
        if datos.get('clave_nueva') != datos.get('clave_confirmacion'):
            raise forms.ValidationError('Las contraseñas nuevas no coinciden.')
        return datos
