"""
Registry of all email templates used by ProposalEmailService and contact utils.

Each entry defines:
- name: Human-readable name shown in the admin UI.
- description: Short explanation of when this email is sent.
- category: 'client' | 'internal' | 'contact'
- html_template: Path to the Django HTML template (None for plain-text only).
- txt_template: Path to the Django plain-text template (None for plain-text only).
- editable_fields: List of dicts defining admin-editable text blocks.

Note: sample_context values for monetary fields use format_cop_email()
so previews always match the live email formatting.
- available_variables: List of variable names the admin can use in text.
- sample_context: Dict of sample values for preview rendering.
"""
from content.utils import format_cop_email


def _client_sample():
    """Common sample context for client-facing proposal emails."""
    return {
        'client_name': 'Carlos Rodríguez',
        'title': 'Plataforma E-commerce Premium',
        'proposal_url': 'https://projectapp.co/proposal/maria-lopez/',
        'days_remaining': 12,
        'expires_at': '2026-04-15',
        'total_investment': format_cop_email(15000000),
        'currency': 'COP',
    }


def _composed_email_base():
    """Shared config for user-composed email templates (branded & proposal)."""
    return {
        'category': 'client',
        'html_template': 'emails/branded_email.html',
        'txt_template': 'emails/branded_email.txt',
        'editable_fields': [
            {
                'key': 'greeting',
                'label': 'Saludo por defecto',
                'type': 'text',
                'default': 'Hola {client_name}',
            },
            {
                'key': 'footer',
                'label': 'Pie de correo por defecto',
                'type': 'textarea',
                'default': 'Quedamos atentos a tus comentarios.\nUn abrazo, el equipo de Project App.',
            },
        ],
        'available_variables': ['client_name', 'title'],
        'sample_context': {
            **_client_sample(),
            'greeting': 'Hola {client_name}',
            'sections': ['Texto de ejemplo para la primera sección.', 'Texto de ejemplo para la segunda sección.'],
            'footer': 'Quedamos atentos a tus comentarios.\nUn abrazo, el equipo de Project App.',
            'attachment_names': ['contrato.pdf', 'propuesta.pdf'],
        },
    }


def _internal_sample():
    """Common sample context for internal notification emails."""
    return {
        'client_name': 'Carlos Rodríguez',
        'title': 'Plataforma E-commerce Premium',
        'proposal_title': 'Plataforma E-commerce Premium',
        'total_investment': format_cop_email(15000000),
        'currency': 'COP',
        'proposal_uuid': 'abc-123-def-456',
    }


