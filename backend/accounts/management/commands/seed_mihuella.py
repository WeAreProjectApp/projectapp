"""
Seed Mi Huella demo project with realistic guías de validación data.

Creates:
  - 1 client: Laura Blanco (laura@entre-especies.com; optional SEED_MIHUELLA_PASSWORD)
  - 1 business proposal: Mi Huella — status accepted, all 15 sections with platform content
  - 1 project: Mi Huella — Plataforma de Adopción Animal
  - Client-readable validation guides with published partial reviews and private drafts
  - 9 bug reports (fictional but coherent with the platform)
  - 6 change requests
  - 8 deliverables with epic assignments
  - 1 hosting subscription + 2 payments

Usage:
  python manage.py seed_mihuella
  python manage.py seed_mihuella --flush
"""

import os
from copy import deepcopy
from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.utils import timezone

from accounts.management.commands._seed_helpers import seed_validation_guides, clear_fake_delivery
from accounts.models import (
    BugComment, BugReport, ChangeRequest, ChangeRequestComment,
    Deliverable, DeliverableVersion, HostingSubscription, Payment,
    Project, ProjectPhase, Requirement, UserProfile,
)
from content.fake_data import add_seed_arguments, ensure_fake_data_allowed, seed_context
from content.models import BusinessProposal, ProposalSection
from content.services.proposal_service import ProposalService

User = get_user_model()

CLIENT_EMAIL = 'laura@entre-especies.com'
CLIENT_PASSWORD = os.environ.get('SEED_MIHUELLA_PASSWORD')
PROJECT_NAME = 'Mi Huella — Plataforma de Adopción Animal'
PROPOSAL_SLUG = 'mi-huella-plataforma-adopcion'
PROPOSAL_INVESTMENT = Decimal('38000000')

# ---------------------------------------------------------------------------
# Epic definitions
# ---------------------------------------------------------------------------

EPICS = {
    'AUTH':          'Autenticación y Acceso',
    'LANDING':       'Plataforma Pública',
    'ADOPTION':      'Proceso de Adopción',
    'CAMPAIGNS':     'Campañas y Donaciones Wompi',
    'SHELTER_PANEL': 'Panel de Refugio',
    'ADMIN':         'Administración de Plataforma',
    'BLOG':          'Blog y Contenido',
    'PROFILE':       'Perfil y Notificaciones',
    'ADOPTER':       'Busco Adoptar',
}

