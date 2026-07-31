(function () {
    'use strict';

    const App = {
        modal: null,
        modalCuerpo: null,
        modalTitulo: null,

        iniciar() {
            this.modal = document.getElementById('modal-fondo');
            this.modalCuerpo = document.getElementById('modal-cuerpo');
            this.modalTitulo = document.getElementById('modal-titulo');
            document.addEventListener('click', (evento) => this.enClick(evento));
            document.addEventListener('submit', (evento) => this.enSubmit(evento));
            document.addEventListener('keydown', (evento) => {
                if (evento.key === 'Escape') this.cerrarModal();
            });
            this.marcarMenuActivo();
            this.restaurarMenu();
            this.restaurarGuia();
        },

        esPantallaAngosta() {
            return window.matchMedia('(max-width: 980px)').matches;
        },

        restaurarMenu() {
            if (!this.esPantallaAngosta() && localStorage.getItem('menu') === 'colapsado') {
                document.querySelector('.aplicacion').classList.add('menu-colapsado');
            }
        },

        alternarMenu() {
            if (this.esPantallaAngosta()) {
                document.querySelector('.menu-lateral').classList.toggle('abierto');
                return;
            }
            const aplicacion = document.querySelector('.aplicacion');
            const colapsado = aplicacion.classList.toggle('menu-colapsado');
            localStorage.setItem('menu', colapsado ? 'colapsado' : 'abierto');
        },

        restaurarGuia() {
            const guia = document.querySelector('.guia');
            if (guia && localStorage.getItem(`guia:${guia.dataset.guia}`) === 'plegada') {
                guia.classList.add('plegada');
            }
        },

        alternarGuia(guia) {
            const plegada = guia.classList.toggle('plegada');
            localStorage.setItem(`guia:${guia.dataset.guia}`, plegada ? 'plegada' : 'abierta');
        },

        marcarMenuActivo() {
            const ruta = window.location.pathname;
            document.querySelectorAll('.menu-item').forEach((enlace) => {
                const destino = enlace.getAttribute('href');
                if (destino && destino !== '/' && ruta.startsWith(destino)) {
                    enlace.classList.add('activo');
                }
            });
        },

        enClick(evento) {
            const abridor = evento.target.closest('[data-accion]');
            if (abridor) {
                evento.preventDefault();
                this.ejecutarAccion(abridor);
                return;
            }
            if (evento.target.matches('[data-cerrar-modal]') || evento.target === this.modal) {
                this.cerrarModal();
            }
            if (evento.target.closest('#alternar-menu')) {
                this.alternarMenu();
            }
            const alternador = evento.target.closest('[data-guia-alternar]');
            if (alternador) {
                this.alternarGuia(alternador.closest('.guia'));
            }
        },

        ejecutarAccion(elemento) {
            const accion = elemento.dataset.accion;
            const url = elemento.dataset.url || window.location.pathname;
            const id = elemento.dataset.id || '';
            const titulo = elemento.dataset.titulo || 'Formulario';

            if (accion === 'add' || accion === 'change' || accion === 'add_opcion' || accion === 'add_documento') {
                this.abrirFormulario(url, accion, id, titulo);
            } else if (accion === 'delete' || accion === 'delete_opcion' || accion === 'delete_documento') {
                this.confirmarEliminar(url, accion, id, elemento.dataset.mensaje);
            } else if (accion === 'post') {
                this.enviarAccion(url, elemento.dataset.payload ? JSON.parse(elemento.dataset.payload) : {},
                    elemento.dataset.recargar !== 'no');
            }
        },

        abrirFormulario(url, accion, id, titulo) {
            const separador = url.includes('?') ? '&' : '?';
            const destino = `${url}${separador}action=${accion}${id ? '&id=' + id : ''}`;
            this.modalTitulo.textContent = titulo;
            this.modalCuerpo.innerHTML = '<p class="texto-tenue">Cargando…</p>';
            this.modal.classList.add('visible');
            fetch(destino, { headers: { 'X-Requested-With': 'XMLHttpRequest' } })
                .then((respuesta) => respuesta.json())
                .then((datos) => {
                    if (datos.result) {
                        this.modalCuerpo.innerHTML = datos.data;
                    } else {
                        this.modalCuerpo.innerHTML = `<p class="error">${datos.message || 'No se pudo cargar.'}</p>`;
                    }
                })
                .catch((error) => {
                    this.modalCuerpo.innerHTML = `<p class="error">${error}</p>`;
                });
        },

        confirmarEliminar(url, accion, id, mensaje) {
            if (!window.confirm(mensaje || '¿Confirmas eliminar este registro?')) return;
            this.enviarAccion(url, { action: accion, id: id }, true);
        },

        enviarAccion(url, datos, recargar) {
            const cuerpo = new FormData();
            Object.entries(datos).forEach(([clave, valor]) => cuerpo.append(clave, valor));
            cuerpo.append('csrfmiddlewaretoken', this.token());
            fetch(url, { method: 'POST', body: cuerpo, headers: { 'X-Requested-With': 'XMLHttpRequest' } })
                .then((respuesta) => respuesta.json())
                .then((datos) => this.procesarRespuesta(datos, recargar))
                .catch((error) => this.aviso(String(error), 'error'));
        },

        enSubmit(evento) {
            const formulario = evento.target.closest('form[data-ajax]');
            if (!formulario) return;
            evento.preventDefault();
            const boton = formulario.querySelector('[type=submit]');
            if (boton) boton.disabled = true;
            fetch(formulario.action || window.location.pathname, {
                method: 'POST',
                body: new FormData(formulario),
                headers: { 'X-Requested-With': 'XMLHttpRequest' },
            })
                .then((respuesta) => respuesta.json())
                .then((datos) => this.procesarRespuesta(datos, true))
                .catch((error) => this.aviso(String(error), 'error'))
                .finally(() => { if (boton) boton.disabled = false; });
        },

        procesarRespuesta(datos, recargar) {
            const item = Array.isArray(datos) ? datos[0] : datos;
            if (!item) return;
            if (item.error) {
                this.aviso(item.message || 'Revisa los datos del formulario.', 'error');
                if (item.errores) this.pintarErrores(item.errores);
                return;
            }
            this.aviso(item.message || 'Operación realizada.', 'exito');
            this.cerrarModal();
            if (recargar && item.reload !== false) {
                window.setTimeout(() => window.location.reload(), 450);
            }
        },

        pintarErrores(errores) {
            this.modalCuerpo.querySelectorAll('.error').forEach((nodo) => nodo.remove());
            errores.forEach((error) => {
                const campo = this.modalCuerpo.querySelector(`[name="${error.campo}"]`);
                if (!campo) return;
                const nodo = document.createElement('div');
                nodo.className = 'error';
                nodo.textContent = error.mensajes.join(' ');
                campo.parentNode.appendChild(nodo);
            });
        },

        cerrarModal() {
            if (this.modal) this.modal.classList.remove('visible');
        },

        token() {
            const campo = document.querySelector('[name=csrfmiddlewaretoken]');
            return campo ? campo.value : '';
        },

        aviso(texto, tipo) {
            const contenedor = document.getElementById('avisos');
            if (!contenedor) return;
            const nodo = document.createElement('div');
            nodo.className = `aviso aviso-${tipo || 'exito'}`;
            nodo.textContent = texto;
            contenedor.appendChild(nodo);
            window.setTimeout(() => nodo.remove(), 4200);
        },
    };

    window.App = App;
    document.addEventListener('DOMContentLoaded', () => App.iniciar());
})();