EMAIL_TEMPLATE_REGISTRY = {
    # -----------------------------------------------------------------------
    # Client-facing emails (sent to client_email)
    # -----------------------------------------------------------------------
    'proposal_sent_client': {
        'name': 'Propuesta Enviada',
        'description': 'Se envía cuando el vendedor envía la propuesta al cliente por primera vez. Adjunta el PDF comercial.',
        'category': 'client',
        'html_template': 'emails/proposal_sent_client.html',
        'txt_template': 'emails/proposal_sent_client.txt',
        'editable_fields': [
            {
                'key': 'subject',
                'label': 'Asunto del correo',
                'type': 'text',
                'default': '\U0001f4cb {client_name}, tu propuesta está lista — Project App',
            },
            {
                'key': 'greeting',
                'label': 'Saludo',
                'type': 'text',
                'default': 'Hola {client_name},',
            },
            {
                'key': 'body',
                'label': 'Cuerpo del mensaje',
                'type': 'textarea',
                'default': (
                    'Espero que estés muy bien. Te comparto la propuesta comercial '
                    'que hemos trabajado para tu proyecto. La hemos estructurado '
                    'para que puedas tomar decisiones con la información completa '
                    'sobre alcance, inversión y cronograma.'
                ),
            },
            {
                'key': 'closing',
                'label': 'Cierre del mensaje',
                'type': 'textarea',
                'default': (
                    'Encontrarás el detalle de los requerimientos funcionales, el '
                    'cronograma de ejecución, la metodología de trabajo y el detalle '
                    'técnico de la solución. Cualquier duda, ajuste o tema que '
                    'quieras conversar, agendamos una llamada cuando te quede '
                    'cómodo.\n\nQuedo atento a tus comentarios.'
                ),
            },
            {
                'key': 'cta_text',
                'label': 'Texto del botón',
                'type': 'text',
                'default': '\U0001f4cb Ver propuesta completa',
            },
        ],
        'available_variables': [
            'client_name', 'title', 'total_investment', 'currency',
            'days_remaining', 'email_intro', 'total_duration',
            'payment_summary',
        ],
        'sample_context': {
            **_client_sample(),
            'email_intro': (
                'Esta primera fase contempla la construcción de la plataforma '
                'base de tu firma: pantallas de inicio, registro, login y un '
                'dashboard como punto de entrada al trabajo diario, junto con '
                'el módulo central de elaboración guiada de demandas laborales.'
            ),
            'total_duration': 'Aproximadamente 1 mes',
            'payment_summary': '40/30/30',
            'payment_options': [
                {'label': '40% al firmar el contrato', 'description': '$1.728.000 COP'},
                {'label': '30% al aprobar el diseño final', 'description': '$1.296.000 COP'},
                {'label': '30% al desplegar la plataforma', 'description': '$1.296.000 COP'},
            ],
        },
    },

    'proposal_multi_sent_client': {
        'name': 'Propuesta Multi — Envío Conjunto',
        'description': (
            'Se envía cuando el vendedor envía 2+ propuestas del mismo '
            'cliente como un único correo. Adjunta el PDF comercial de cada '
            'propuesta seleccionada.'
        ),
        'category': 'client',
        'html_template': 'emails/proposal_multi_sent_client.html',
        'txt_template': 'emails/proposal_multi_sent_client.txt',
        'editable_fields': [
            {
                'key': 'subject',
                'label': 'Asunto del correo',
                'type': 'text',
                'default': '\U0001f4cb {client_name}, tus propuestas comerciales — Project App',
            },
            {
                'key': 'greeting',
                'label': 'Saludo',
                'type': 'text',
                'default': 'Hola {client_name},',
            },
            {
                'key': 'body',
                'label': 'Cuerpo del mensaje',
                'type': 'textarea',
                'default': (
                    'Espero que estés muy bien. Te comparto las propuestas '
                    'comerciales que hemos trabajado para tu proyecto. '
                    'Las hemos estructurado en fases para que puedas tomar '
                    'decisiones progresivas según tus prioridades y presupuesto.'
                ),
            },
            {
                'key': 'closing',
                'label': 'Cierre del mensaje',
                'type': 'textarea',
                'default': (
                    'En todas las propuestas encontrarás el detalle de los '
                    'requerimientos funcionales, el cronograma de ejecución, '
                    'la metodología de trabajo y el detalle técnico de la '
                    'solución. Cualquier duda, ajuste o tema que quieras '
                    'conversar, agendamos una llamada cuando te quede '
                    'cómodo.\n\nQuedo atento a tus comentarios.'
                ),
            },
        ],
        'available_variables': [
            'client_name', 'phases_count',
        ],
        'sample_context': {
            'client_name': 'Juan',
            'phases_count': 2,
            'phases': [
                {
                    'title': 'Fase 1 — Plataforma Jurídica',
                    'email_intro': (
                        'Esta primera fase contempla la construcción de la '
                        'plataforma base de tu firma...'
                    ),
                    'proposal_url': 'https://projectapp.co/proposal/juan-fase-1',
                    'total_investment': format_cop_email(4320000),
                    'currency': 'COP',
                    'total_duration': '1 mes',
                    'payment_summary': '40/30/30',
                    'payment_options': [
                        {'label': '40% al firmar el contrato', 'description': '$1.728.000 COP'},
                        {'label': '30% al aprobar el diseño final', 'description': '$1.296.000 COP'},
                        {'label': '30% al desplegar la plataforma', 'description': '$1.296.000 COP'},
                    ],
                },
                {
                    'title': 'Fase 2 — Módulo de Vigilancia Judicial',
                    'email_intro': (
                        'La segunda fase suma a la plataforma un módulo que '
                        'vigila automáticamente los procesos...'
                    ),
                    'proposal_url': 'https://projectapp.co/proposal/juan-fase-2',
                    'total_investment': format_cop_email(14100000),
                    'currency': 'COP',
                    'total_duration': '2 meses',
                    'payment_summary': '40/30/30',
                    'payment_options': [
                        {'label': '40% al firmar el contrato', 'description': '$5.640.000 COP'},
                        {'label': '30% al aprobar el diseño final', 'description': '$4.230.000 COP'},
                        {'label': '30% al desplegar el módulo', 'description': '$4.230.000 COP'},
                    ],
                },
            ],
        },
    },

    'proposal_reminder': {
        'name': 'Recordatorio de Propuesta',
        'description': 'Se envía N días después del envío si el cliente no ha respondido.',
        'category': 'client',
        'html_template': 'emails/proposal_reminder.html',
        'txt_template': 'emails/proposal_reminder.txt',
        'editable_fields': [
            {
                'key': 'subject',
                'label': 'Asunto del correo',
                'type': 'text',
                'default': '\U0001f4cb {client_name}, tu propuesta te espera — Project App',
            },
            {
                'key': 'greeting',
                'label': 'Saludo',
                'type': 'text',
                'default': 'Hola {client_name} \U0001f44b',
            },
            {
                'key': 'body',
                'label': 'Cuerpo del mensaje',
                'type': 'textarea',
                'default': (
                    'Preparamos una propuesta personalizada para tu proyecto y queremos '
                    'asegurarnos de que no se te pase revisarla.'
                ),
            },
            {
                'key': 'cta_text',
                'label': 'Texto del botón',
                'type': 'text',
                'default': '\U0001f449 Ver mi propuesta',
            },
        ],
        'available_variables': [
            'client_name', 'title', 'total_investment', 'currency',
            'days_remaining',
        ],
        'sample_context': {
            **_client_sample(),
        },
    },

    'proposal_urgency': {
        'name': 'Urgencia con Descuento',
        'description': 'Se envía al día 15 cuando hay descuento activo.',
        'category': 'client',
        'html_template': 'emails/proposal_urgency.html',
        'txt_template': 'emails/proposal_urgency.txt',
        'editable_fields': [
            {
                'key': 'subject',
                'label': 'Asunto del correo',
                'type': 'text',
                'default': (
                    '\U0001f525 {client_name}, tu propuesta expira pronto — '
                    '{discount_percent}% de descuento si accedes hoy'
                ),
            },
            {
                'key': 'greeting',
                'label': 'Saludo',
                'type': 'text',
                'default': '{client_name}, no dejes pasar esta oportunidad',
            },
            {
                'key': 'body',
                'label': 'Cuerpo del mensaje',
                'type': 'textarea',
                'default': (
                    'Tu propuesta {title} está por expirar. '
                    'Para que no pierdas esta oportunidad, te ofrecemos un '
                    '{discount_percent}% de descuento si accedes hoy.'
                ),
            },
            {
                'key': 'cta_text',
                'label': 'Texto del botón',
                'type': 'text',
                'default': '\U0001f525 Acceder a mi propuesta con descuento',
            },
        ],
        'available_variables': [
            'client_name', 'title', 'total_investment', 'currency',
            'days_remaining', 'discount_percent', 'discounted_investment',
        ],
        'sample_context': {
            **_client_sample(),
            'discount_percent': 15,
            'discounted_investment': format_cop_email(12750000),
        },
    },

    'proposal_urgency_no_discount': {
        'name': 'Urgencia sin Descuento',
        'description': 'Se envía al día 15 cuando NO hay descuento activo.',
        'category': 'client',
        'html_template': 'emails/proposal_urgency_no_discount.html',
        'txt_template': 'emails/proposal_urgency_no_discount.txt',
        'editable_fields': [
            {
                'key': 'subject',
                'label': 'Asunto del correo',
                'type': 'text',
                'default': '\u23f0 {client_name}, tu propuesta expira pronto — Project App',
            },
            {
                'key': 'greeting',
                'label': 'Saludo',
                'type': 'text',
                'default': '{client_name}, tu propuesta está por expirar',
            },
            {
                'key': 'body',
                'label': 'Cuerpo del mensaje',
                'type': 'textarea',
                'default': (
                    'Tu propuesta {title} expira pronto. '
                    'No queremos que pierdas esta oportunidad de transformar '
                    'tu presencia digital.'
                ),
            },
            {
                'key': 'cta_text',
                'label': 'Texto del botón',
                'type': 'text',
                'default': '\U0001f449 Ver mi propuesta',
            },
        ],
        'available_variables': [
            'client_name', 'title', 'total_investment', 'currency',
            'days_remaining',
        ],
        'sample_context': {
            **_client_sample(),
        },
    },

    'proposal_accepted_client': {
        'name': 'Confirmación de Aceptación',
        'description': 'Se envía al cliente cuando acepta la propuesta.',
        'category': 'client',
        'html_template': 'emails/proposal_accepted_client.html',
        'txt_template': 'emails/proposal_accepted_client.txt',
        'editable_fields': [
            {
                'key': 'subject',
                'label': 'Asunto del correo',
                'type': 'text',
                'default': '\u2705 {client_name}, tu propuesta ha sido aceptada — Project App',
            },
            {
                'key': 'greeting',
                'label': 'Saludo',
                'type': 'text',
                'default': '\u00a1Excelente, {client_name}! \U0001f389',
            },
            {
                'key': 'body',
                'label': 'Cuerpo del mensaje',
                'type': 'textarea',
                'default': (
                    'Hemos recibido tu confirmación para la propuesta {title}. '
                    'Estamos emocionados de comenzar este proyecto contigo. '
                    'Encontrarás enlaces y PDFs adjuntos: propuesta comercial, detalle técnico (si aplica) '
                    'y una guía para usar la plataforma de seguimiento.'
                ),
            },
            {
                'key': 'cta_text',
                'label': 'Texto del botón',
                'type': 'text',
                'default': '\U0001f4c4 Ver mi propuesta',
            },
        ],
        'available_variables': [
            'client_name', 'title', 'total_investment', 'currency',
            'platform_login_url', 'project_name', 'deliverable_title',
        ],
        'sample_context': {
            **_client_sample(),
            'platform_login_url': 'https://projectapp.co/platform/login',
            'project_name': 'Proyecto demo',
            'deliverable_title': 'Propuesta comercial',
        },
    },

    'proposal_finished_client': {
        'name': 'Cierre de Proyecto',
        'description': 'Se envía al cliente cuando su proyecto se marca como finalizado.',
        'category': 'client',
        'html_template': 'emails/proposal_finished_client.html',
        'txt_template': 'emails/proposal_finished_client.txt',
        'editable_fields': [
            {
                'key': 'subject',
                'label': 'Asunto del correo',
                'type': 'text',
                'default': '\U0001f3af {client_name}, tu proyecto ha sido finalizado — Project App',
            },
            {
                'key': 'greeting',
                'label': 'Saludo',
                'type': 'text',
                'default': '\u00a1Lo logramos, {client_name}! \U0001f3af',
            },
            {
                'key': 'body',
                'label': 'Cuerpo del mensaje',
                'type': 'textarea',
                'default': (
                    'Queremos confirmarte que el proyecto correspondiente a la propuesta '
                    '{title} ha sido finalizado exitosamente. Gracias por tu confianza y '
                    'por permitirnos acompa\u00f1arte en este proceso. Toda la documentaci\u00f3n '
                    'y los entregables permanecen disponibles en tu espacio de la plataforma.'
                ),
            },
            {
                'key': 'cta_text',
                'label': 'Texto del bot\u00f3n',
                'type': 'text',
                'default': '\U0001f4c2 Ir a la plataforma',
            },
        ],
        'available_variables': [
            'client_name', 'title', 'project_name', 'deliverable_title',
            'platform_login_url',
        ],
        'sample_context': {
            **_client_sample(),
            'platform_login_url': 'https://projectapp.co/platform/login',
            'project_name': 'Proyecto demo',
            'deliverable_title': 'Propuesta comercial',
        },
    },

    'proposal_rejected_client': {
        'name': 'Agradecimiento por Rechazo',
        'description': 'Se envía al cliente cuando rechaza la propuesta.',
        'category': 'client',
        'html_template': 'emails/proposal_rejected_client.html',
        'txt_template': 'emails/proposal_rejected_client.txt',
        'editable_fields': [
            {
                'key': 'subject',
                'label': 'Asunto del correo',
                'type': 'text',
                'default': 'Gracias por tu tiempo, {client_name} — Project App',
            },
            {
                'key': 'greeting',
                'label': 'Saludo',
                'type': 'text',
                'default': 'Gracias por tu tiempo, {client_name} \U0001f64f',
            },
            {
                'key': 'body',
                'label': 'Cuerpo del mensaje',
                'type': 'textarea',
                'default': (
                    'Lamentamos que la propuesta {title} no se ajuste a lo que '
                    'buscas en este momento. Tu opinión es muy valiosa para nosotros '
                    'y nos ayuda a seguir mejorando.'
                ),
            },
            {
                'key': 'inspirational_text',
                'label': 'Mensaje inspiracional',
                'type': 'textarea',
                'default': (
                    'En Project App creemos que cada proyecto tiene su momento perfecto. '
                    'Cuando estés listo para dar el siguiente paso en tu transformación digital, '
                    'estaremos aquí como tu aliado estratégico. No dudes en contactarnos '
                    'para explorar nuevas ideas o retomar esta conversación.'
                ),
            },
            {
                'key': 'cta_text',
                'label': 'Texto del botón',
                'type': 'text',
                'default': '\U0001f4ac Conversemos cuando estés listo',
            },
        ],
        'available_variables': ['client_name', 'title'],
        'sample_context': {
            'client_name': 'Carlos Rodríguez',
            'title': 'Plataforma E-commerce Premium',
        },
    },

    'proposal_reengagement': {
        'name': 'Re-engagement post Rechazo',
        'description': 'Se envía 48h después de un rechazo por presupuesto.',
        'category': 'client',
        'html_template': 'emails/proposal_reengagement.html',
        'txt_template': 'emails/proposal_reengagement.txt',
        'editable_fields': [
            {
                'key': 'subject',
                'label': 'Asunto del correo',
                'type': 'text',
                'default': (
                    '{client_name}, ¿podemos encontrar una solución '
                    'que se ajuste a tu presupuesto?'
                ),
            },
            {
                'key': 'greeting',
                'label': 'Saludo',
                'type': 'text',
                'default': '{client_name}, ¿podemos encontrar una solución? \U0001f91d',
            },
            {
                'key': 'body',
                'label': 'Cuerpo del mensaje',
                'type': 'textarea',
                'default': (
                    'Hace un par de días recibimos tu decisión sobre la propuesta '
                    '{title}. Entendemos completamente que el presupuesto es un '
                    'factor clave, y queremos explorar contigo si hay una forma de '
                    'hacer que esto funcione.'
                ),
            },
            {
                'key': 'cta_text',
                'label': 'Texto del botón',
                'type': 'text',
                'default': '\U0001f4ac Hablemos por WhatsApp',
            },
        ],
        'available_variables': [
            'client_name', 'title', 'total_investment', 'currency',
            'discount_percent', 'discounted_investment',
        ],
        'sample_context': {
            'client_name': 'Carlos Rodríguez',
            'title': 'Plataforma E-commerce Premium',
            'proposal_title': 'Plataforma E-commerce Premium',
            'total_investment': format_cop_email(15000000),
            'currency': 'COP',
            'discount_percent': 10,
            'discounted_investment': format_cop_email(13500000),
        },
    },

    'proposal_abandonment_followup': {
        'name': 'Seguimiento por Abandono',
        'description': 'Se envía cuando el cliente vio la propuesta pero no llegó a la sección de inversión.',
        'category': 'client',
        'html_template': 'emails/proposal_abandonment_followup.html',
        'txt_template': 'emails/proposal_abandonment_followup.txt',
        'editable_fields': [
            {
                'key': 'subject',
                'label': 'Asunto del correo',
                'type': 'text',
                'default': '\U0001f4cb {client_name}, ¿te quedaron dudas sobre la propuesta? — Project App',
            },
            {
                'key': 'greeting',
                'label': 'Saludo',
                'type': 'text',
                'default': 'Hola {client_name} \U0001f44b',
            },
            {
                'key': 'body',
                'label': 'Cuerpo del mensaje',
                'type': 'textarea',
                'default': (
                    'Noté que revisaste la propuesta "{title}" pero no alcanzaste a ver '
                    'todas las secciones. ¡Es totalmente normal! A veces hay mucho que procesar.'
                ),
            },
            {
                'key': 'body_secondary',
                'label': 'Segundo párrafo',
                'type': 'textarea',
                'default': (
                    '¿Te gustaría agendar una llamada rápida de 15 minutos para resolver '
                    'cualquier duda? Podemos repasar la propuesta juntos y ajustarla a lo que necesites.'
                ),
            },
            {
                'key': 'cta_text',
                'label': 'Texto del botón principal',
                'type': 'text',
                'default': '\U0001f449 Continuar revisando la propuesta',
            },
        ],
        'available_variables': ['client_name', 'title', 'proposal_url'],
        'sample_context': {
            **_client_sample(),
        },
    },

    'proposal_investment_interest_followup': {
        'name': 'Seguimiento por Interés en Inversión',
        'description': 'Se envía cuando el cliente pasó tiempo significativo en la sección de inversión.',
        'category': 'client',
        'html_template': 'emails/proposal_investment_interest_followup.html',
        'txt_template': 'emails/proposal_investment_interest_followup.txt',
        'editable_fields': [
            {
                'key': 'subject',
                'label': 'Asunto del correo',
                'type': 'text',
                'default': '\U0001f4b0 {client_name}, hablemos sobre opciones de inversión — Project App',
            },
            {
                'key': 'greeting',
                'label': 'Saludo',
                'type': 'text',
                'default': 'Hola {client_name} \U0001f4b0',
            },
            {
                'key': 'body',
                'label': 'Cuerpo del mensaje',
                'type': 'textarea',
                'default': (
                    'Noté que estás evaluando la inversión de la propuesta '
                    '"{title}". Es una decisión importante y queremos que te '
                    'sientas totalmente cómodo/a con ella.'
                ),
            },
            {
                'key': 'body_secondary',
                'label': 'Segundo párrafo',
                'type': 'textarea',
                'default': (
                    '¿Qué tal si hablamos sobre opciones de pago flexibles? '
                    'Podemos ajustar el plan de pagos a tu presupuesto y tiempos.'
                ),
            },
            {
                'key': 'cta_text',
                'label': 'Texto del botón principal',
                'type': 'text',
                'default': '\U0001f4ac Hablar sobre opciones de pago',
            },
        ],
        'available_variables': [
            'client_name', 'title', 'total_investment', 'currency',
            'time_on_investment',
        ],
        'sample_context': {
            **_client_sample(),
            'time_on_investment': '3m 45s',
        },
    },

    'proposal_scheduled_followup': {
        'name': 'Seguimiento Programado',
        'description': 'Se envía como follow-up programado tras rechazo por "no es el momento".',
        'category': 'client',
        'html_template': 'emails/proposal_scheduled_followup.html',
        'txt_template': 'emails/proposal_scheduled_followup.txt',
        'editable_fields': [
            {
                'key': 'subject',
                'label': 'Asunto del correo',
                'type': 'text',
                'default': '\U0001f44b {client_name}, ¿es buen momento para retomar tu proyecto? — Project App',
            },
            {
                'key': 'greeting',
                'label': 'Saludo',
                'type': 'text',
                'default': 'Hola {client_name} \U0001f44b',
            },
            {
                'key': 'body',
                'label': 'Cuerpo del mensaje',
                'type': 'textarea',
                'default': (
                    'Hace un tiempo nos pediste que te recordáramos sobre la propuesta '
                    '"{title}". ¡Aquí estamos!'
                ),
            },
            {
                'key': 'body_secondary',
                'label': 'Segundo párrafo',
                'type': 'textarea',
                'default': (
                    'Nos encantaría saber cómo va todo y si ahora es un buen momento '
                    'para retomar el proyecto. La propuesta sigue disponible y podemos '
                    'actualizarla según tus necesidades actuales.'
                ),
            },
            {
                'key': 'cta_text',
                'label': 'Texto del botón principal',
                'type': 'text',
                'default': '\U0001f449 Revisar la propuesta',
            },
        ],
        'available_variables': ['client_name', 'title', 'proposal_url'],
        'sample_context': {
            **_client_sample(),
        },
    },

    'proposal_negotiation_confirmation': {
        'name': 'Confirmación de Negociación',
        'description': 'Se envía al cliente cuando elige "Aceptar con cambios".',
        'category': 'client',
        'html_template': 'emails/proposal_negotiation_confirmation.html',
        'txt_template': 'emails/proposal_negotiation_confirmation.txt',
        'editable_fields': [
            {
                'key': 'subject',
                'label': 'Asunto del correo',
                'type': 'text',
                'default': '\U0001f91d {client_name}, recibimos tu solicitud de ajustes — Project App',
            },
            {
                'key': 'greeting',
                'label': 'Saludo',
                'type': 'text',
                'default': 'Hola {client_name},',
            },
            {
                'key': 'body',
                'label': 'Cuerpo del mensaje',
                'type': 'textarea',
                'default': (
                    'Recibimos tu solicitud para ajustar el alcance de la propuesta '
                    '"{title}". Nuestro equipo revisará tus notas y te contactará '
                    'en las próximas horas para conversar sobre las opciones.'
                ),
            },
            {
                'key': 'body_secondary',
                'label': 'Segundo párrafo',
                'type': 'textarea',
                'default': 'Mientras tanto, puedes seguir revisando la propuesta en cualquier momento:',
            },
            {
                'key': 'cta_text',
                'label': 'Texto del botón',
                'type': 'text',
                'default': '\U0001f4c4 Ver mi propuesta',
            },
        ],
        'available_variables': ['client_name', 'title', 'total_investment', 'currency'],
        'sample_context': {
            **_client_sample(),
        },
    },

    # -----------------------------------------------------------------------
    # Internal/Team emails (sent to NOTIFICATION_EMAIL)
    # -----------------------------------------------------------------------
    'proposal_response_notification': {
        'name': 'Notificación de Respuesta',
        'description': 'Se envía al equipo cuando el cliente acepta, rechaza o negocia.',
        'category': 'internal',
        'html_template': 'emails/proposal_response_notification.html',
        'txt_template': 'emails/proposal_response_notification.txt',
        'editable_fields': [
            {
                'key': 'subject',
                'label': 'Asunto del correo',
                'type': 'text',
                'default': '[{action_tag}] Propuesta: {title} — {client_name}',
            },
        ],
        'available_variables': [
            'client_name', 'title', 'total_investment', 'currency',
            'action', 'action_label', 'action_tag',
            'rejection_reason', 'rejection_comment',
        ],
        'sample_context': {
            **_internal_sample(),
            'action': 'accepted',
            'action_label': 'ACEPTADA',
            'action_tag': 'ACCEPTED',
            'rejection_reason': '',
            'rejection_comment': '',
        },
    },

    'proposal_first_view_notification': {
        'name': 'Primera Vista',
        'description': 'Se envía al equipo cuando el cliente abre la propuesta por primera vez.',
        'category': 'internal',
        'html_template': 'emails/proposal_first_view_notification.html',
        'txt_template': 'emails/proposal_first_view_notification.txt',
        'editable_fields': [
            {
                'key': 'subject',
                'label': 'Asunto del correo',
                'type': 'text',
                'default': '\U0001f441 [OPENED] Propuesta: {title} — {client_name}',
            },
            {
                'key': 'body',
                'label': 'Texto principal',
                'type': 'textarea',
                'default': (
                    '{client_name} acaba de abrir la propuesta por primera vez. '
                    'Tiene la propuesta frente a él/ella en este momento.'
                ),
            },
        ],
        'available_variables': [
            'client_name', 'proposal_title', 'total_investment', 'currency',
            'client_email', 'viewed_at',
        ],
        'sample_context': {
            **_internal_sample(),
            'client_email': 'carlos@empresa.com',
            'viewed_at': '2026-03-13 14:30',
        },
    },

    'proposal_comment_notification': {
        'name': 'Notificación de Comentario',
        'description': 'Se envía al equipo cuando el cliente envía un comentario de negociación.',
        'category': 'internal',
        'html_template': 'emails/proposal_comment_notification.html',
        'txt_template': 'emails/proposal_comment_notification.txt',
        'editable_fields': [
            {
                'key': 'subject',
                'label': 'Asunto del correo',
                'type': 'text',
                'default': '[COMENTARIO] Propuesta: {title} — {client_name}',
            },
        ],
        'available_variables': [
            'client_name', 'proposal_title', 'total_investment', 'currency',
            'comment',
        ],
        'sample_context': {
            **_internal_sample(),
            'comment': 'Me interesa pero necesito revisar el alcance del módulo de facturación.',
        },
    },

    'proposal_revisit_alert': {
        'name': 'Alerta de Revisitas',
        'description': 'Se envía al equipo cuando el cliente revisita la propuesta múltiples veces.',
        'category': 'internal',
        'html_template': 'emails/proposal_revisit_alert.html',
        'txt_template': 'emails/proposal_revisit_alert.txt',
        'editable_fields': [
            {
                'key': 'subject',
                'label': 'Asunto del correo',
                'type': 'text',
                'default': '\U0001f525 [HOT LEAD] {client_name} revisó la propuesta {visit_count} veces',
            },
        ],
        'available_variables': [
            'client_name', 'proposal_title', 'total_investment', 'currency',
            'visit_count', 'top_section', 'top_section_time',
        ],
        'sample_context': {
            **_internal_sample(),
            'visit_count': 5,
            'top_section': 'Inversión',
            'top_section_time': '4m 20s',
        },
    },

    'proposal_share_notification': {
        'name': 'Propuesta Compartida',
        'description': 'Se envía al equipo cuando el cliente comparte la propuesta con alguien.',
        'category': 'internal',
        'html_template': 'emails/proposal_share_notification.html',
        'txt_template': 'emails/proposal_share_notification.txt',
        'editable_fields': [
            {
                'key': 'subject',
                'label': 'Asunto del correo',
                'type': 'text',
                'default': '\U0001f517 [SHARED] {client_name} compartió la propuesta "{title}"',
            },
            {
                'key': 'body',
                'label': 'Texto principal',
                'type': 'textarea',
                'default': (
                    '{client_name} ha compartido la propuesta "{title}" con alguien más. '
                    'Esto es una señal positiva: el cliente está involucrando a más personas en la decisión.'
                ),
            },
        ],
        'available_variables': [
            'client_name', 'proposal_title', 'shared_by_name', 'shared_by_email',
        ],
        'sample_context': {
            **_internal_sample(),
            'shared_by_name': 'María López',
            'shared_by_email': 'maria@empresa.com',
        },
    },

    'proposal_stakeholder_detected': {
        'name': 'Stakeholder Detectado',
        'description': 'Se envía al equipo cuando se detecta acceso desde una nueva IP.',
        'category': 'internal',
        'html_template': 'emails/proposal_stakeholder_detected.html',
        'txt_template': 'emails/proposal_stakeholder_detected.txt',
        'editable_fields': [
            {
                'key': 'subject',
                'label': 'Asunto del correo',
                'type': 'text',
                'default': '\U0001f465 [NUEVO LECTOR] Propuesta: {title} — {client_name}',
            },
        ],
        'available_variables': [
            'client_name', 'proposal_title', 'total_investment', 'currency',
            'known_ips_count',
        ],
        'sample_context': {
            **_internal_sample(),
            'known_ips_count': 3,
        },
    },

    'seller_inactivity_escalation': {
        'name': 'Escalación por Inactividad',
        'description': 'Se envía al equipo cuando una propuesta lleva 5+ días sin seguimiento del vendedor.',
        'category': 'internal',
        'html_template': 'emails/seller_inactivity_escalation.html',
        'txt_template': 'emails/seller_inactivity_escalation.txt',
        'editable_fields': [
            {
                'key': 'subject',
                'label': 'Asunto del correo',
                'type': 'text',
                'default': '\u26a0\ufe0f Propuesta sin seguimiento: {client_name} — {title}',
            },
            {
                'key': 'body',
                'label': 'Texto principal',
                'type': 'textarea',
                'default': (
                    'La propuesta para {client_name} lleva {days_inactive} días sin ninguna '
                    'actividad de seguimiento. El cliente ya revisó la propuesta — cada día '
                    'sin contacto reduce las probabilidades de cierre.'
                ),
            },
        ],
        'available_variables': [
            'client_name', 'proposal_title', 'total_investment', 'currency',
            'days_inactive', 'edit_url', 'status',
        ],
        'sample_context': {
            **_internal_sample(),
            'days_inactive': 7,
            'edit_url': 'https://projectapp.co/panel/proposals/1/edit',
            'status': 'viewed',
        },
    },

    'proposal_negotiation_notification': {
        'name': 'Notificación de Negociación',
        'description': 'Se envía al equipo cuando el cliente quiere aceptar con cambios.',
        'category': 'internal',
        'html_template': 'emails/proposal_negotiation_notification.html',
        'txt_template': 'emails/proposal_negotiation_notification.txt',
        'editable_fields': [
            {
                'key': 'subject',
                'label': 'Asunto del correo',
                'type': 'text',
                'default': '\U0001f91d [NEGOCIANDO] {client_name} quiere ajustar la propuesta "{title}"',
            },
        ],
        'available_variables': [
            'client_name', 'proposal_title', 'total_investment', 'currency',
            'comment', 'edit_url',
        ],
        'sample_context': {
            **_internal_sample(),
            'comment': 'Necesito ajustar el alcance del módulo de pagos.',
            'edit_url': 'https://projectapp.co/panel/proposals/1/edit',
        },
    },

    'post_rejection_revisit_alert': {
        'name': 'Revisita Post-Rechazo',
        'description': 'Se envía al equipo cuando un cliente rechazado revisita la propuesta.',
        'category': 'internal',
        'html_template': 'emails/post_rejection_revisit_alert.html',
        'txt_template': 'emails/post_rejection_revisit_alert.txt',
        'editable_fields': [
            {
                'key': 'subject',
                'label': 'Asunto del correo',
                'type': 'text',
                'default': (
                    '\U0001f504 [RECONSIDERACIÓN] {client_name} revisitó la propuesta '
                    'rechazada "{title}" ({days_since_rejection}d después)'
                ),
            },
            {
                'key': 'body',
                'label': 'Texto principal',
                'type': 'textarea',
                'default': (
                    '{client_name} revisitó la propuesta "{title}" que había rechazado hace '
                    '{days_since_rejection} días. Este comportamiento sugiere que el cliente está '
                    'reconsiderando y es un excelente momento para retomar contacto.'
                ),
            },
        ],
        'available_variables': [
            'client_name', 'proposal_title', 'total_investment', 'currency',
            'days_since_rejection', 'edit_url',
        ],
        'sample_context': {
            **_internal_sample(),
            'days_since_rejection': 12,
            'edit_url': 'https://projectapp.co/panel/proposals/1/edit',
        },
    },

    'daily_pipeline_digest': {
        'name': 'Resumen Diario de Pipeline',
        'description': 'Se envía todos los días a las 7 AM con resumen de propuestas.',
        'category': 'internal',
        'html_template': 'emails/daily_pipeline_digest.html',
        'txt_template': 'emails/daily_pipeline_digest.txt',
        'editable_fields': [
            {
                'key': 'subject',
                'label': 'Asunto del correo',
                'type': 'text',
                'default': '\U0001f4ca Pipeline Diario — {date} — {total_active} propuestas activas',
            },
        ],
        'available_variables': [
            'date', 'total_active', 'viewed_yesterday', 'inactive',
            'expiring_soon',
        ],
        'sample_context': {
            'date': '2026-03-13',
            'total_active': 8,
            'viewed_yesterday': [
                {'client_name': 'Carlos', 'title': 'E-commerce', 'status': 'viewed'},
            ],
            'inactive': [
                {'client_name': 'Ana', 'title': 'App Móvil', 'days_inactive': 5},
            ],
            'expiring_soon': [
                {'client_name': 'Luis', 'title': 'SaaS', 'expires_at': '2026-03-18'},
            ],
        },
    },

    'proposal_post_expiration_visit': {
        'name': 'Visita Post-Expiración',
        'description': 'Se envía al equipo cuando un cliente abre una propuesta ya expirada.',
        'category': 'internal',
        'html_template': 'emails/proposal_post_expiration_visit.html',
        'txt_template': 'emails/proposal_post_expiration_visit.txt',
        'editable_fields': [
            {
                'key': 'subject',
                'label': 'Asunto del correo',
                'type': 'text',
                'default': (
                    '\U0001f525 {client_name} abrió la propuesta expirada '
                    '"{title}" — ¡Alto interés!'
                ),
            },
        ],
        'available_variables': [
            'client_name', 'proposal_title', 'total_investment', 'currency',
            'edit_url',
        ],
        'sample_context': {
            **_internal_sample(),
            'edit_url': 'https://projectapp.co/panel/proposals/1/edit',
        },
    },

    # -----------------------------------------------------------------------
    # Contact (plain text)
    # -----------------------------------------------------------------------
    'contact_notification': {
        'name': 'Notificación de Contacto',
        'description': 'Se envía al equipo cuando alguien envía el formulario de contacto.',
        'category': 'contact',
        'html_template': None,
        'txt_template': None,
        'editable_fields': [
            {
                'key': 'subject',
                'label': 'Asunto del correo',
                'type': 'text',
                'default': 'Nuevo mensaje de contacto: {subject}',
            },
            {
                'key': 'body',
                'label': 'Cuerpo del mensaje',
                'type': 'textarea',
                'default': (
                    'Nuevo mensaje de contacto recibido:\n\n'
                    '━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n'
                    'Email: {email}\n'
                    'Teléfono: {phone}\n'
                    'Presupuesto: {budget}\n'
                    '━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n'
                    'Asunto: {subject}\n\n'
                    'Mensaje:\n{message}\n\n'
                    '━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n'
                    'Este mensaje fue enviado desde el formulario de contacto de projectapp.co'
                ),
            },
        ],
        'available_variables': [
            'email', 'phone', 'budget', 'subject', 'message',
        ],
        'sample_context': {
            'email': 'ejemplo@empresa.com',
            'phone': '+57 312 345 6789',
            'budget': '$10,000,000 COP',
            'subject': 'Consulta sobre desarrollo web',
            'message': 'Hola, me interesa desarrollar una plataforma para mi empresa.',
        },
    },

    # -----------------------------------------------------------------------
    # Document dispatch (manual send from documents tab)
    # -----------------------------------------------------------------------
    'proposal_formalization': {
        'name': 'Formalización de proyecto',
        'description': 'Documentación formal para revisión y firma desde Documentos de la propuesta.',
        'category': 'client',
        'html_template': 'emails/proposal_formalization.html',
        'txt_template': 'emails/proposal_formalization.txt',
        'editable_fields': [
            {'key': 'subject', 'label': 'Asunto', 'type': 'text', 'default': 'Documentación para formalización — {title}'},
            {'key': 'greeting', 'label': 'Saludo', 'type': 'text', 'default': 'Hola {client_name},'},
            {'key': 'body', 'label': 'Introducción', 'type': 'textarea', 'default': 'Te compartimos la documentación de {title} para su revisión y para coordinar la firma de los documentos que correspondan.'},
            {'key': 'footer', 'label': 'Cierre', 'type': 'textarea', 'default': 'Por favor, compártenos tus observaciones respondiendo este correo. Una vez revisada la documentación, coordinaremos la firma.'},
        ],
        'available_variables': ['client_name', 'title'],
        'sample_context': {**_client_sample(), 'sections': ['Documentación para revisión y firma.']},
    },
    'proposal_documents_sent': {
        'name': 'Documentos Enviados al Cliente',
        'description': 'Se envía cuando el vendedor envía documentos (borrador de contrato, propuesta, etc.) al cliente desde el tab de documentos.',
        'category': 'client',
        'html_template': 'emails/proposal_documents_sent.html',
        'txt_template': 'emails/proposal_documents_sent.txt',
        'editable_fields': [
            {
                'key': 'subject',
                'label': 'Asunto del correo',
                'type': 'text',
                'default': '📎 {client_name}, te compartimos documentos de tu proyecto — Project App',
            },
            {
                'key': 'greeting',
                'label': 'Saludo',
                'type': 'text',
                'default': 'Hola {client_name} 👋',
            },
            {
                'key': 'body',
                'label': 'Texto introductorio',
                'type': 'textarea',
                'default': (
                    'Te enviamos los siguientes documentos relacionados con tu proyecto. '
                    'Encontrarás cada uno adjunto a este correo.'
                ),
            },
            {
                'key': 'footer',
                'label': 'Texto de cierre',
                'type': 'textarea',
                'default': (
                    'Si tienes dudas sobre alguno de los documentos, '
                    'no dudes en responder este correo o escribirnos por WhatsApp.'
                ),
            },
        ],
        'available_variables': [
            'client_name', 'title', 'document_descriptions',
        ],
        'sample_context': {
            **_client_sample(),
            'document_descriptions': [
                {
                    'name': 'Contrato de desarrollo',
                    'description': 'Contrato de desarrollo de software formalizado para el proyecto.',
                },
                {
                    'name': 'Propuesta comercial',
                    'description': 'Propuesta comercial con el alcance, inversión y condiciones del proyecto.',
                },
            ],
        },
    },

    # -----------------------------------------------------------------------
    # Project-stage tracking — internal team notifications
    # Sent by the daily Huey task `notify_proposal_stage_deadlines` based on
    # ProposalProjectStage rows (start/end dates set per stage from the
    # admin Cronograma tab).
    # -----------------------------------------------------------------------
    'proposal_stage_warning_notification': {
        'name': 'Aviso 70% Etapa de Proyecto',
        'description': (
            'Se envía al equipo cuando una etapa del cronograma del proyecto '
            '(diseño o desarrollo) ha transcurrido el 70% de su tiempo planeado. '
            'Sirve como aviso temprano para evitar que la etapa se cuelgue.'
        ),
        'category': 'internal',
        'html_template': 'emails/proposal_stage_warning_notification.html',
        'txt_template': 'emails/proposal_stage_warning_notification.txt',
        'editable_fields': [
            {
                'key': 'subject',
                'label': 'Asunto del correo',
                'type': 'text',
                'default': (
                    '\u26a0\ufe0f Etapa {stage_label} cerca de vencer — '
                    '{client_name} ({proposal_title})'
                ),
            },
            {
                'key': 'intro',
                'label': 'Texto principal',
                'type': 'textarea',
                'default': (
                    'La etapa de {stage_label} para {client_name} '
                    '({proposal_title}) terminará en {time_remaining_human}. '
                    'Verifica si vamos en tiempo o si hay riesgo de retraso.'
                ),
            },
        ],
        'available_variables': [
            'client_name', 'proposal_title', 'stage_label',
            'time_remaining_human', 'start_date_human', 'end_date_human',
            'edit_url',
        ],
        'sample_context': {
            **_internal_sample(),
            'stage_label': 'Diseño',
            'time_remaining_human': '1 semana 2 días',
            'start_date_human': 'Mié, 1 abr 2026',
            'end_date_human': 'Mié, 15 abr 2026',
            'edit_url': 'https://projectapp.co/panel/proposals/42/edit?tab=schedule',
        },
    },

    'proposal_stage_overdue_notification': {
        'name': 'Etapa de Proyecto Vencida',
        'description': (
            'Se envía al equipo cuando una etapa del cronograma ya pasó su '
            'fecha fin. Se reenvía como recordatorio cada 3 días mientras '
            'la etapa no se marque como completada en el panel.'
        ),
        'category': 'internal',
        'html_template': 'emails/proposal_stage_overdue_notification.html',
        'txt_template': 'emails/proposal_stage_overdue_notification.txt',
        'editable_fields': [
            {
                'key': 'subject',
                'label': 'Asunto del correo',
                'type': 'text',
                'default': (
                    '\U0001f534 Etapa {stage_label} VENCIDA — '
                    '{client_name} ({proposal_title})'
                ),
            },
            {
                'key': 'intro',
                'label': 'Texto principal',
                'type': 'textarea',
                'default': (
                    'La etapa de {stage_label} para {client_name} '
                    '({proposal_title}) debió haber terminado hace '
                    '{time_overdue_human}. Marca la etapa como completada '
                    'en el panel para silenciar este recordatorio.'
                ),
            },
        ],
        'available_variables': [
            'client_name', 'proposal_title', 'stage_label',
            'time_overdue_human', 'days_overdue', 'end_date_human', 'edit_url',
        ],
        'sample_context': {
            **_internal_sample(),
            'stage_label': 'Desarrollo',
            'time_overdue_human': '3 días',
            'days_overdue': 3,
            'end_date_human': 'Lun, 6 abr 2026',
            'edit_url': 'https://projectapp.co/panel/proposals/42/edit?tab=schedule',
        },
    },

    # -----------------------------------------------------------------------
    # User-composed emails (branded & proposal) — shared config
    # -----------------------------------------------------------------------
    'branded_email': {
        'name': 'Correo con Branding',
        'description': 'Correo genérico con branding de la marca, compuesto por el usuario desde la pestaña Correos.',
        **_composed_email_base(),
    },
    'proposal_email': {
        'name': 'Correo de Propuesta',
        'description': 'Correo compuesto por el vendedor desde la pestaña Enviar correo. Se registra como actividad de la propuesta.',
        **_composed_email_base(),
    },
    'delivery_stage_approved_client': {
        'name': 'Cierre de Etapa Aprobada',
        'description': 'Constancia manual revisada por el administrador cuando el cliente aprueba todos los requerimientos de una etapa.',
        **_composed_email_base(),
    },
    'delivery_published_client': {
        'name': 'Etapa disponible para revisión',
        'description': 'Aviso automático de publicación o nueva ronda; no acredita conformidad.',
        'category': 'client', 'html_template': 'emails/delivery_activity.html', 'txt_template': 'emails/delivery_activity.txt',
        'editable_fields': [], 'available_variables': [], 'sample_context': {},
    },
    'delivery_reviewed_team': {
        'name': 'Observaciones de revisión de entregas',
        'description': 'Aviso al equipo por objeción, rechazo o comentario del cliente.',
        'category': 'internal', 'html_template': 'emails/delivery_activity.html', 'txt_template': 'emails/delivery_activity.txt',
        'editable_fields': [], 'available_variables': [], 'sample_context': {},
    },
    'delivery_message_client': {
        'name': 'Respuesta pública de seguimiento',
        'description': 'Aviso al cliente sobre una respuesta pública del equipo.',
        'category': 'client', 'html_template': 'emails/delivery_activity.html', 'txt_template': 'emails/delivery_activity.txt',
        'editable_fields': [], 'available_variables': [], 'sample_context': {},
    },
    'delivery_message_team': {
        'name': 'Comentario del cliente en seguimiento',
        'description': 'Aviso al equipo sobre un comentario público del cliente.',
        'category': 'internal', 'html_template': 'emails/delivery_activity.html', 'txt_template': 'emails/delivery_activity.txt',
        'editable_fields': [], 'available_variables': [], 'sample_context': {},
    },
}