# fmt: off
VALIDATION_GUIDES = [
    {'title': 'Registro de usuario con email y contraseña', 'description': "Pantalla de registro donde nuevos usuarios crean una cuenta proporcionando nombre, email y contraseña. Al registrarse, se asigna automáticamente el rol 'adopter'.", 'role': 'Todos los usuarios no autenticados (guests).', 'steps': ['Usuario abre /sign-up', 'completa nombre, email y contraseña', 'el sistema valida campos', 'crea cuenta con rol adopter', 'emite tokens JWT', 'redirige al home'], 'review_status': 'approved', 'draft': False},
    {'title': 'Inicio de sesión con email y contraseña', 'description': 'Pantalla de autenticación donde usuarios existentes inician sesión con sus credenciales de email y contraseña.', 'role': 'Todos los usuarios no autenticados.', 'steps': ['Usuario abre /sign-in', 'ingresa email y contraseña', 'click en Iniciar sesión', 'el sistema valida credenciales', 'emite tokens JWT', 'redirige al home'], 'review_status': 'objected', 'draft': False},
    {'title': 'Inicio de sesión con Google OAuth', 'description': 'Autenticación alternativa mediante cuenta de Google. Si el usuario no existe, se crea automáticamente con rol adopter.', 'role': 'Todos los usuarios no autenticados.', 'steps': ['Usuario abre /sign-in', "click en 'Iniciar con Google'", 'flujo OAuth de Google', 'el sistema crea o vincula usuario', 'emite tokens JWT', 'redirige al home'], 'review_status': 'rejected', 'draft': False},
    {'title': 'Recuperación de contraseña por email', 'description': 'Flujo de restablecimiento de contraseña mediante envío de código de verificación al email registrado del usuario.', 'role': 'Todos los usuarios registrados.', 'steps': ['Usuario abre /forgot-password', 'ingresa email', 'el sistema genera PasswordCode y envía email', 'usuario ingresa código', 'establece nueva contraseña', 'redirige a /sign-in'], 'review_status': 'in_review', 'draft': False},
    {'title': 'Cierre de sesión', 'description': 'Permite al usuario cerrar su sesión activa, eliminando tokens de autenticación del navegador.', 'role': 'Todos los usuarios autenticados.', 'steps': ["Usuario click en 'Cerrar sesión' en menú de usuario", 'tokens eliminados de localStorage', 'redirige a /sign-in'], 'review_status': 'in_review', 'draft': False},
    {'title': 'Persistencia de sesión con refresh de tokens', 'description': 'Renovación automática del token de acceso JWT cuando expira, permitiendo sesiones continuas sin re-autenticación.', 'role': 'Todos los usuarios autenticados.', 'steps': ['Token de acceso expira', 'interceptor Axios detecta 401', 'envía refresh token', 'el sistema emite nuevos tokens', 'la solicitud original se reintenta automáticamente'], 'review_status': 'in_review', 'draft': False},
    {'title': 'Redirección de rutas protegidas', 'description': 'Los usuarios no autenticados que intentan acceder a rutas protegidas son redirigidos automáticamente a la pantalla de inicio de sesión.', 'role': 'Usuarios no autenticados intentando acceder a rutas que requieren autenticación.', 'steps': ['Usuario no autenticado navega a ruta protegida', 'middleware detecta ausencia de token', 'redirige a /sign-in', 'tras login, redirige a la ruta original'], 'review_status': 'in_review', 'draft': False},
    {'title': 'Página de inicio (landing)', 'description': 'Página principal de la plataforma con sección hero, carrusel de animales destacados, carrusel de campañas activas y spotlight de refugios.', 'role': 'Visible para todos los usuarios.', 'steps': ['Usuario abre /', 've sección hero con CTA principal', 'navega carrusel de animales destacados', 've carrusel de campañas activas', 've spotlight de refugio', 'puede navegar a cualquier sección desde los CTAs'], 'review_status': 'in_review', 'draft': False},
    {'title': 'Navegación principal (header)', 'description': 'Barra de navegación con enlaces a secciones principales, selector de idioma, campana de notificaciones, toggle de tema y menú de usuario.', 'role': 'Visible para todos los usuarios. Menú de usuario y notificaciones solo para autenticados.', 'steps': ['Usuario ve header', 'links visibles: Animales, Refugios, Campañas, Busco Adoptar, Blog', 'click para navegar', 'si autenticado: ve campana de notificaciones y menú de usuario'], 'review_status': 'in_review', 'draft': False},
    {'title': 'Menú móvil responsive', 'description': 'Navegación adaptada para dispositivos móviles con menú hamburguesa que despliega sidebar con todos los enlaces.', 'role': 'Todos los usuarios en dispositivos móviles.', 'steps': ['Usuario en móvil', 'click en ícono hamburguesa', 'sidebar se despliega con todos los enlaces de navegación', 'click en enlace', 'navega y sidebar se cierra'], 'review_status': 'in_review', 'draft': False},
    {'title': 'Catálogo de animales con filtros', 'description': 'Listado paginado de todos los animales disponibles para adopción, con filtros por especie, tamaño, edad y género.', 'role': 'Visible para todos los usuarios (autenticados y guests).', 'steps': ['Usuario navega a /animales', 've grid de tarjetas de animales', 'aplica filtros (perro/gato, pequeño/mediano/grande, cachorro/joven/adulto, macho/hembra)', 'resultados se actualizan en tiempo real'], 'review_status': 'in_review', 'draft': False},
    {'title': 'Detalle de animal con galería', 'description': 'Página de perfil completo del animal mostrando nombre, descripción, historial médico, necesidades especiales, galería de imágenes y CTAs de adopción/apadrinamiento.', 'role': 'Visible para todos los usuarios.', 'steps': ['Usuario click en tarjeta de animal', 'navega a /animales/{id}', 've información completa', 'puede recorrer galería (Swiper)', 've botones de Adoptar, Apadrinar y Donar'], 'review_status': 'in_review', 'draft': False},
    {'title': 'Directorio de refugios', 'description': 'Listado público de todos los refugios verificados en la plataforma con tarjetas informativas.', 'role': 'Visible para todos los usuarios.', 'steps': ['Usuario navega a /refugios', 've grid de tarjetas de refugios (nombre, logo, ubicación)', 'click en refugio', 'navega a perfil del refugio'], 'review_status': 'in_review', 'draft': False},
    {'title': 'Perfil público del refugio', 'description': 'Página de detalle del refugio mostrando información completa, galería, animales disponibles y campañas activas.', 'role': 'Visible para todos los usuarios.', 'steps': ['Usuario click en refugio', 've /refugios/{id}', 've descripción, galería, contacto', 'sección de animales del refugio', 'sección de campañas activas'], 'review_status': 'in_review', 'draft': False},
    {'title': 'Modo oscuro/claro', 'description': 'Toggle de tema visual que permite alternar entre modo oscuro y modo claro en toda la aplicación.', 'role': 'Todos los usuarios.', 'steps': ['Usuario click en toggle de tema en header', 'toda la aplicación cambia a modo oscuro/claro', 'preferencia persistida'], 'review_status': 'in_review', 'draft': False},
    {'title': 'Formulario de solicitud de adopción (wizard)', 'description': 'Formulario de adopción en 3 pasos con 6 preguntas por sección, cubriendo información personal, hogar/estilo de vida, y revisión final antes de enviar.', 'role': 'Solo usuarios autenticados con rol adopter. Requiere seleccionar un animal específico.', 'steps': ['Usuario en detalle de animal', "click 'Adoptar'", 'Paso 1: info personal (6 preguntas)', 'Paso 2: hogar y estilo de vida (6 preguntas)', 'Paso 3: revisión y confirmación', 'envía', "solicitud creada con status 'submitted'"], 'review_status': 'in_review', 'draft': False},
    {'title': 'Seguimiento de solicitudes de adopción', 'description': 'Pantalla donde el adoptante ve todas sus solicitudes de adopción con su estado actual (enviada, en revisión, entrevista, aprobada, rechazada).', 'role': 'Solo usuarios autenticados con rol adopter.', 'steps': ['Usuario navega a /mis-solicitudes', 've lista de solicitudes con nombre del animal, fecha y badge de estado', 'puede click en cada una para ver detalles'], 'review_status': 'in_review', 'draft': False},
    {'title': 'Listado de campañas de donación', 'description': 'Página con todas las campañas de recaudación activas y completadas, mostrando progreso de cada una.', 'role': 'Visible para todos los usuarios.', 'steps': ['Usuario navega a /campanas', 've tarjetas con título, barra de progreso, meta y monto recaudado', 'puede alternar entre pestañas Activas/Completadas'], 'review_status': 'in_review', 'draft': False},
    {'title': 'Detalle de campaña con progreso', 'description': 'Página completa de una campaña mostrando descripción, meta, monto recaudado, porcentaje de progreso y CTA para donar.', 'role': 'Visible para todos los usuarios.', 'steps': ['Usuario click en campaña', 've /campanas/{id}', 've descripción completa, barra de progreso, porcentaje, galería de evidencia', "click en 'Donar'"], 'review_status': 'in_review', 'draft': False},
    {'title': 'Checkout de donación', 'description': 'Flujo de pago para realizar una donación a un refugio o campaña específica, con montos preestablecidos y método de pago.', 'role': 'Solo usuarios autenticados con rol adopter.', 'steps': ['Usuario navega a /checkout/donacion', 'selecciona monto', 'elige método de pago (tarjeta/PSE/Nequi)', 'agrega mensaje opcional', 'confirma', 'pago procesado vía Wompi', 'redirige a confirmación'], 'review_status': 'in_review', 'draft': False},
    {'title': 'Integración de pagos con Wompi', 'description': 'Procesamiento de pagos mediante la pasarela colombiana Wompi, soportando tarjeta de crédito, PSE y Nequi como métodos de pago.', 'role': 'Usuarios autenticados que realizan donaciones o apadrinamientos. Requiere configuración de API keys de Wompi.', 'steps': ['Usuario en checkout', 'selecciona método de pago', 'sistema crea payment intent vía Wompi API', 'usuario completa pago en widget', 'webhook de Wompi confirma transacción'], 'review_status': 'in_review', 'draft': False},
    {'title': 'Registro de refugio (onboarding)', 'description': 'Formulario de registro para organizaciones de refugio que desean publicar animales en la plataforma. El refugio queda en estado pendiente de verificación.', 'role': 'Usuarios autenticados con rol shelter_admin.', 'steps': ['Shelter admin navega a /refugio/onboarding', 'completa formulario (nombre, logo, cover, ubicación, descripción, contacto)', 'envía', 'Shelter creado con verification_status=pending'], 'review_status': 'in_review', 'draft': False},
    {'title': 'Gestión de animales del refugio (CRUD)', 'description': 'Panel completo para crear, ver, editar y archivar animales del refugio, incluyendo carga de galería de imágenes.', 'role': 'Solo usuarios con rol shelter_admin del refugio correspondiente.', 'steps': ['Shelter admin navega a /refugio/animales', 've lista paginada con filtros', "click 'Crear'", 'completa formulario con galería drag-drop', 'guarda', 'animal publicado'], 'review_status': 'in_review', 'draft': False},
    {'title': 'Marcar animal como favorito', 'description': 'Permite a usuarios autenticados guardar animales en su lista de favoritos mediante un ícono de corazón.', 'role': 'Solo usuarios autenticados con rol adopter.', 'steps': ['Usuario autenticado', 'click en ícono de corazón en tarjeta o detalle de animal', 'favorito creado en BD', 'ícono cambia a lleno', 'animal aparece en /favoritos'], 'review_status': 'in_review', 'draft': False},
    {'title': 'Lista de animales favoritos', 'description': 'Página dedicada donde el usuario ve todos los animales que ha marcado como favoritos.', 'role': 'Solo usuarios autenticados con rol adopter.', 'steps': ['Usuario navega a /favoritos', 've grid con todos los animales favoritos', 'puede click en cualquiera para ver detalle', 'puede quitar favorito'], 'review_status': 'in_review', 'draft': False},
    {'title': 'Revisión de solicitudes por refugio', 'description': 'Panel donde el administrador del refugio revisa las solicitudes de adopción recibidas y puede cambiar su estado.', 'role': 'Solo usuarios con rol shelter_admin, limitado a solicitudes de animales de su refugio.', 'steps': ['Shelter admin navega a /refugio/solicitudes', 've lista de solicitudes', 'click en una', 've info del solicitante y respuestas', 'selecciona nuevo estado', 'guarda'], 'review_status': 'in_review', 'draft': False},
    {'title': 'Confirmación de pago', 'description': 'Página de confirmación mostrada después de un pago exitoso, con resumen del recibo.', 'role': 'Solo usuarios autenticados que acaban de completar un pago.', 'steps': ['Usuario completa checkout', 'sistema procesa pago', 'redirige a /checkout/confirmation', 've mensaje de agradecimiento con detalles (monto, destinatario, fecha, referencia)'], 'review_status': 'in_review', 'draft': False},
    {'title': 'Checkout de apadrinamiento', 'description': 'Flujo de pago para apadrinar un animal con opción de frecuencia mensual o única, selección de monto y método de pago.', 'role': 'Solo usuarios autenticados con rol adopter.', 'steps': ['Usuario navega a /checkout/apadrinamiento', 'selecciona animal', 'elige frecuencia', 'selecciona monto', 'elige método de pago', 'confirma', 'Sponsorship y Payment creados'], 'review_status': 'in_review', 'draft': False},
    {'title': 'Dashboard del panel de refugio', 'description': 'Panel de navegación central para administradores de refugio con accesos directos a todas las secciones de gestión.', 'role': 'Solo usuarios con rol shelter_admin.', 'steps': ['Shelter admin navega a /refugio', 've dashboard con enlaces a: animales, solicitudes, campañas, donaciones, updates, configuración'], 'review_status': 'in_review', 'draft': False},
    {'title': 'Gestión de campañas del refugio', 'description': 'Panel para crear y administrar campañas de recaudación de fondos del refugio, con seguimiento de progreso.', 'role': 'Solo usuarios con rol shelter_admin del refugio correspondiente.', 'steps': ['Shelter admin navega a /refugio/campanas', 've campañas activas y completadas', "click 'Crear'", 'completa formulario', 'publica', 've progreso de recaudación'], 'review_status': 'in_review', 'draft': False},
    {'title': 'Dashboard de administración de plataforma', 'description': 'Panel principal del administrador con métricas resumidas: total de usuarios, refugios, animales, solicitudes, donaciones y apadrinamientos.', 'role': 'Solo usuarios con rol admin.', 'steps': ['Admin navega a /admin/dashboard', 've tarjetas resumen con KPIs de la plataforma'], 'review_status': 'in_review', 'draft': False},
    {'title': 'Aprobación y verificación de refugios', 'description': 'Cola de aprobación donde el administrador revisa y aprueba o rechaza refugios que se han registrado en la plataforma.', 'role': 'Solo usuarios con rol admin.', 'steps': ['Admin navega a /admin/refugios/aprobar', 've lista de refugios con status pending', 'click en refugio', 'revisa información', 'click Aprobar o Rechazar'], 'review_status': 'in_review', 'draft': False},
    {'title': 'Cambio de idioma (español/inglés)', 'description': 'Selector de idioma en el header que permite cambiar toda la interfaz entre español e inglés usando next-intl.', 'role': 'Todos los usuarios.', 'steps': ['Usuario click en toggle ES/EN en header', 'toda la página se re-renderiza en el idioma seleccionado', 'preferencia guardada'], 'review_status': 'in_review', 'draft': False},
    {'title': 'Campana de notificaciones con contador', 'description': 'Ícono de campana en el header que muestra la cantidad de notificaciones no leídas y un dropdown con las más recientes.', 'role': 'Todos los usuarios autenticados.', 'steps': ['Usuario ve ícono de campana con badge numérico', 'click', 'se despliega dropdown con 5 notificaciones recientes', 'puede marcar todas como leídas'], 'review_status': 'in_review', 'draft': False},
    {'title': 'Listado de posts del blog (público)', 'description': 'Página pública del blog con listado de artículos publicados, imagen destacada, título, extracto y fecha.', 'role': 'Visible para todos los usuarios.', 'steps': ['Usuario navega a /blog', 've lista de posts publicados con imagen, título, extracto, autor y fecha', 'puede filtrar por categoría', 'click en post para leer'], 'review_status': 'in_review', 'draft': False},
    {'title': 'Historial de donaciones del usuario', 'description': 'Página donde el usuario ve todas las donaciones que ha realizado, con monto, destinatario y fecha.', 'role': 'Solo usuarios autenticados con rol adopter.', 'steps': ['Usuario navega a /mis-donaciones', 've lista cronológica de donaciones (monto, refugio/campaña, fecha, estado)'], 'review_status': 'in_review', 'draft': False},
    {'title': 'Lista de apadrinamientos activos', 'description': 'Página donde el usuario ve todos sus apadrinamientos activos con animal, monto, frecuencia y estado de suscripción.', 'role': 'Solo usuarios autenticados con rol adopter.', 'steps': ['Usuario navega a /mis-apadrinamientos', 've lista de apadrinamientos (animal, monto, frecuencia, próximo cobro)'], 'review_status': 'in_review', 'draft': False},
    {'title': 'Gestión de suscripción de apadrinamiento', 'description': 'Permite pausar, reanudar o cancelar un apadrinamiento mensual activo.', 'role': 'Solo usuarios autenticados con rol adopter que tienen apadrinamientos mensuales activos.', 'steps': ['Usuario en /mis-apadrinamientos', 'click en apadrinamiento', 've opciones de gestión', 'click Pausar/Reanudar/Cancelar', 'confirma acción'], 'review_status': 'in_review', 'draft': False},
    {'title': 'Crear/actualizar intención de adopción', 'description': 'Perfil de preferencias de adopción donde el usuario publica qué tipo de animal busca, permitiendo que refugios lo descubran.', 'role': 'Solo usuarios autenticados con rol adopter.', 'steps': ['Usuario navega a /mi-intencion', 'selecciona preferencias (especie, tamaño, edad)', 'agrega descripción', 'elige visibilidad', 'guarda'], 'review_status': 'in_review', 'draft': False},
    {'title': 'Explorar intenciones de adopción públicas', 'description': 'Listado de adoptantes que han publicado sus preferencias de adopción, permitiendo a refugios descubrir posibles adoptantes.', 'role': 'Visible para todos los usuarios autenticados.', 'steps': ['Usuario navega a /busco-adoptar', 've tarjetas de adoptantes con sus preferencias', 'puede filtrar por tipo de animal'], 'review_status': 'in_review', 'draft': False},
    {'title': 'Enviar invitación a adoptante desde refugio', 'description': 'Permite al administrador de un refugio invitar a un adoptante interesado a conocer los animales del refugio.', 'role': 'Solo usuarios con rol shelter_admin.', 'steps': ['Shelter admin en /busco-adoptar', 've intención de adoptante', "click 'Enviar invitación'", 'ShelterInvite creado', 'notificación enviada'], 'review_status': 'in_review', 'draft': False},
    {'title': 'Gestión de perfil de usuario', 'description': 'Pantalla donde el usuario puede ver y editar su información personal (nombre, ciudad, avatar).', 'role': 'Todos los usuarios autenticados.', 'steps': ['Usuario navega a /mi-perfil', 've información actual', 'edita nombre, ciudad o avatar', 'click Guardar', 'datos actualizados'], 'review_status': 'in_review', 'draft': False},
    {'title': 'Preferencias de notificaciones', 'description': 'Pantalla donde el usuario configura qué notificaciones desea recibir por email y/o en la aplicación.', 'role': 'Todos los usuarios autenticados.', 'steps': ['Usuario navega a /my-profile/notifications', 've lista de eventos', 'activa/desactiva canal email e in-app por evento', 'guarda'], 'review_status': 'in_review', 'draft': False},
    {'title': 'Configuración del perfil del refugio', 'description': 'Pantalla de ajustes donde el administrador del refugio puede actualizar la información de su organización.', 'role': 'Solo usuarios con rol shelter_admin del refugio correspondiente.', 'steps': ['Shelter admin navega a /refugio/configuracion', 'edita nombre, descripción, logo, cover, contacto', 'guarda'], 'review_status': 'in_review', 'draft': False},
    {'title': 'Vista de donaciones recibidas por refugio', 'description': 'Listado de todas las donaciones recibidas por el refugio, con detalle de donante, monto y fecha.', 'role': 'Solo usuarios con rol shelter_admin del refugio correspondiente.', 'steps': ['Shelter admin navega a /refugio/donaciones', 've tabla de donaciones (monto, donante, fecha, campaña asociada)'], 'review_status': 'in_review', 'draft': False},
    {'title': 'Publicar post de actualización del refugio', 'description': 'Permite al refugio publicar actualizaciones sobre animales o campañas para mantener informados a donantes y adoptantes.', 'role': 'Solo usuarios con rol shelter_admin del refugio correspondiente.', 'steps': ['Shelter admin navega a /refugio/updates', "click 'Crear'", 'completa formulario', 'publica', 'post visible públicamente'], 'review_status': 'in_review', 'draft': False},
    {'title': 'Editar post de actualización del refugio', 'description': 'Permite modificar un post de actualización previamente publicado por el refugio.', 'role': 'Solo usuarios con rol shelter_admin del refugio correspondiente.', 'steps': ['Shelter admin navega a /refugio/updates', 'click en post existente', 'edita contenido', 'guarda'], 'review_status': 'in_review', 'draft': False},
    {'title': 'Lectura de artículo del blog', 'description': 'Página de detalle de un post del blog con contenido completo, barra de progreso de lectura, bio del autor y botones de compartir.', 'role': 'Visible para todos los usuarios.', 'steps': ['Usuario click en post', 've /blog/{slug}', 'lee contenido completo', 'barra de progreso indica avance', 've bio del autor', 'puede compartir'], 'review_status': 'in_review', 'draft': False},
    {'title': 'Administración de posts del blog (CRUD)', 'description': 'Panel de administración del blog para crear, editar, duplicar y gestionar artículos con contenido JSON, categorías, SEO y soporte bilingüe.', 'role': 'Solo usuarios con rol admin.', 'steps': ['Admin navega a /admin/blog', 've lista de posts', "click 'Crear'", 'completa formulario', 'publica o guarda como borrador'], 'review_status': 'in_review', 'draft': False},
    {'title': 'Calendario editorial del blog', 'description': 'Vista de calendario mensual que muestra la distribución de publicaciones del blog, con conteo por día y colores por estado.', 'role': 'Solo usuarios con rol admin.', 'steps': ['Admin navega a /admin/blog/calendario', 've calendario mensual', 'cada día muestra cantidad de posts', 'click en día para ver/crear'], 'review_status': 'in_review', 'draft': False},
    {'title': 'Métricas detalladas de la plataforma', 'description': 'Panel analítico con estadísticas financieras y de adopción: tasa de adopción, totales de donación, ingresos por mes/refugio.', 'role': 'Solo usuarios con rol admin.', 'steps': ['Admin navega a /admin/metricas', 've gráficos y tablas con: tasa de adopción, totales de donaciones, apadrinamientos recurrentes'], 'review_status': 'in_review', 'draft': False},
    {'title': 'Moderación de contenido publicado', 'description': 'Vista de moderación donde el administrador revisa animales, posts de actualización y posts de blog para detectar contenido inapropiado.', 'role': 'Solo usuarios con rol admin.', 'steps': ['Admin navega a /admin/moderacion', 've contenido publicado', 'items flaggeados resaltados', 'puede tomar acción'], 'review_status': 'in_review', 'draft': False},
    {'title': 'Auditoría de pagos', 'description': 'Tabla completa de todos los pagos procesados en la plataforma con fuente, estado y detalles de transacción.', 'role': 'Solo usuarios con rol admin.', 'steps': ['Admin navega a /admin/pagos', 've tabla con: ID de pago, monto, fuente, refugio, usuario, fecha, estado'], 'review_status': 'in_review', 'draft': True},
    {'title': 'Página de preguntas frecuentes (FAQ)', 'description': 'Página con preguntas frecuentes organizadas por temas en formato acordeón expandible.', 'role': 'Visible para todos los usuarios.', 'steps': ['Usuario navega a /faq', 've temas organizados', 'click en pregunta', 'respuesta se expande en acordeón'], 'review_status': 'in_review', 'draft': True},
    {'title': 'Páginas institucionales', 'description': 'Páginas estáticas de Acerca de nosotros, Términos y condiciones, Trabaja con nosotros y Aliados estratégicos.', 'role': 'Visible para todos los usuarios.', 'steps': ['Usuario navega a la página correspondiente desde el footer', 'lee contenido informativo'], 'review_status': 'in_review', 'draft': True},
]
# fmt: on


