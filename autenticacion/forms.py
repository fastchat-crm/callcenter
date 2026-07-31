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


class RegistroForm(forms.Form):
    """Alta pública. Pide lo mínimo: quién es, qué empresa y cómo entrar."""

    empresa = forms.CharField(label='Nombre de la empresa', max_length=120)
    nombres = forms.CharField(label='Tu nombre', max_length=120)
    email = forms.EmailField(label='Correo electrónico')
    username = forms.CharField(label='Usuario', max_length=150)
    clave = forms.CharField(label='Contraseña', widget=forms.PasswordInput, min_length=8)
    clave_confirmacion = forms.CharField(label='Repetir contraseña', widget=forms.PasswordInput)

    def clean_empresa(self):
        from clientes.models import Cliente

        nombre = (self.cleaned_data['empresa'] or '').strip()
        if Cliente.objects.filter(nombre__iexact=nombre, status=True).exists():
            raise forms.ValidationError('Ya hay una cuenta con ese nombre de empresa.')
        return nombre

    def clean_username(self):
        nombre = (self.cleaned_data['username'] or '').strip().lower()
        if Usuario.objects.filter(username__iexact=nombre).exists():
            raise forms.ValidationError('Ese usuario ya está tomado.')
        return nombre

    def clean_email(self):
        correo = (self.cleaned_data['email'] or '').strip().lower()
        if Usuario.objects.filter(email__iexact=correo).exists():
            raise forms.ValidationError('Ya hay una cuenta con ese correo.')
        return correo

    def clean(self):
        datos = super().clean()
        if datos.get('clave') != datos.get('clave_confirmacion'):
            raise forms.ValidationError('Las contraseñas no coinciden.')
        return datos