def get_registry():
    """Return the full email template registry."""
    return EMAIL_TEMPLATE_REGISTRY


def get_template_entry(template_key):
    """Return a single registry entry or None."""
    return EMAIL_TEMPLATE_REGISTRY.get(template_key)


def get_all_keys():
    """Return all registered template keys."""
    return list(EMAIL_TEMPLATE_REGISTRY.keys())


def get_default_field_values(template_key):
    """
    Return a dict of {field_key: default_value} for a given template.
    """
    entry = EMAIL_TEMPLATE_REGISTRY.get(template_key)
    if not entry:
        return {}
    return {
        field['key']: field['default']
        for field in entry.get('editable_fields', [])
    }


def resolve_field_values(template_key, overrides=None):
    """
    Merge defaults with overrides, returning the final {field_key: value} dict.
    """
    defaults = get_default_field_values(template_key)
    if overrides:
        for key, value in overrides.items():
            if key in defaults and value:
                defaults[key] = value
    return defaults


def substitute_variables(text, context):
    """
    Replace {variable} placeholders in text with actual context values.

    Uses str.format_map with a defaultdict so missing keys are left as-is.
    """
    if not text or not context:
        return text or ''

    class SafeDict(dict):
        def __missing__(self, key):
            return '{' + key + '}'

    try:
        return text.format_map(SafeDict(**{k: str(v) for k, v in context.items()}))
    except (KeyError, ValueError, IndexError):
        return text