class Command(BaseCommand):
    help = 'Seed Mi Huella demo project with Laura Blanco as client.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--flush',
            action='store_true',
            help='Remove existing Laura Blanco seed data first.',
        )
        add_seed_arguments(parser)

    def handle(self, *args, **options):
        ensure_fake_data_allowed('seed_mihuella')
        self.seed_context = seed_context(options, 'mihuella')
        if options['flush']:
            self._flush()

        admin = self._get_admin()
        client = self._create_client()
        self._create_proposal(client)
        project = self._create_project(client)
        self._create_deliverables(project, admin)
        self._create_requirements(project)
        self._create_change_requests(project, client, admin)
        self._create_bug_reports(project, client, admin)
        self._create_subscription(project)

        req_qs = Requirement.objects.filter(stage__phase__scope__contract__project=project)

        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS('Mi Huella seed data created:'))
        self.stdout.write(f'  Client  → {CLIENT_EMAIL} / password supplied through environment or disabled')
        self.stdout.write(f'  Proposal → Mi Huella (accepted, all sections)')
        self.stdout.write(f'  Project → {PROJECT_NAME}')

        for status, label in Requirement.ReviewStatus.choices:
            count = req_qs.filter(review_status=status).count()
            self.stdout.write(f'    {label:<15} {count}')

        self.stdout.write(f'  Progress         → {project.progress}%')
        self.stdout.write(f'  Change requests  → {ChangeRequest.objects.filter(project=project).count()}')
        self.stdout.write(f'  Bug reports      → {BugReport.objects.filter(project=project).count()}')
        self.stdout.write(f'  Deliverables     → {Deliverable.objects.filter(project=project).count()}')
        self.stdout.write(f'  Subscription     → {HostingSubscription.objects.filter(project=project).count()}')
        self.stdout.write('')

    # ── Helpers ────────────────────────────────────────────────────────────

    def _get_admin(self):
        admin_profile = UserProfile.objects.filter(role=UserProfile.ROLE_ADMIN).first()
        return admin_profile.user if admin_profile else None

    def _flush(self):
        from content.models import Document

        user = User.objects.filter(email=CLIENT_EMAIL).first()
        if user:
            projects = Project.objects.filter(client=user, name=PROJECT_NAME)
            from accounts.management.commands._billing_seed_helpers import clear_fake_billing
            clear_fake_billing(projects)
            clear_fake_delivery(projects)
            Document.objects.filter(
                client_user=user, project__in=projects, title__startswith='[Seed]',
            ).delete()
            # Delete payments → subscriptions → projects (ProtectedFKs)
            for project in projects:
                for sub in HostingSubscription.objects.filter(project=project):
                    Payment.objects.filter(subscription=sub).delete()
                HostingSubscription.objects.filter(project=project).delete()
            projects.delete()
            BusinessProposal.objects.filter(
                client_email=CLIENT_EMAIL, slug=PROPOSAL_SLUG,
            ).delete()
            self.stdout.write(f'  Cleared Mi Huella seed project data for: {CLIENT_EMAIL}')

    def _create_client(self):
        if User.objects.filter(email=CLIENT_EMAIL).exists():
            self.stdout.write(f'  Client already exists: {CLIENT_EMAIL}')
            return User.objects.get(email=CLIENT_EMAIL)

        user = User.objects.create_user(
            username=CLIENT_EMAIL,
            email=CLIENT_EMAIL,
            password=CLIENT_PASSWORD,
            first_name='Laura',
            last_name='Blanco',
        )
        UserProfile.objects.update_or_create(
            user=user,
            defaults={
                'role': UserProfile.ROLE_CLIENT,
                'is_onboarded': True,
                'profile_completed': True,
                'company_name': 'Entre Especies',
                'phone': '+57 315 420 8899',
                'cedula': '1098765432',
                'date_of_birth': '1994-08-22',
                'gender': UserProfile.GENDER_FEMALE,
                'education_level': UserProfile.EDUCATION_UNIVERSITY,
            },
        )
        self.stdout.write(self.style.SUCCESS(f'  Created client: {CLIENT_EMAIL}'))
        return user

    def _create_proposal(self, client):
        if BusinessProposal.objects.filter(client_email=CLIENT_EMAIL, slug=PROPOSAL_SLUG).exists():
            self.stdout.write(f'  Proposal already exists for {CLIENT_EMAIL}')
            return

        now = self.seed_context.anchor_now

        proposal = BusinessProposal.objects.create(
            title='Propuesta Mi Huella — Plataforma de Adopción Animal',
            client=client.profile,
            client_name='Laura Blanco',
            client_email=CLIENT_EMAIL,
            client_phone='+57 315 420 8899',
            slug=PROPOSAL_SLUG,
            language='es',
            status=BusinessProposal.Status.ACCEPTED,
            total_investment=PROPOSAL_INVESTMENT,
            currency='COP',
            discount_percent=0,
            project_type='webapp',
            market_type='ngo',
            sent_at=now - timedelta(days=30),
            first_viewed_at=now - timedelta(days=28),
            view_count=7,
            responded_at=now - timedelta(days=22),
            last_activity_at=now - timedelta(days=22),
            expires_at=now + timedelta(days=180),
            automations_paused=True,
        )

        sections = ProposalService.get_default_sections(language='es')
        total_inv = float(PROPOSAL_INVESTMENT)
        fmt = lambda n: f'${n:,.0f}'  # noqa: E731

        for cfg in sections:
            st = cfg['section_type']

            if st == 'greeting':
                cfg['content_json']['proposalTitle'] = 'Mi Huella — Plataforma de Adopción y Apadrinamiento Animal'
                cfg['content_json']['clientName'] = 'Laura Blanco'
                cfg['content_json']['inspirationalQuote'] = (
                    'Hasta que no hayas amado a un animal, una parte de tu alma permanecerá despertando.'
                )

            elif st == 'executive_summary':
                cfg['content_json']['index'] = '1'
                cfg['content_json']['title'] = 'Resumen ejecutivo'
                cfg['content_json']['paragraphs'] = [
                    'Mi Huella es una plataforma web que conecta refugios de animales, adoptantes, padrinos '
                    'y donantes en un solo ecosistema digital confiable. El objetivo es hacer visibles a los '
                    'refugios pequeños, simplificar el proceso de adopción y canalizar donaciones de forma '
                    'transparente y trazable mediante la pasarela Wompi.',
                    'La plataforma contempla 50 vistas organizadas en módulos: exploración pública de animales '
                    'y refugios, flujo completo de adopción con formulario guiado, campañas de donación con '
                    'progreso en tiempo real, panel de gestión para shelter admins, área personal del adoptante '
                    'y panel de administración de la plataforma.',
                ]
                cfg['content_json']['highlightsTitle'] = 'Lo que incluye el proyecto'
                cfg['content_json']['highlights'] = [
                    '50 vistas en 10 módulos (público, adopción, campañas, blog, refugios, panel, perfil, admin)',
                    '27 modelos de datos: animales, solicitudes, campañas, donaciones, apadrinamientos y más',
                    'Integración con pasarela Wompi (tarjeta, PSE, Nequi) para donaciones y apadrinamientos',
                    'Panel de refugio con CRUD de animales, gestión de campañas y solicitudes de adopción',
                    'Sistema de notificaciones con 12 eventos transaccionales (email + in-app)',
                    'Blog con calendario editorial, panel admin y soporte bilingüe (es/en)',
                ]

            elif st == 'context_diagnostic':
                cfg['content_json']['index'] = '2'
                cfg['content_json']['title'] = 'Contexto y diagnóstico'
                cfg['content_json']['paragraphs'] = [
                    'En Colombia existen cientos de refugios de animales pequeños que operan sin presencia digital '
                    'profesional. Su única herramienta de comunicación son grupos de WhatsApp y publicaciones '
                    'esporádicas en redes sociales, lo que limita enormemente su alcance y credibilidad.',
                    'Las donaciones se gestionan de forma informal —transferencias sin recibo, sin trazabilidad y '
                    'sin visibilidad para el donante— generando desconfianza y reduciendo la recurrencia. '
                    'Tampoco existe un proceso estandarizado de adopción: cada refugio tiene su propio formulario '
                    '(o ninguno), lo que dificulta el seguimiento y aumenta las adopciones fallidas.',
                ]
                cfg['content_json']['issuesTitle'] = 'Problemas identificados'
                cfg['content_json']['issues'] = [
                    'Refugios sin visibilidad digital: operan por WhatsApp sin proceso estructurado',
                    'Información dispersa: no hay un punto central confiable para adoptantes y donantes',
                    'Donaciones informales: sin trazabilidad, recibos ni seguimiento posterior',
                    'Adopciones fallidas: sin formulario guiado ni seguimiento post-adopción',
                    'Desconfianza del donante: no sabe si su dinero llegó o qué impacto tuvo',
                ]
                cfg['content_json']['opportunityTitle'] = 'La oportunidad'
                cfg['content_json']['opportunity'] = (
                    'Crear el punto de encuentro digital del ecosistema de adopción animal en Colombia: '
                    'un espacio donde los refugios profesionalizan su presencia, los adoptantes encuentran '
                    'el animal ideal con un proceso claro, y los donantes confían porque ven el impacto '
                    'de cada peso aportado.'
                )

            elif st == 'conversion_strategy':
                cfg['content_json']['index'] = '3'
                cfg['content_json']['title'] = 'Estrategia de la plataforma'
                cfg['content_json']['intro'] = (
                    'Mi Huella se construye alrededor de tres pilares estratégicos: confianza, '
                    'simplicidad y transparencia. Cada módulo está diseñado para reducir la fricción '
                    'entre el refugio y quien quiere ayudar.'
                )
                cfg['content_json']['steps'] = [
                    {
                        'title': '🐾 Visibilidad para refugios verificados',
                        'bullets': [
                            'Sello de verificación visible en todos los listados y perfiles',
                            'Perfil completo con galería, descripción, historial de campañas y animales activos',
                            'Panel de administración simple para shelter admins sin conocimiento técnico',
                        ],
                    },
                    {
                        'title': '❤️ Proceso de adopción claro y guiado',
                        'bullets': [
                            'Formulario wizard de 3 pasos que cubre hogar, experiencia y compromiso',
                            'Seguimiento del estado en tiempo real desde /mis-solicitudes',
                            'Notificaciones automáticas en cada cambio de estado',
                        ],
                    },
                    {
                        'title': '💳 Donaciones con trazabilidad Wompi',
                        'bullets': [
                            'Checkout rápido con montos preestablecidos y método de pago a elección',
                            'Barra de progreso en campañas actualizada con cada donación',
                            'Historial completo en /mis-donaciones con recibo descargable',
                        ],
                    },
                    {
                        'title': '🔄 Apadrinamiento mensual recurrente',
                        'bullets': [
                            'Suscripción mensual vía tokenización Wompi, sin fricción para el padrino',
                            'Actualizaciones del animal apadrinado publicadas por el refugio',
                            'Panel de gestión: pausar, reanudar o cancelar desde /mis-apadrinamientos',
                        ],
                    },
                ]
                cfg['content_json']['resultTitle'] = '🎯 Resultado esperado'
                cfg['content_json']['result'] = (
                    'Una plataforma que convierte la intención de ayudar en una acción concreta y confiable: '
                    'adoptar un animal con un proceso profesional, donar sabiendo el impacto, '
                    'y apadrinar con seguimiento real del animal elegido.'
                )

            elif st == 'investment':
                cfg['content_json']['index'] = '4'
                cfg['content_json']['title'] = 'Inversión y Formas de Pago'
                cfg['content_json']['totalInvestment'] = fmt(total_inv)
                cfg['content_json']['currency'] = 'COP'
                cfg['content_json']['introText'] = (
                    'La inversión total para Mi Huella — plataforma completa de adopción y apadrinamiento — es:'
                )
                cfg['content_json']['whatsIncluded'] = [
                    {'icon': '🎨', 'title': 'Diseño UX/UI', 'description': 'Brandbook, wireframes y mockups finales para las 50 vistas'},
                    {'icon': '⚙️', 'title': 'Desarrollo full-stack', 'description': 'Django API + Next.js frontend con los 27 modelos y 9 módulos'},
                    {'icon': '💳', 'title': 'Integración Wompi', 'description': 'Pasarela de pagos colombiana: donaciones, apadrinamientos y webhooks'},
                    {'icon': '🚀', 'title': 'Despliegue y entrega', 'description': 'Producción, documentación técnica y capacitación al equipo'},
                ]
                cfg['content_json']['paymentOptions'] = [
                    {'label': '40% al firmar el contrato ✍️', 'description': f'{fmt(total_inv * 0.4)} COP'},
                    {'label': '30% al aprobar los diseños ✅', 'description': f'{fmt(total_inv * 0.3)} COP'},
                    {'label': '30% al lanzar en producción 🚀', 'description': f'{fmt(total_inv * 0.3)} COP'},
                ]
                cfg['content_json']['valueReasons'] = [
                    'Plataforma completa lista para producción, no un MVP limitado',
                    'Integración Wompi nativa para Colombia (PSE, tarjeta, Nequi)',
                    'Panel de refugio intuitivo sin conocimiento técnico requerido',
                    'Soporte y mantenimiento incluido en el plan de hosting',
                ]

            elif st == 'timeline':
                cfg['content_json']['index'] = '5'
                cfg['content_json']['title'] = 'Cronograma del Proyecto'
                cfg['content_json']['introText'] = (
                    'El proyecto se desarrollará en 5 fases durante aproximadamente 5 meses:'
                )
                cfg['content_json']['totalDuration'] = 'Aproximadamente 5 meses'
                cfg['content_json']['phases'] = [
                    {
                        'title': '🎨 Diseño y Marca',
                        'duration': '3 semanas',
                        'weeks': 'Semanas 1–3',
                        'circleColor': 'bg-purple-600',
                        'statusColor': 'bg-purple-100 text-purple-700',
                        'description': 'Brandbook de Mi Huella, wireframes de los 50 flujos y mockups finales en Figma.',
                        'tasks': ['Brandbook: logo, paleta, tipografías, tono', 'Wireframes de flujos principales', 'Mockups desktop + mobile (50 vistas)'],
                        'milestone': 'Diseños aprobados por Laura',
                    },
                    {
                        'title': '🔐 Autenticación y Estructura Base',
                        'duration': '2 semanas',
                        'weeks': 'Semanas 4–5',
                        'circleColor': 'bg-blue-600',
                        'statusColor': 'bg-blue-100 text-blue-700',
                        'description': 'Configuración del proyecto, modelos de datos, JWT auth y rutas protegidas.',
                        'tasks': ['Setup Django + Next.js + PostgreSQL', 'Modelos de datos (27 entidades)', 'Auth: registro, login, Google OAuth, JWT'],
                        'milestone': 'Auth funcional en staging',
                    },
                    {
                        'title': '🐾 Módulos Públicos y Refugios',
                        'duration': '5 semanas',
                        'weeks': 'Semanas 6–10',
                        'circleColor': 'bg-green-600',
                        'statusColor': 'bg-green-100 text-green-700',
                        'description': 'Catálogo de animales, perfiles de refugios, directorio y panel de gestión shelter admin.',
                        'tasks': ['Catálogo /animals con filtros', 'Directorio /shelters + perfil público', 'Panel refugio: CRUD animales, campañas, solicitudes'],
                        'milestone': 'Panel de refugio funcional',
                    },
                    {
                        'title': '💳 Pagos Wompi y Adopción',
                        'duration': '4 semanas',
                        'weeks': 'Semanas 11–14',
                        'circleColor': 'bg-orange-600',
                        'statusColor': 'bg-orange-100 text-orange-700',
                        'description': 'Integración Wompi para donaciones y apadrinamientos, wizard de adopción y notificaciones.',
                        'tasks': ['Integración Wompi (tarjeta, PSE, Nequi)', 'Checkout donación + apadrinamiento', 'Wizard adopción 3 pasos + notificaciones'],
                        'milestone': 'Pago real procesado en sandbox',
                    },
                    {
                        'title': '🚀 Admin, Blog y Lanzamiento',
                        'duration': '3 semanas',
                        'weeks': 'Semanas 15–17',
                        'circleColor': 'bg-pink-600',
                        'statusColor': 'bg-pink-100 text-pink-700',
                        'description': 'Panel admin con métricas, blog bilingüe, QA completo y despliegue a producción.',
                        'tasks': ['Panel admin + métricas + aprobación refugios', 'Blog con calendario editorial', 'QA, ajustes finales y lanzamiento'],
                        'milestone': 'Mi Huella en producción 🎉',
                    },
                ]

            elif st == 'functional_requirements':
                cfg['content_json']['index'] = '6'
                cfg['content_json']['title'] = 'Requerimientos Funcionales del Proyecto'
                cfg['content_json']['intro'] = (
                    'Mi Huella contempla 50 vistas organizadas en 10 módulos y los siguientes grupos funcionales:'
                )
                cfg['content_json']['groups'] = [
                    {
                        'id': 'public_views',
                        'icon': '🌐',
                        'title': 'Plataforma Pública (19 vistas)',
                        'is_visible': True,
                        'selected': True,
                        'is_always_included': True,
                        'description': 'Todas las vistas accesibles sin autenticación: landing, exploración de animales, refugios, campañas, blog y páginas institucionales.',
                        'items': [
                            {'icon': '🏠', 'name': 'Landing / Home', 'description': 'Hero, carrusel de animales destacados, carrusel de campañas activas y spotlight de refugios verificados.'},
                            {'icon': '🐾', 'name': 'Explorar animales (/animals)', 'description': 'Grid paginado con filtros por especie, tamaño, edad y género. Tarjetas con foto, nombre y estado.'},
                            {'icon': '🐶', 'name': 'Detalle de animal (/animals/[id])', 'description': 'Galería Swiper, descripción, historial médico, necesidades especiales. CTAs: Adoptar, Apadrinar, Donar.'},
                            {'icon': '🏘️', 'name': 'Directorio de refugios (/shelters)', 'description': 'Grid de refugios verificados con nombre, logo, ciudad y sello de verificación.'},
                            {'icon': '🏡', 'name': 'Perfil de refugio (/shelters/[id])', 'description': 'Info completa, galería, animales disponibles del refugio y campañas activas.'},
                            {'icon': '📢', 'name': 'Campañas (/campaigns)', 'description': 'Listado de campañas activas y completadas con barra de progreso y meta de recaudación.'},
                            {'icon': '📋', 'name': 'Detalle de campaña (/campaigns/[id])', 'description': 'Descripción, barra de progreso, galería de evidencia y botón Donar.'},
                            {'icon': '📖', 'name': 'Blog (/blog)', 'description': 'Listado de artículos con imagen, categoría, extracto y filtro.'},
                            {'icon': '📝', 'name': 'Artículo del blog (/blog/[slug])', 'description': 'Contenido completo, barra de progreso de lectura, bio del autor y botones de compartir.'},
                            {'icon': '🤝', 'name': 'Busco adoptar (/looking-to-adopt)', 'description': 'Listado de intenciones de adopción publicadas, filtrable por especie y características.'},
                            {'icon': '❓', 'name': 'FAQ (/faq)', 'description': 'Preguntas frecuentes organizadas por temas en acordeón expandible.'},
                            {'icon': 'ℹ️', 'name': 'Páginas institucionales', 'description': 'Acerca de, Términos, Aliados estratégicos, Contáctanos y Trabaja con nosotros.'},
                        ],
                    },
                    {
                        'id': 'adoption_module',
                        'icon': '❤️',
                        'title': 'Módulo de Adopción',
                        'is_visible': True,
                        'selected': True,
                        'is_always_included': True,
                        'description': 'Flujo completo de adopción: desde el formulario wizard hasta el seguimiento del estado por parte del adoptante y la gestión por el refugio.',
                        'items': [
                            {'icon': '📝', 'name': 'Formulario de adopción wizard (3 pasos)', 'description': 'Paso 1: datos personales. Paso 2: hogar y estilo de vida. Paso 3: revisión y confirmación. Incluye validación y guardado parcial.'},
                            {'icon': '📊', 'name': 'Mis solicitudes (/my-applications)', 'description': 'Seguimiento de todas las solicitudes con badge de estado: enviada, en revisión, entrevista, aprobada, rechazada.'},
                            {'icon': '📥', 'name': 'Bandeja del refugio (/shelter/applications)', 'description': 'Inbox de solicitudes recibidas, filtrable por estado. El shelter admin puede cambiar estados y agregar notas.'},
                        ],
                    },
                    {
                        'id': 'payments_module',
                        'icon': '💳',
                        'title': 'Pagos y Donaciones Wompi',
                        'is_visible': True,
                        'selected': True,
                        'is_always_included': True,
                        'description': 'Integración completa con la pasarela Wompi (Colombia) para donaciones únicas y apadrinamientos recurrentes.',
                        'items': [
                            {'icon': '💳', 'name': 'Integración Wompi', 'description': 'Tarjeta de crédito/débito, PSE y Nequi. Webhooks para confirmación asíncrona de pagos.'},
                            {'icon': '💝', 'name': 'Checkout de donación (/checkout/donation)', 'description': 'Montos preestablecidos + monto libre. Mensaje opcional. Destino: refugio o campaña específica.'},
                            {'icon': '🌟', 'name': 'Checkout de apadrinamiento (/checkout/sponsorship)', 'description': 'Selección de animal, frecuencia (mensual/único) y monto. Suscripción recurrente con tokenización Wompi.'},
                            {'icon': '✅', 'name': 'Confirmación de pago (/checkout/confirmation)', 'description': 'Página de éxito con detalles del recibo: monto, destinatario, fecha y referencia Wompi.'},
                            {'icon': '📜', 'name': 'Mis donaciones (/my-donations)', 'description': 'Historial cronológico de donaciones con estado, monto, destinatario y descarga de recibo.'},
                            {'icon': '🐾', 'name': 'Mis apadrinamientos (/my-sponsorships)', 'description': 'Apadrinamientos activos con animal, monto, frecuencia y opciones de pausar/cancelar.'},
                        ],
                    },
                    {
                        'id': 'shelter_panel',
                        'icon': '🏘️',
                        'title': 'Panel de Refugio (9 vistas)',
                        'is_visible': True,
                        'selected': True,
                        'is_always_included': True,
                        'description': 'Panel completo para administradores de refugio: gestión de animales, campañas, solicitudes, donaciones y actualizaciones.',
                        'items': [
                            {'icon': '📊', 'name': 'Dashboard del refugio (/shelter/dashboard)', 'description': 'KPIs: animales activos, solicitudes pendientes, donaciones del mes. Accesos directos a todas las secciones.'},
                            {'icon': '🐶', 'name': 'Gestión de animales (/shelter/animals)', 'description': 'CRUD completo con galería drag-drop, campos médicos y cambio de estado (draft → published → adopted).'},
                            {'icon': '📋', 'name': 'Gestión de campañas (/shelter/campaigns)', 'description': 'Crear y editar campañas de recaudación con meta, descripción y galería de evidencia. Seguimiento de progreso.'},
                            {'icon': '💰', 'name': 'Donaciones recibidas (/shelter/donations)', 'description': 'Tabla con todas las donaciones: monto, donante (anónimo si aplica), fecha, campaña asociada.'},
                            {'icon': '📣', 'name': 'Actualizaciones (/shelter/updates)', 'description': 'Publicar y editar posts de seguimiento para donantes y padrinos sobre animales o campañas.'},
                            {'icon': '⚙️', 'name': 'Configuración del refugio (/shelter/settings)', 'description': 'Editar nombre, descripción, logo, cover, ubicación y datos de contacto del refugio.'},
                        ],
                    },
                    {
                        'id': 'admin_panel',
                        'icon': '🛠️',
                        'title': 'Panel de Administración (9 vistas)',
                        'is_visible': True,
                        'selected': True,
                        'is_always_included': True,
                        'description': 'Panel para el equipo de Mi Huella: aprobación de refugios, moderación, métricas, auditoría de pagos y gestión del blog.',
                        'items': [
                            {'icon': '📊', 'name': 'Dashboard admin (/admin/dashboard)', 'description': 'KPIs globales: total usuarios, refugios activos, animales, solicitudes, donaciones del mes.'},
                            {'icon': '✅', 'name': 'Aprobación de refugios (/admin/shelters/approve)', 'description': 'Cola de refugios pending. Revisar info, aprobar o rechazar con mensaje.'},
                            {'icon': '🔍', 'name': 'Moderación (/admin/moderation)', 'description': 'Revisar animales, posts y blog flaggeados. Tomar acciones de remoción o advertencia.'},
                            {'icon': '📈', 'name': 'Métricas (/admin/metrics)', 'description': 'Tasa de adopción, totales de donación por mes/refugio, apadrinamientos recurrentes activos.'},
                            {'icon': '💳', 'name': 'Auditoría de pagos (/admin/payments)', 'description': 'Tabla completa de transacciones: monto, fuente, refugio, usuario, estado Wompi.'},
                            {'icon': '✍️', 'name': 'Blog admin (4 vistas)', 'description': 'Gestión de artículos, creación/edición con editor JSON bilingüe y calendario editorial mensual.'},
                        ],
                    },
                    {
                        'id': 'notifications_system',
                        'icon': '🔔',
                        'title': 'Sistema de Notificaciones',
                        'is_visible': True,
                        'selected': True,
                        'is_always_included': True,
                        'description': '12 eventos transaccionales enviados por email y/o in-app según preferencias del usuario.',
                        'items': [
                            {'icon': '📬', 'name': 'Notificaciones de adopción', 'description': 'Solicitud enviada, cambio de estado, entrevista agendada, información solicitada.'},
                            {'icon': '💳', 'name': 'Notificaciones de pagos', 'description': 'Donación confirmada, donación fallida, apadrinamiento confirmado, apadrinamiento fallido.'},
                            {'icon': '🏘️', 'name': 'Notificaciones de refugio', 'description': 'Invitación enviada, respuesta a invitación, meta de campaña alcanzada, nueva actualización publicada.'},
                            {'icon': '⚙️', 'name': 'Preferencias configurables', 'description': 'Cada usuario elige qué notificaciones recibir y por qué canal (email / in-app) desde su perfil.'},
                        ],
                    },
                ]
                cfg['content_json']['additionalModules'] = []

            elif st == 'design_ux':
                cfg['content_json']['index'] = '7'
                cfg['content_json']['title'] = 'Diseño Visual y Experiencia de Usuario'
                cfg['content_json']['paragraphs'] = [
                    'Mi Huella tendrá una identidad visual cálida y confiable que refleje amor por los animales '
                    'y profesionalismo. El sistema de diseño incluirá brandbook completo con paleta, tipografías, '
                    'iconografía y tono de voz definidos desde el inicio.',
                    'Cada flujo será diseñado priorizando la claridad y reduciendo la fricción: el adoptante '
                    'encontrará su animal en 3 clics, el donante completará su pago en menos de 2 minutos, '
                    'y el shelter admin gestionará sus animales desde un panel intuitivo sin manual.',
                ]
                cfg['content_json']['focusTitle'] = 'Principios de diseño'
                cfg['content_json']['focusItems'] = [
                    '🐾 Warm & trustworthy: paleta terracota + verde musgo + blanco roto',
                    '📱 Mobile-first: más del 70% del tráfico llegará desde dispositivos móviles',
                    '♿ Accesible: contraste AA, textos legibles y navegación por teclado',
                    '⚡ Performance: imágenes optimizadas, lazy loading y Skeleton loaders',
                ]
                cfg['content_json']['objectiveTitle'] = 'Objetivo de la experiencia'
                cfg['content_json']['objective'] = (
                    'Que cualquier persona —sin importar su nivel digital— pueda encontrar, adoptar o donar '
                    'a un animal en menos de 5 minutos desde la primera visita. Confianza antes que funcionalidad.'
                )

            elif st == 'creative_support':
                cfg['content_json']['index'] = '8'
                cfg['content_json']['title'] = 'Acompañamiento Creativo Personalizado'
                cfg['content_json']['paragraphs'] = [
                    'Laura tendrá acompañamiento directo en todas las decisiones de diseño y contenido. '
                    'Cada componente visual pasará por un ciclo de revisión antes de entrar en desarrollo.',
                    'El proceso será iterativo: primero wireframes de baja fidelidad para validar flujos, '
                    'luego mockups de alta fidelidad para aprobar la estética, y finalmente implementación.',
                ]
                cfg['content_json']['includesTitle'] = 'El acompañamiento incluye'
                cfg['content_json']['includes'] = [
                    '📐 Sesiones de revisión en Figma para aprobar wireframes y mockups antes de desarrollar',
                    '🎨 Definición colaborativa del brandbook: paleta, tipografías y tono de voz de Mi Huella',
                    '📸 Guía para fotografía de animales: cómo los refugios deben tomar fotos para la plataforma',
                    '✍️ Revisión de textos clave: landing, formularios, notificaciones y emails transaccionales',
                ]
                cfg['content_json']['closing'] = (
                    'Cada decisión de diseño será co-creada con Laura para asegurar que Mi Huella '
                    'refleje auténticamente la misión de Entre Especies y genere confianza desde el primer instante.'
                )

            elif st == 'process_methodology':
                cfg['content_json']['index'] = '9'
                cfg['content_json']['title'] = 'Proceso y Metodología'

            elif st == 'development_stages':
                cfg['content_json']['index'] = '10'
                cfg['content_json']['title'] = 'Etapas de Desarrollo'

            elif st == 'proposal_summary':
                cfg['content_json']['index'] = '11'
                cfg['content_json']['title'] = 'Resumen de la propuesta'

            elif st == 'final_note':
                cfg['content_json']['index'] = '12'
                cfg['content_json']['title'] = 'Nota final'

            elif st == 'next_steps':
                cfg['content_json']['index'] = '13'
                cfg['content_json']['title'] = 'Próximos pasos'

            elif st == 'technical_document':
                try:
                    from content.demo_technical_document import DEMO_TECHNICAL_DOCUMENT_JSON
                    cfg['content_json'] = deepcopy(DEMO_TECHNICAL_DOCUMENT_JSON)
                except ImportError:
                    pass

            ProposalSection.objects.create(proposal=proposal, **cfg)

        self.stdout.write(self.style.SUCCESS(
            f'  Created proposal: {proposal.title} (accepted, {proposal.sections.count()} sections)'
        ))

    def _create_project(self, client):
        existing = Project.objects.filter(client=client, name=PROJECT_NAME).first()
        if existing:
            self.stdout.write(f'  Project already exists: {PROJECT_NAME}')
            return existing

        today = self.seed_context.anchor_date
        project = Project.objects.create(
            name=PROJECT_NAME,
            description=(
                'Plataforma web de adopción y apadrinamiento de animales de refugio. '
                'Incluye catálogo de animales, sistema de solicitudes de adopción, '
                'campañas de donación con pasarela Wompi, panel de refugios, '
                'blog, y panel de administración con métricas. '
                '50 vistas, 27 modelos, 9 módulos.'
            ),
            client=client,
            status=Project.STATUS_ACTIVE,
            progress=0,
            start_date=today - timedelta(days=45),
            estimated_end_date=today + timedelta(days=90),
        )
        ProjectPhase.objects.create(
            project=project,
            business_proposal=BusinessProposal.objects.get(
                client_email=CLIENT_EMAIL, slug=PROPOSAL_SLUG,
            ),
            order=0,
        )
        self.stdout.write(self.style.SUCCESS(f'  Created project: {PROJECT_NAME}'))
        return project

    def _create_requirements(self, project):
        seed_validation_guides(project, VALIDATION_GUIDES, context=self.seed_context)

    def _create_change_requests(self, project, client, admin):
        if ChangeRequest.objects.filter(project=project).exists():
            self.stdout.write(f'  Change requests already exist for {project.name}')
            return

        crs = [
            {
                'title': 'Agregar filtro por raza en el catálogo de animales',
                'description': 'Los adoptantes nos piden poder filtrar no solo por especie y tamaño, sino también por raza. Por ejemplo: Labrador, Siamés, Mestizo.',
                'module_or_screen': 'Catálogo de animales (/animals)',
                'suggested_priority': 'high',
                'is_urgent': False,
                'status': ChangeRequest.STATUS_APPROVED,
                'admin_response': 'Tiene sentido. Agregaremos un campo "breed" al modelo Animal y un filtro adicional. Estimamos 3 días.',
                'estimated_cost': 0,
                'estimated_time': '3 días',
            },
            {
                'title': 'Botón de compartir perfil de animal en redes sociales',
                'description': 'Queremos que desde la ficha de cada animal se pueda compartir directamente en WhatsApp, Instagram y Facebook con una imagen preview (Open Graph).',
                'module_or_screen': 'Detalle de animal (/animals/[id])',
                'suggested_priority': 'medium',
                'is_urgent': False,
                'status': ChangeRequest.STATUS_EVALUATING,
                'admin_response': '',
            },
            {
                'title': 'Notificación cuando un animal favoritado es adoptado',
                'description': 'Si un usuario tiene un animal en favoritos y ese animal es adoptado, debería recibir una notificación amigable tipo "¡Loki encontró hogar!" y sugerencias de animales similares.',
                'module_or_screen': 'Notificaciones / Favoritos',
                'suggested_priority': 'medium',
                'is_urgent': False,
                'status': ChangeRequest.STATUS_PENDING,
                'admin_response': '',
            },
            {
                'title': 'Galería de "antes y después" para animales adoptados',
                'description': 'Los adoptantes quieren subir fotos del animal en su nuevo hogar. Sería una sección en el perfil del animal mostrando el antes y después.',
                'module_or_screen': 'Perfil de animal',
                'suggested_priority': 'low',
                'is_urgent': False,
                'status': ChangeRequest.STATUS_REJECTED,
                'admin_response': 'Es una idea muy bonita pero implica un módulo completo de UGC con moderación. Lo evaluaremos para la fase 2 del proyecto.',
            },
            {
                'title': 'Recibo de donación descargable en PDF para declaración de renta',
                'description': 'En Colombia las donaciones a fundaciones son deducibles de impuestos. Los donantes necesitan un recibo formal en PDF con NIT del refugio y monto.',
                'module_or_screen': 'Historial de donaciones (/my-donations)',
                'suggested_priority': 'high',
                'is_urgent': True,
                'status': ChangeRequest.STATUS_NEEDS_CLARIFICATION,
                'admin_response': '¿Cada refugio tiene su propio NIT o usamos el NIT de la fundación paraguas Entre Especies?',
            },
            {
                'title': 'Mapa interactivo con ubicación de refugios',
                'description': 'En el directorio de refugios, además de la lista, queremos un mapa tipo Google Maps donde se vean los pins de cada refugio verificado en Colombia.',
                'module_or_screen': 'Directorio de refugios (/shelters)',
                'suggested_priority': 'medium',
                'is_urgent': False,
                'status': ChangeRequest.STATUS_APPROVED,
                'admin_response': 'Integraremos Leaflet (open source) con los datos de ubicación. Estimamos 4 días incluyendo geocodificación.',
                'estimated_cost': 0,
                'estimated_time': '4 días',
            },
        ]

        for cr_data in crs:
            cr = ChangeRequest.objects.create(
                project=project,
                created_by=client,
                title=cr_data['title'],
                description=cr_data['description'],
                module_or_screen=cr_data.get('module_or_screen', ''),
                suggested_priority=cr_data['suggested_priority'],
                is_urgent=cr_data.get('is_urgent', False),
                status=cr_data['status'],
                admin_response=cr_data.get('admin_response', ''),
                estimated_cost=cr_data.get('estimated_cost'),
                estimated_time=cr_data.get('estimated_time', ''),
            )
            if cr_data.get('admin_response') and admin:
                ChangeRequestComment.objects.create(
                    change_request=cr,
                    user=admin,
                    content=cr_data['admin_response'],
                    is_internal=False,
                )

        self.stdout.write(self.style.SUCCESS(f'  Created {len(crs)} change requests'))

    def _create_bug_reports(self, project, client, admin):
        if BugReport.objects.filter(project=project).exists():
            self.stdout.write(f'  Bug reports already exist for {project.name}')
            return


        bugs = [
            {
                'title': 'Galería del animal no carga en Safari iOS',
                'description': 'En iPhones con Safari, las imágenes del Swiper de la galería del animal se quedan en blanco. Solo aparece el placeholder gris.',
                'severity': BugReport.SEVERITY_CRITICAL,
                'steps_to_reproduce': [
                    'Abrir /animals/15 desde un iPhone con Safari',
                    'Esperar a que cargue la página de detalle',
                    'La galería muestra un cuadro gris vacío',
                    'Deslizar no muestra más imágenes',
                ],
                'expected_behavior': 'La galería debería mostrar todas las fotos del animal con el carrusel Swiper funcional.',
                'actual_behavior': 'Las imágenes no cargan. Solo se ve el placeholder gris. El carrusel no responde al deslizamiento.',
                'environment': BugReport.ENV_PRODUCTION,
                'device_browser': 'iPhone 13 / Safari 17.2',
                'is_recurring': True,
                'status': BugReport.STATUS_FIXING,
                'admin_response': 'Confirmado. El problema es la carga lazy de imágenes con IntersectionObserver en Safari. Estamos implementando un polyfill.',
            },
            {
                'title': 'Filtro de tamaño "grande" muestra animales pequeños',
                'description': 'Al filtrar por tamaño "grande" en el catálogo, aparecen gatos y perros que claramente son pequeños o medianos.',
                'severity': BugReport.SEVERITY_HIGH,
                'steps_to_reproduce': [
                    'Ir a /animals',
                    'Seleccionar filtro Tamaño → Grande',
                    'Aparece "Luna" (gata siamés, 3kg) que es claramente pequeña',
                ],
                'expected_behavior': 'Solo deberían aparecer animales clasificados como "grande".',
                'actual_behavior': 'Mezcla animales de todos los tamaños. Parece que el filtro no está aplicando bien el campo size.',
                'environment': BugReport.ENV_PRODUCTION,
                'device_browser': 'Chrome 121 / macOS',
                'is_recurring': True,
                'status': BugReport.STATUS_CONFIRMED,
                'admin_response': 'El campo size de algunos animales fue ingresado como "large" y otros como "gran" (en español). Necesitamos normalizar la data y validar el input en el formulario del refugio.',
            },
            {
                'title': 'Donación se cobra dos veces al dar doble click',
                'description': 'Un donante reportó que al hacer doble click rápido en "Confirmar donación" se le cobró el monto duplicado. Aparecen 2 transacciones en Wompi.',
                'severity': BugReport.SEVERITY_CRITICAL,
                'steps_to_reproduce': [
                    'Ir a /checkout/donation',
                    'Seleccionar monto de $50.000',
                    'Completar datos de tarjeta en el widget Wompi',
                    'Hacer doble click rápido en "Confirmar donación"',
                    'Se procesan 2 cobros de $50.000',
                ],
                'expected_behavior': 'Solo se debería procesar un cobro. El botón debería deshabilitarse al primer click.',
                'actual_behavior': 'Se procesan dos cobros. No hay protección contra double-submit en el frontend.',
                'environment': BugReport.ENV_PRODUCTION,
                'device_browser': 'Chrome / Windows',
                'is_recurring': False,
                'status': BugReport.STATUS_REPORTED,
                'admin_response': '',
            },
            {
                'title': 'Email de confirmación de solicitud llega con caracteres raros',
                'description': 'El email que recibe el adoptante después de enviar la solicitud muestra "Â¡" en lugar de "¡" y otros caracteres en español mal codificados.',
                'severity': BugReport.SEVERITY_MEDIUM,
                'steps_to_reproduce': [
                    'Completar el formulario de solicitud de adopción de 3 pasos',
                    'Enviar la solicitud en el paso 3',
                    'Revisar el email de confirmación en Gmail',
                    'El asunto dice "Â¡Solicitud recibida!" en vez de "¡Solicitud recibida!"',
                ],
                'expected_behavior': 'El email debería mostrar caracteres en español correctamente (UTF-8).',
                'actual_behavior': 'Caracteres UTF-8 mal codificados (mojibake). Afecta tildes, ñ y signos de exclamación.',
                'environment': BugReport.ENV_PRODUCTION,
                'device_browser': 'Gmail web',
                'is_recurring': True,
                'status': BugReport.STATUS_RESOLVED,
                'admin_response': 'El template del email no tenía el header charset UTF-8. Corregido y desplegado en producción.',
            },
            {
                'title': 'Página de campaña muestra 0% aunque ya tiene donaciones',
                'description': 'La campaña "Esterilización masiva Soacha" tiene $2.300.000 recaudados pero la barra de progreso muestra 0% y $0.',
                'severity': BugReport.SEVERITY_HIGH,
                'steps_to_reproduce': [
                    'Ir a /campaigns',
                    'Click en la campaña "Esterilización masiva Soacha"',
                    'La barra muestra 0% y monto recaudado $0',
                    'Pero en el admin se ven 12 donaciones asociadas',
                ],
                'expected_behavior': 'Debería mostrar $2.300.000 / $5.000.000 (46%).',
                'actual_behavior': 'Muestra 0%. El campo total_raised no está siendo recalculado al confirmar pagos.',
                'environment': BugReport.ENV_PRODUCTION,
                'device_browser': 'Cualquier navegador',
                'is_recurring': True,
                'status': BugReport.STATUS_FIXING,
                'admin_response': 'El signal de post_save en Donation no está disparando la actualización de total_raised en Campaign. Lo estamos corrigiendo.',
            },
            {
                'title': 'El formulario de adopción no valida el campo "teléfono" en móvil',
                'description': 'En dispositivos móviles, el campo de teléfono del paso 1 del wizard acepta letras sin mostrar error. La solicitud se envía con teléfono inválido.',
                'severity': BugReport.SEVERITY_MEDIUM,
                'steps_to_reproduce': [
                    'Abrir /adopt/[animalId] desde un teléfono Android',
                    'En el paso 1, escribir "abcdef" en el campo Teléfono',
                    'Click en "Continuar"',
                    'El wizard avanza al paso 2 sin mostrar error de validación',
                ],
                'expected_behavior': 'El campo debería rechazar texto no numérico y mostrar el mensaje "Ingresa un teléfono válido".',
                'actual_behavior': 'No hay validación client-side en móvil. El pattern HTML5 no funciona con el teclado virtual de Android.',
                'environment': BugReport.ENV_STAGING,
                'device_browser': 'Android 13 / Chrome Mobile',
                'is_recurring': True,
                'status': BugReport.STATUS_CONFIRMED,
                'admin_response': 'Agregaremos validación explícita con Zod en el schema del formulario, sin depender del pattern nativo.',
            },
            {
                'title': 'Perfil de refugio no carga la sección de campañas activas',
                'description': 'En el perfil público de algunos refugios (/shelters/[id]), la sección "Campañas activas" aparece vacía aunque el refugio tiene campañas con status active.',
                'severity': BugReport.SEVERITY_HIGH,
                'steps_to_reproduce': [
                    'Ir a /shelters/3 (Refugio Huellitas Bogotá)',
                    'Hacer scroll hasta la sección "Campañas activas"',
                    'La sección aparece con el mensaje "Este refugio no tiene campañas activas"',
                    'Pero en el panel del refugio se ven 2 campañas activas',
                ],
                'expected_behavior': 'Deberían aparecer las 2 campañas activas del refugio con barra de progreso.',
                'actual_behavior': 'La query del endpoint /api/v1/shelters/{id}/ no está incluyendo campañas activas en el serializer.',
                'environment': BugReport.ENV_PRODUCTION,
                'device_browser': 'Firefox 121 / Windows',
                'is_recurring': True,
                'status': BugReport.STATUS_CONFIRMED,
                'admin_response': 'El campo campaigns estaba excluido del ShelterDetailSerializer. Ya está corregido en la rama de desarrollo.',
            },
            {
                'title': 'Tiempo de carga lento en /animals con más de 50 animales',
                'description': 'La página del catálogo tarda más de 8 segundos en cargar cuando hay más de 50 animales publicados. El problema es un N+1 en las queries.',
                'severity': BugReport.SEVERITY_MEDIUM,
                'steps_to_reproduce': [
                    'Ir a /animals con al menos 50 animales publicados',
                    'Abrir las DevTools → pestaña Network',
                    'La respuesta del endpoint /api/v1/animals/ tarda +8 segundos',
                    'El panel Django Debug Toolbar muestra 52 queries',
                ],
                'expected_behavior': 'El endpoint debería responder en menos de 500ms con todas las relaciones cargadas eficientemente.',
                'actual_behavior': 'N+1 query: cada animal hace 1 query adicional para el shelter. Con 50 animales = 52 queries.',
                'environment': BugReport.ENV_PRODUCTION,
                'device_browser': 'Cualquier navegador',
                'is_recurring': True,
                'status': BugReport.STATUS_FIXING,
                'admin_response': 'Agregaremos select_related("shelter") al queryset del AnimalListView. También implementaremos paginación de 12 por página.',
            },
            {
                'title': 'El webhook de Wompi no confirma apadrinamientos en staging',
                'description': 'Los pagos de apadrinamiento completados en sandbox de Wompi no cambian el status del Sponsorship a "active". El webhook llega (se ve en logs) pero el handler no procesa el evento.',
                'severity': BugReport.SEVERITY_CRITICAL,
                'steps_to_reproduce': [
                    'Ir a /checkout/sponsorship y completar un pago con tarjeta de prueba de Wompi',
                    'El pago aparece como approved en el dashboard de Wompi sandbox',
                    'Revisar /my-sponsorships → el apadrinamiento sigue en status "pending"',
                    'Revisar los logs del servidor → el webhook llegó con event_type "transaction.updated"',
                ],
                'expected_behavior': 'El webhook debería actualizar el Sponsorship a status "active" y crear el registro de PaymentHistory.',
                'actual_behavior': 'El handler del webhook solo procesa eventos de tipo "donation". Los eventos de "sponsorship" no tienen un case definido.',
                'environment': BugReport.ENV_STAGING,
                'device_browser': 'N/A (servidor)',
                'is_recurring': True,
                'status': BugReport.STATUS_REPORTED,
                'admin_response': '',
            },
        ]

        for bug_data in bugs:
            bug = BugReport.objects.create(
                project=project,
                reported_by=client,
                title=bug_data['title'],
                description=bug_data['description'],
                severity=bug_data['severity'],
                steps_to_reproduce=bug_data['steps_to_reproduce'],
                expected_behavior=bug_data['expected_behavior'],
                actual_behavior=bug_data['actual_behavior'],
                environment=bug_data['environment'],
                device_browser=bug_data.get('device_browser', ''),
                is_recurring=bug_data.get('is_recurring', False),
                status=bug_data['status'],
                admin_response=bug_data.get('admin_response', ''),
            )
            if bug_data.get('admin_response') and admin:
                BugComment.objects.create(
                    bug_report=bug,
                    user=admin,
                    content=bug_data['admin_response'],
                    is_internal=False,
                )

        self.stdout.write(self.style.SUCCESS(f'  Created {len(bugs)} bug reports'))

    def _create_deliverables(self, project, admin):
        if Deliverable.objects.filter(project=project).exists():
            self.stdout.write(f'  Deliverables already exist for {project.name}')
            return

        if not admin:
            self.stdout.write('  Skipping deliverables (no admin user found)')
            return

        from django.core.files.base import ContentFile

        # Each non-empty epic_key must be unique per project (UniqueConstraint condition)
        deliverables = [
            {
                'title': 'Wireframes UX — Flujos de adopción y checkout',
                'description': 'Wireframes de baja fidelidad para el wizard de solicitud de adopción (3 pasos), el checkout de donación y el checkout de apadrinamiento.',
                'category': Deliverable.CATEGORY_DESIGNS,
                'filename': 'wireframes-adopcion-checkout-v1.pdf',
                'epic_key': 'ADOPTION',
            },
            {
                'title': 'Diseño UI — Catálogo, detalle de animal y perfil de refugio',
                'description': 'Mockups finales en Figma exportados a PDF. Incluye versión desktop y mobile de /animals, /animals/[id], /shelters y /shelters/[id].',
                'category': Deliverable.CATEGORY_DESIGNS,
                'filename': 'ui-catalogo-animal-refugio-v2.pdf',
                'epic_key': 'LANDING',
            },
            {
                'title': 'Brandbook Mi Huella',
                'description': 'Guía de marca completa: logo, paleta de colores (terracota + verde musgo + blanco roto), tipografías, iconografía y tono de voz aprobados por Laura.',
                'category': Deliverable.CATEGORY_DESIGNS,
                'filename': 'mi-huella-brandbook-v1.pdf',
                'epic_key': '',
            },
            {
                'title': 'Credenciales Wompi Sandbox',
                'description': 'Llaves de API para pruebas en sandbox de la pasarela Wompi. Incluye public key, events secret y URL de webhooks configurada en staging.',
                'category': Deliverable.CATEGORY_OTHER,
                'filename': 'wompi-sandbox-keys.txt',
                'epic_key': 'CAMPAIGNS',
            },
            {
                'title': 'Manual de administración para shelter admins',
                'description': 'Guía paso a paso para administradores de refugio: cómo crear animales, gestionar campañas, responder solicitudes y publicar actualizaciones.',
                'category': Deliverable.CATEGORY_DOCUMENTS,
                'filename': 'manual-shelter-admin-v1.pdf',
                'epic_key': 'SHELTER_PANEL',
            },
            {
                'title': 'Diagrama de arquitectura del sistema',
                'description': 'Diagrama técnico: Next.js frontend, Django REST API, PostgreSQL, Redis, Wompi webhooks y Cloudinary para gestión de imágenes.',
                'category': Deliverable.CATEGORY_DOCUMENTS,
                'filename': 'arquitectura-mihuella-v1.pdf',
                'epic_key': '',
            },
            {
                'title': 'Documento de requerimientos funcionales (50 vistas)',
                'description': 'Especificación completa de las 50 vistas agrupadas en 10 módulos, con flujos de usuario, estados y reglas de negocio para cada una.',
                'category': Deliverable.CATEGORY_DOCUMENTS,
                'filename': 'requerimientos-funcionales-mihuella-v1.pdf',
                'epic_key': '',
            },
            {
                'title': 'Plan de integración Wompi — Webhooks y suscripciones',
                'description': 'Detalle técnico con el plan de integración de Wompi: endpoints, estructura de webhooks, manejo de eventos (donaciones y apadrinamientos) y casos de error.',
                'category': Deliverable.CATEGORY_DOCUMENTS,
                'filename': 'plan-integracion-wompi-v1.pdf',
                'epic_key': '',
            },
        ]

        for d_data in deliverables:
            placeholder = ContentFile(b'placeholder content', name=d_data['filename'])
            epic_key = d_data.get('epic_key', '')
            d = Deliverable.objects.create(
                project=project,
                uploaded_by=admin,
                title=d_data['title'],
                description=d_data['description'],
                category=d_data['category'],
                file=placeholder,
                current_version=1,
                source_epic_key=epic_key,
                source_epic_title=EPICS.get(epic_key, ''),
            )
            DeliverableVersion.objects.create(
                deliverable=d,
                file=placeholder,
                version_number=1,
                uploaded_by=admin,
            )

        self.stdout.write(self.style.SUCCESS(f'  Created {len(deliverables)} deliverables'))

    def _create_subscription(self, project):
        if HostingSubscription.objects.filter(project=project).exists():
            self.stdout.write(f'  Subscription already exists for {project.name}')
            return

        today = self.seed_context.anchor_date

        sub = HostingSubscription.objects.create(
            project=project,
            plan=HostingSubscription.PLAN_QUARTERLY,
            base_monthly_amount=Decimal('280000'),
            discount_percent=10,
            effective_monthly_amount=Decimal('252000'),
            billing_amount=Decimal('756000'),
            status=HostingSubscription.STATUS_ACTIVE,
            start_date=today - timedelta(days=45),
            next_billing_date=today + timedelta(days=45),
        )

        # First quarter — paid
        Payment.objects.create(
            subscription=sub,
            amount=sub.billing_amount,
            description=f'Hosting trimestral — {project.name}',
            billing_period_start=today - timedelta(days=45),
            billing_period_end=today + timedelta(days=44),
            due_date=today - timedelta(days=45),
            status=Payment.STATUS_PAID,
            paid_at=self.seed_context.anchor_now - timedelta(days=43),
        )

        # Next quarter — pending
        Payment.objects.create(
            subscription=sub,
            amount=sub.billing_amount,
            description=f'Hosting trimestral — {project.name}',
            billing_period_start=today + timedelta(days=45),
            billing_period_end=today + timedelta(days=134),
            due_date=today + timedelta(days=45),
            status=Payment.STATUS_PENDING,
        )

        self.stdout.write(self.style.SUCCESS('  Created subscription + 2 payments'))
