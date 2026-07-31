from django import forms
from django.contrib.auth.models import Group

from autenticacion.models import Usuario
from core.custom_forms import FormularioBase

from .models import GroupModulo, Modulo, ModuloGrupo


class UsuarioForm(FormularioBase):
    grupos = forms.ModelMultipleChoiceField(
        queryset=Group.objects.all().order_by('name'), required=False, label='Roles',
        widget=forms.SelectMultiple(attrs={'size': 6}),
    )
    clave = forms.CharField(
        required=False, label='Contraseña', widget=forms.PasswordInput(render_value=False),
        help_text='En una edición, déjala vacía para no cambiarla.',
    )

    class Meta:
        model = Usuario
        fields = ('username', 'first_name', 'last_name', 'email', 'cedula', 'telefono',
                  'cliente', 'perfil', 'is_active', 'is_staff', 'is_superuser', 'cambiar_clave')
        labels = {
            'username': 'Usuario', 'first_name': 'Nombres', 'last_name': 'Apellidos',
            'email': 'Correo', 'cedula': 'Cédula', 'telefono': 'Teléfono',
            'cliente': 'Cliente', 'perfil': 'Perfil',
            'is_active': 'Activo', 'is_staff': 'Accede al panel', 'is_superuser': 'Superusuario',
            'cambiar_clave': 'Debe cambiar la contraseña al ingresar',
        }
        help_texts = {
            'cliente': 'Vacío: usuario del operador, ve y administra todos los clientes.',
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.pk:
            self.fields['grupos'].initial = self.instance.groups.all()
        else:
            self.fields['clave'].required = True
        self.fields['is_staff'].initial = True

    def clean_username(self):
        username = (self.cleaned_data['username'] or '').strip()
        existentes = Usuario.objects.filter(username__iexact=username)
        if self.instance and self.instance.pk:
            existentes = existentes.exclude(pk=self.instance.pk)
        if existentes.exists():
            raise forms.ValidationError('Ya existe un usuario con ese nombre.')
        return username

    def clean_clave(self):
        clave = self.cleaned_data.get('clave') or ''
        if clave and len(clave) < 8:
            raise forms.ValidationError('La contraseña debe tener al menos 8 caracteres.')
        return clave

    def save(self, commit=True):
        usuario = super().save(commit=False)
        clave = self.cleaned_data.get('clave')
        if clave:
            usuario.set_password(clave)
        if commit:
            usuario.save()
            usuario.groups.set(self.cleaned_data.get('grupos') or [])
        return usuario


class RolForm(forms.ModelForm):
    descripcion = forms.CharField(required=False, label='Descripción',
                                  widget=forms.TextInput(attrs={'class': 'campo'}))

    class Meta:
        model = Group
        fields = ('name',)
        labels = {'name': 'Nombre del rol'}
        widgets = {'name': forms.TextInput(attrs={'class': 'campo', 'required': 'required'})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.pk:
            permisos = GroupModulo.objects.filter(group=self.instance).first()
            if permisos:
                self.fields['descripcion'].initial = permisos.descripcion

    def clean_name(self):
        nombre = (self.cleaned_data['name'] or '').strip()
        existentes = Group.objects.filter(name__iexact=nombre)
        if self.instance and self.instance.pk:
            existentes = existentes.exclude(pk=self.instance.pk)
        if existentes.exists():
            raise forms.ValidationError('Ya existe un rol con ese nombre.')
        return nombre


class ModuloForm(FormularioBase):
    class Meta:
        model = Modulo
        fields = ('nombre', 'url', 'descripcion', 'icono', 'orden', 'visible_menu')
        labels = {
            'nombre': 'Nombre', 'url': 'URL', 'descripcion': 'Descripción',
            'icono': 'Icono', 'orden': 'Orden', 'visible_menu': 'Mostrar en el menú',
        }

    def clean_url(self):
        url = (self.cleaned_data['url'] or '').strip()
        if not url.startswith('/'):
            url = '/' + url
        if not url.endswith('/'):
            url += '/'
        existentes = Modulo.objects.filter(url=url)
        if self.instance and self.instance.pk:
            existentes = existentes.exclude(pk=self.instance.pk)
        if existentes.exists():
            raise forms.ValidationError('Ya existe un módulo con esa URL.')
        return url


class SeccionMenuForm(FormularioBase):
    class Meta:
        model = ModuloGrupo
        fields = ('nombre', 'icono', 'prioridad', 'modulos')
        labels = {'nombre': 'Nombre', 'icono': 'Icono', 'prioridad': 'Prioridad',
                  'modulos': 'Módulos que incluye'}
        widgets = {'modulos': forms.SelectMultiple(attrs={'size': 12})}


class PermisosRolForm(forms.ModelForm):
    class Meta:
        model = GroupModulo
        fields = ('modulos',)
        labels = {'modulos': 'Módulos permitidos'}
        widgets = {'modulos': forms.CheckboxSelectMultiple()}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['modulos'].queryset = Modulo.objects.filter(status=True).order_by('orden', 'nombre')
