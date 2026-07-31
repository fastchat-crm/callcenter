"""Validadores reutilizables para archivos y datos ecuatorianos/internacionales."""
import re

from django.core.exceptions import ValidationError

MB = 1024 * 1024


def _validar_tamano(archivo, limite_mb):
    if archivo and archivo.size > limite_mb * MB:
        raise ValidationError(f'El archivo supera el máximo permitido de {limite_mb} MB.')


def validate_file_size_2mb(archivo):
    _validar_tamano(archivo, 2)


def validate_file_size_5mb(archivo):
    _validar_tamano(archivo, 5)


def validate_file_size_20mb(archivo):
    _validar_tamano(archivo, 20)


def validate_file_size_50mb(archivo):
    _validar_tamano(archivo, 50)


def validar_cedula_ecuatoriana(cedula):
    """Valida el digito verificador de una cedula de Ecuador."""
    cedula = (cedula or '').strip()
    if not cedula.isdigit() or len(cedula) != 10:
        raise ValidationError('La cédula debe tener 10 dígitos numéricos.')
    provincia = int(cedula[:2])
    if provincia < 1 or provincia > 24:
        raise ValidationError('El código de provincia de la cédula no es válido.')
    coeficientes = [2, 1, 2, 1, 2, 1, 2, 1, 2]
    total = 0
    for indice, coeficiente in enumerate(coeficientes):
        producto = int(cedula[indice]) * coeficiente
        total += producto - 9 if producto > 9 else producto
    verificador = (10 - total % 10) % 10
    if verificador != int(cedula[9]):
        raise ValidationError('La cédula ingresada no es válida.')
    return cedula


PATRON_E164 = re.compile(r'^\+[1-9]\d{7,14}$')


def validar_e164(numero):
    """Valida numeros internacionales en formato E.164 (+59399..., +1415..., +34600...)."""
    if not PATRON_E164.match((numero or '').strip()):
        raise ValidationError('El número debe estar en formato internacional E.164, ejemplo +593987654321.')
    return numero
