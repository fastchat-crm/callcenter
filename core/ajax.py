"""Despachador AJAX central.

Convencion heredada de fastchatdj: toda consulta ligera del frontend entra por
`/ajaxrequest/<accion>` en vez de crear endpoints sueltos.
"""
import json

from django.http import JsonResponse
from django.views.generic import View


class ConsultasAjax(View):
    def get(self, request, accion=None, pk=None, *args, **kwargs):
        accion = accion or request.GET.get('accion', '')
        if not request.user.is_authenticated:
            return JsonResponse({'error': True, 'message': 'Sesión no válida.'}, status=401)

        if accion == 'buscar_agentes':
            return self._buscar_agentes(request)
        if accion == 'buscar_flujos':
            return self._buscar_flujos(request)
        if accion == 'buscar_asesores':
            return self._buscar_asesores(request)
        if accion == 'resumen_llamada':
            return self._resumen_llamada(request, pk)
        if accion == 'metricas_panel':
            return self._metricas_panel(request)
        return JsonResponse({'error': True, 'message': f'Acción no soportada: {accion}'}, status=400)

    def post(self, request, accion=None, pk=None, *args, **kwargs):
        accion = accion or request.POST.get('accion', '')
        if not request.user.is_authenticated:
            return JsonResponse({'error': True, 'message': 'Sesión no válida.'}, status=401)

        if accion == 'cambiar_estado_agente':
            return self._cambiar_estado_agente(request)
        return JsonResponse({'error': True, 'message': f'Acción no soportada: {accion}'}, status=400)

    # --- Acciones ---
    def _buscar_agentes(self, request):
        from agentes_ia.models import AgenteIA

        criterio = (request.GET.get('q') or '').strip()
        consulta = AgenteIA.objects.filter(status=True)
        if criterio:
            consulta = consulta.filter(nombre__icontains=criterio)
        datos = list(consulta.values('id', 'nombre')[:30])
        return JsonResponse({'error': False, 'resultados': datos})

    def _buscar_flujos(self, request):
        from ivr.models import FlujoVoz

        criterio = (request.GET.get('q') or '').strip()
        consulta = FlujoVoz.objects.filter(status=True)
        if criterio:
            consulta = consulta.filter(nombre__icontains=criterio)
        datos = list(consulta.values('id', 'nombre')[:30])
        return JsonResponse({'error': False, 'resultados': datos})

    def _buscar_asesores(self, request):
        from telefonia.models import AsesorHumano

        criterio = (request.GET.get('q') or '').strip()
        consulta = AsesorHumano.objects.filter(status=True, disponible=True)
        if criterio:
            consulta = consulta.filter(nombre__icontains=criterio)
        datos = list(consulta.values('id', 'nombre', 'numero_destino')[:30])
        return JsonResponse({'error': False, 'resultados': datos})

    def _resumen_llamada(self, request, pk):
        from llamadas.models import Llamada

        llamada = Llamada.objects.filter(pk=pk).first()
        if llamada is None:
            return JsonResponse({'error': True, 'message': 'Llamada no encontrada.'}, status=404)
        turnos = list(llamada.turnos.values('rol', 'texto', 'latencia_ms', 'fecha'))
        return JsonResponse({
            'error': False,
            'llamada': {
                'id': llamada.id,
                'numero_origen': llamada.numero_origen,
                'estado': llamada.estado,
                'duracion_segundos': llamada.duracion_segundos,
                'datos_capturados': llamada.datos_capturados or {},
            },
            'turnos': turnos,
        }, json_dumps_params={'default': str})

    def _metricas_panel(self, request):
        from llamadas.consultas import metricas_generales

        return JsonResponse({'error': False, 'metricas': metricas_generales()},
                            json_dumps_params={'default': str})

    def _cambiar_estado_agente(self, request):
        from agentes_ia.models import AgenteIA

        try:
            cuerpo = json.loads(request.body or '{}') if request.content_type == 'application/json' else request.POST
            agente = AgenteIA.objects.get(pk=int(cuerpo['id']))
            agente.activo = not agente.activo
            agente.save(request)
            return JsonResponse({'error': False, 'activo': agente.activo})
        except Exception as ex:
            return JsonResponse({'error': True, 'message': str(ex)}, status=400)
