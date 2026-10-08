import { LEGAL_ENTITY as L } from '../../config/legalEntity.js'

// Official (Spanish) copy of the Waiter product and legal pages published for
// Meta's WhatsApp Tech Provider review. Source: waiter_project
// docs/legal/requisitos-projectapp-verificacion-meta.md (2026-10-07).
// Inline markup rendered by components/legal/LegalRichText.vue:
// **bold**, `code` and [label](href).

const MAIL = `[${L.email}](mailto:${L.email})`
const PHONE = `[${L.phone}](${L.phoneHref})`
const ADDRESS = `${L.address}, ${L.city}, ${L.country}`
const HOURS = 'lunes a viernes, de 8:00 a. m. a 6:00 p. m., hora de Colombia'
const UPDATED = 'Última actualización: 7 de octubre de 2026.'

export default {
  footer: {
    nav_label: 'Páginas legales de Waiter',
    product: 'Waiter',
    privacy: 'Política de privacidad de Waiter',
    terms: 'Condiciones del servicio de Waiter',
    data_deletion: 'Eliminación de datos',
    contact: 'Contacto',
    phone_label: 'Teléfono',
    copyright: '© 2026 ProjectApp. Waiter es un producto de ProjectApp.',
  },

  company: {
    title: 'Datos de la empresa',
    legal_name: 'Razón comercial',
    owner: 'Titular',
    nit: 'NIT',
    address: 'Dirección',
    phone: 'Teléfono y WhatsApp',
    email: 'Ventas, soporte y privacidad',
    hours: 'Horario de atención',
    hours_value: 'Lunes a viernes, 8:00 a. m. a 6:00 p. m., hora de Colombia',
  },

  back_to_waiter: 'Volver a Waiter',
  back_to_home: 'Volver al inicio',

  product: {
    eyebrow: 'Un producto de ProjectApp',
    title: 'Waiter',
    tagline: 'El sistema para restaurantes que también atiende por WhatsApp.',
    intro:
      'Waiter es el punto de venta de ProjectApp para restaurantes en Colombia: caja, mesas y salón, pedidos, pantalla de cocina, inventario y recetas, reservas, clientes y puntos, menú digital con código QR, pagos en línea y reportes.',
    cta_contact: 'Habla con nosotros',
    cta_privacy: 'Política de privacidad',
    features: [
      {
        title: 'Todo el restaurante en un solo sistema',
        text: 'Caja con apertura y cuadre, plano del salón, pedidos por mesa, para llevar y a domicilio, pantalla de cocina, inventario con recetas, reservas con anticipo, clientes con puntos y beneficios, facturación, reportes y una consola para el dueño con todos sus locales.',
      },
      {
        title: 'Menú digital con asistente',
        text: 'El cliente escanea el QR de la mesa, ve la carta, hace su pedido y paga desde su celular. Un asistente con inteligencia artificial le ayuda a elegir y responde sus dudas sobre los platos.',
      },
      {
        title: 'Atención por WhatsApp',
        text: 'El restaurante conecta su número de WhatsApp Business a Waiter con el registro oficial de Meta, en unos minutos y sin cambiar de número. El asistente contesta los mensajes de sus clientes sobre la carta, el horario y la ubicación; arma el pedido, muestra el total calculado por el sistema y lo envía a la cocina solo cuando el cliente lo confirma. El personal puede tomar la conversación en cualquier momento.',
      },
    ],
    steps_title: 'Así funciona la conexión con WhatsApp',
    steps: [
      'El dueño entra a su consola de Waiter y pulsa «Conectar WhatsApp».',
      'Inicia sesión con su cuenta de Meta y autoriza a Waiter a enviar y recibir mensajes en nombre de su negocio.',
      'Verifica su número con el código que le llega por SMS o llamada.',
      'Desde ese momento, los mensajes de sus clientes llegan al asistente de Waiter, y los pedidos, al punto de venta.',
    ],
    steps_note:
      'El restaurante puede desconectar su número cuando quiera desde la consola de Waiter o desde su cuenta de Meta.',
    data_title: 'Tus datos y los de tus clientes',
    data_text:
      'El restaurante es el dueño de la información de sus clientes; ProjectApp la trata solo para prestar el servicio. Lee nuestra [política de privacidad](/waiter/privacy), las [condiciones del servicio](/waiter/terms) y [cómo pedir la eliminación de tus datos](/waiter/data-deletion).',
  },

  privacy: {
    title: 'Política de tratamiento de datos personales de ProjectApp',
    last_updated: UPDATED,
    notice:
      'Esta política aplica a **Waiter** y a sus usuarios. El uso del sitio projectapp.co y de los servicios de desarrollo de ProjectApp se rige además por la [política de privacidad del sitio](/privacy-policy).',
    sections: [
      {
        id: 'quienes-somos',
        title: '1. Quiénes somos',
        blocks: [
          { p: `ProjectApp es el nombre comercial de **${L.tradeName}**, establecimiento de comercio de **${L.owner}**, identificado con NIT ${L.nit} (cédula de ciudadanía ${L.nationalId}), con domicilio en ${ADDRESS}, teléfono ${PHONE} y correo ${MAIL} («ProjectApp», «nosotros»).` },
          { p: 'ProjectApp desarrolla y opera **Waiter**, un sistema en la nube para restaurantes: punto de venta, salón, cocina, inventario, reservas, clientes y puntos, menú digital con código QR, pagos en línea, asistente con inteligencia artificial en el menú y en WhatsApp, facturación y reportes.' },
        ],
      },
      {
        id: 'nuestro-papel',
        title: '2. Nuestro papel frente a tus datos',
        blocks: [
          {
            ul: [
              '**Cuando eres cliente de un restaurante que usa Waiter** (comensal, persona que reserva o escribe por WhatsApp), el **responsable** del tratamiento es **ese restaurante**: él decide qué datos pide y para qué. ProjectApp actúa como **encargado del tratamiento**: trata tus datos por cuenta del restaurante, solo para prestarle el servicio de Waiter y según sus instrucciones. Para ejercer tus derechos puedes acudir al restaurante o a nosotros, y le daremos traslado.',
              '**Cuando eres empleado de un restaurante** que usa Waiter, el responsable es el restaurante, que es tu empleador, y ProjectApp es encargado.',
              '**Cuando eres dueño o representante de un restaurante que contrata Waiter, persona del equipo de ProjectApp o visitante de projectapp.co**, ProjectApp es el **responsable**.',
            ],
          },
        ],
      },
      {
        id: 'datos-que-tratamos',
        title: '3. Qué datos tratamos',
        blocks: [
          { h3: '3.1 Clientes de los restaurantes (comensales)' },
          {
            ul: [
              '**Si usas el menú digital sin registrarte:** un identificador aleatorio guardado en una cookie y, si lo escribes, tu nombre o apodo.',
              {
                text: '**Si creas una cuenta en el menú de un restaurante:**',
                items: [
                  'nombre, correo y, si lo das, celular;',
                  'contraseña, que guardamos cifrada con un algoritmo de un solo sentido;',
                  'alergias o alimentos que evitas, si los escribes;',
                  'si aceptas recibir novedades, que viene sin marcar;',
                  'la constancia de que aceptaste esta política;',
                  'platos favoritos, beneficios y premios, y las opiniones y calificaciones que dejes.',
                ],
              },
              {
                text: '**Si el restaurante te registra como cliente:**',
                items: [
                  'nombre, teléfono, correo;',
                  'tipo y número de documento;',
                  'dirección y ciudad;',
                  'puntos, beneficios y su historial de movimientos.',
                ],
              },
              {
                text: '**Pedidos:**',
                items: [
                  'lo que pides;',
                  'las notas para cocina y las alergias que indiques;',
                  'la mesa;',
                  'para domicilios, dirección y teléfono;',
                  'propina, pagos y devoluciones.',
                ],
              },
              {
                text: '**Reservas:**',
                items: [
                  'nombre, teléfono y correo;',
                  'número de personas, fecha y hora, notas;',
                  'anticipo y su estado.',
                ],
              },
              {
                text: '**Pagos en línea:**',
                items: [
                  'el monto, el medio de pago, el estado y la referencia de la transacción;',
                  'para tarjeta, solo su franquicia (Visa, Mastercard o American Express).',
                ],
              },
              {
                text: '**Facturación electrónica:** los datos de comprador que pidas incluir en la factura:',
                items: [
                  'nombre o razón social;',
                  'tipo y número de documento;',
                  'correo, dirección y ciudad.',
                ],
              },
              '**Conversaciones con el asistente:** los mensajes que escribes en el chat del menú o por WhatsApp, las respuestas del asistente y los platos que te propuso.',
              {
                text: '**WhatsApp**, cuando el restaurante conecta su número a Waiter:',
                items: [
                  'tu número de WhatsApp y el nombre de tu perfil;',
                  'el contenido de los mensajes que envías al restaurante y los que el restaurante o su asistente te envían;',
                  'la fecha y hora de cada mensaje y su estado (enviado, entregado, leído).',
                ],
              },
            ],
          },
          { h3: '3.2 Personal de los restaurantes' },
          {
            ul: [
              'Nombre, usuario, correo, rol y locales asignados.',
              'Horario de turno y registro de entrada y salida, para calcular horas trabajadas.',
              'Valor de la hora, si el dueño lo registra.',
              'Las ventas y propinas de los pedidos que registra.',
              'Las acciones que realiza en el sistema (historial de cambios).',
              'Contraseña cifrada con un algoritmo de un solo sentido.',
            ],
          },
          { p: 'No guardamos tu ubicación ni tu dirección IP al entrar.' },
          { h3: '3.3 Dueños de restaurantes y equipo de ProjectApp' },
          {
            ul: [
              'Datos de contacto y facturación de la empresa.',
              'Usuarios y contraseñas cifradas.',
              'Segundo factor de autenticación.',
              'Registros de acceso y de las acciones de soporte.',
            ],
          },
          { h3: '3.4 Visitantes de projectapp.co' },
          { ul: ['Los datos que nos envíes por el formulario o por correo.'] },
        ],
      },
      {
        id: 'datos-que-no-tratamos',
        title: '4. Qué datos NO tratamos',
        blocks: [
          {
            ul: [
              '**No recibimos ni guardamos el número de tu tarjeta.** Lo envías directamente a la pasarela de pagos (Wompi), que nos devuelve un código que no sirve para cobrar en otro lugar.',
              'No usamos herramientas de analítica ni publicidad para rastrearte en el menú ni en el punto de venta.',
              'No vendemos ni alquilamos datos personales.',
              'No usamos los mensajes de WhatsApp ni las conversaciones con el asistente para publicidad, ni para entrenar modelos de inteligencia artificial.',
              '**Tu ubicación no se envía a nuestros servidores.** Si permites usarla en el menú digital, se usa solo en tu celular para mostrar la distancia al restaurante.',
            ],
          },
        ],
      },
      {
        id: 'finalidades',
        title: '5. Para qué usamos los datos',
        blocks: [
          {
            ul: [
              {
                text: 'Prestar el servicio de Waiter al restaurante:',
                items: [
                  'tomar, preparar, cobrar y entregar pedidos;',
                  'administrar reservas, clientes, puntos y beneficios;',
                  'facturar;',
                  'llevar caja e inventario;',
                  'generar reportes.',
                ],
              },
              'Atenderte por el menú digital y por WhatsApp con el asistente. El asistente responde sobre la carta, recomienda y arma pedidos que solo se envían a la cocina cuando tú los confirmas.',
              'Procesar pagos en línea y anticipos de reservas.',
              'Enviarte por correo lo que pediste: confirmaciones de reserva, documentos de venta, códigos para recuperar tu contraseña.',
              'Enviarte novedades y promociones del restaurante, **solo si lo aceptaste**. Puedes retirar tu aceptación cuando quieras.',
              'Calcular horas trabajadas, ventas y propinas del personal, como base para la nómina del restaurante.',
              {
                text: 'Seguridad:',
                items: [
                  'evitar accesos indebidos y fraudes;',
                  'limitar intentos de inicio de sesión;',
                  'dejar constancia de quién cambió qué.',
                ],
              },
              'Dar soporte técnico al restaurante. Solo entramos a la cuenta del restaurante con su permiso expreso, por un tiempo limitado, y queda registrado.',
              'Cumplir obligaciones legales, contables y tributarias.',
            ],
          },
        ],
      },
      {
        id: 'inteligencia-artificial',
        title: '6. Inteligencia artificial',
        blocks: [
          { p: 'El asistente de Waiter usa un modelo de lenguaje de **OpenAI** para entender tu mensaje y proponer una respuesta.' },
          { p: '**Qué le enviamos a OpenAI:**' },
          {
            ul: [
              'el texto que escribes;',
              'los últimos mensajes de la conversación;',
              'la carta del restaurante (platos, descripciones, ingredientes y precios).',
            ],
          },
          { p: '**Qué NO le enviamos:** tu nombre, tu correo ni tu teléfono. Pedimos a OpenAI que no guarde las solicitudes, y sus condiciones para clientes de su API indican que no usa estos datos para entrenar sus modelos.' },
          { p: '**Por eso te pedimos** no escribir en el chat datos sensibles que no sean necesarios para tu pedido. Las alergias déjalas en el campo de alergias de tu pedido o de tu cuenta: así llegan a la cocina.' },
          { p: '**Límites del asistente:** no puede cobrar, ni dar descuentos, ni cambiar precios, ni confirmar pedidos por su cuenta. Los precios y totales los calcula el sistema del restaurante.' },
        ],
      },
      {
        id: 'whatsapp',
        title: '7. WhatsApp',
        blocks: [
          { p: 'Cuando un restaurante conecta su número de WhatsApp Business a Waiter, usamos la plataforma oficial de Meta (WhatsApp Business Platform).' },
          { p: '**Al escribirle al restaurante, Meta nos entrega:**' },
          { ul: ['tu número;', 'el nombre de tu perfil;', 'tus mensajes;', 'el estado de entrega de los mensajes.'] },
          { p: '**Solo los usamos para:**' },
          {
            ul: [
              'que el restaurante y su asistente te respondan;',
              'registrar tus pedidos y reservas;',
              'enviarte avisos sobre ellos, por ejemplo «tu pedido está listo».',
            ],
          },
          { p: '**Lo que no hacemos:**' },
          {
            ul: [
              'no te enviamos mensajes promocionales por WhatsApp sin tu aceptación;',
              'no compartimos tu número ni tus mensajes con otros restaurantes.',
            ],
          },
          { p: '**Puedes escribir «humano»** o pedir hablar con una persona en cualquier momento. También puedes bloquear el número del restaurante, y dejarás de recibir mensajes.' },
          { p: 'Meta trata los datos según sus propias políticas, que puedes consultar en [whatsapp.com/legal](https://www.whatsapp.com/legal).' },
        ],
      },
      {
        id: 'con-quien-compartimos',
        title: '8. Con quién compartimos datos',
        blocks: [
          { p: 'Solo con quienes necesitamos para prestar el servicio, y con contratos que los obligan a protegerlos:' },
          {
            table: {
              head: ['Quién', 'Para qué', 'Dónde'],
              rows: [
                ['El restaurante que usas', 'Es el responsable de tus datos: prepara tu pedido, te atiende, te factura', 'Colombia'],
                ['Meta Platforms (WhatsApp Business Platform)', 'Enviar y recibir los mensajes de WhatsApp del restaurante', 'Estados Unidos y otros países'],
                ['OpenAI', 'Modelo de lenguaje del asistente (ver punto 6)', 'Estados Unidos'],
                ['Wompi (Bancolombia)', 'Procesar pagos en línea y anticipos', 'Colombia'],
                ['Amazon Web Services (AWS)', 'Alojar Waiter y sus bases de datos', 'Estados Unidos'],
                ['Google (Google Workspace)', 'Enviar correos del servicio', 'Estados Unidos'],
                ['DIAN y el sistema de facturación electrónica del restaurante', 'Validar las facturas electrónicas, cuando el restaurante factura', 'Colombia'],
                ['Google', 'Fuentes tipográficas de las pantallas y los enlaces «Cómo llegar» de Google Maps (Google recibe tu dirección IP al cargarlas)', 'Estados Unidos'],
                ['Autoridades', 'Cuando una ley o una orden judicial lo exija', 'Colombia'],
              ],
            },
          },
          { p: 'Algunos de estos proveedores están fuera de Colombia. En esos casos hacemos una **transmisión internacional** a encargados que deben tratar los datos solo según nuestras instrucciones y con medidas de seguridad equivalentes.' },
        ],
      },
      {
        id: 'conservacion',
        title: '9. Cuánto tiempo guardamos los datos',
        blocks: [
          {
            table: {
              head: ['Datos', 'Tiempo'],
              rows: [
                ['Cuenta del comensal', 'Hasta que pidas eliminarla o hasta 24 meses sin uso'],
                ['Conversaciones con el asistente (menú y WhatsApp)', '90 días desde el último mensaje; puedes borrar la del menú en cualquier momento desde el chat'],
                ['Pedidos, pagos, documentos de venta y reservas', 'El tiempo que exigen las normas contables y tributarias (hasta 10 años); los datos de contacto que no sean necesarios para esa obligación se anonimizan a los 24 meses'],
                ['Clientes registrados por el restaurante', 'Mientras el restaurante sea cliente de Waiter y lo necesite, o hasta que pidas su eliminación'],
                ['Personal del restaurante', 'Mientras la persona trabaje en el restaurante y hasta 5 años después, para soportes de nómina y horas'],
                ['Historial de cambios y registros de seguridad', '2 años'],
                ['Cookies de sesión', 'Hasta 12 horas en el menú; hasta el fin del turno en el punto de venta'],
                ['Cuando un restaurante deja Waiter', 'Le entregamos sus datos si los pide y los eliminamos a los 90 días, salvo lo que la ley obligue a conservar'],
              ],
            },
          },
        ],
      },
      {
        id: 'derechos',
        title: '10. Tus derechos',
        blocks: [
          { p: 'Según la Ley 1581 de 2012, puedes:' },
          {
            ul: [
              '**conocer, actualizar y rectificar** tus datos;',
              '**pedir prueba** de la autorización que diste;',
              '**saber cómo se han usado**;',
              '**revocar** la autorización y **pedir que se eliminen**, cuando no haya un deber legal o contractual de conservarlos;',
              '**acceder gratis** a tus datos;',
              '**presentar quejas** ante la Superintendencia de Industria y Comercio (SIC) después de agotar el trámite con nosotros o con el restaurante.',
            ],
          },
          { p: `**Cómo ejercerlos:** escribe a ${MAIL} indicando:` },
          {
            ul: [
              'tu nombre;',
              'el restaurante;',
              'el dato de contacto con el que usaste Waiter (correo o número de WhatsApp);',
              'lo que pides.',
            ],
          },
          { p: 'Si eres cliente de un restaurante, también puedes pedirlo directamente al restaurante.' },
          { p: '**Plazos de respuesta:**' },
          {
            ul: [
              '**consultas:** 10 días hábiles, prorrogables por 5 más;',
              '**reclamos** (corrección, actualización, supresión o revocatoria): 15 días hábiles, prorrogables por 8 más.',
            ],
          },
          { p: 'Te avisaremos si necesitamos la prórroga.' },
          { p: '**Eliminación de datos:** el paso a paso está en [projectapp.co/waiter/data-deletion](/waiter/data-deletion).' },
        ],
      },
      {
        id: 'seguridad',
        title: '11. Seguridad',
        blocks: [
          {
            ul: [
              'Comunicación cifrada (HTTPS).',
              'Contraseñas guardadas con algoritmos de un solo sentido, y códigos y sesiones guardados como huellas criptográficas.',
              'Credenciales de pasarelas de pago cifradas.',
              'Separación estricta de la información de cada restaurante.',
              'Segundo factor obligatorio para el equipo de ProjectApp.',
              'Acceso de soporte solo con permiso del restaurante, por tiempo limitado y registrado.',
            ],
          },
          { p: 'Si ocurre un incidente que afecte tus datos, lo informaremos al restaurante, a la SIC y a ti cuando la ley lo exija.' },
        ],
      },
      {
        id: 'cookies',
        title: '12. Cookies y almacenamiento en tu dispositivo',
        blocks: [
          { p: '**En el menú digital:**' },
          {
            ul: [
              'una **cookie de sesión** (`waiter_diner`, hasta 12 horas) que te identifica en la mesa;',
              'una cookie que recuerda que ya viste la presentación del restaurante (1 año);',
              'en tu navegador, tus preferencias del menú, que puedes borrar desde el mismo menú.',
            ],
          },
          { p: '**En el punto de venta:**' },
          {
            ul: [
              'cookies de sesión del personal;',
              'en el dispositivo del restaurante, una copia temporal de la información de trabajo, para seguir operando sin internet.',
            ],
          },
          { p: 'En Waiter no usamos cookies de publicidad ni de analítica.' },
        ],
      },
      {
        id: 'menores',
        title: '13. Menores de edad',
        blocks: [
          { p: 'Waiter no está dirigido a menores de edad. Si un menor usa el menú de un restaurante, debe hacerlo con autorización de su representante legal, y sus datos se tratan respetando su interés superior.' },
        ],
      },
      {
        id: 'cambios',
        title: '14. Cambios a esta política',
        blocks: [
          { p: 'Si la cambiamos, publicaremos la nueva versión aquí con su fecha. Si el cambio es importante, avisaremos a los restaurantes y, cuando corresponda, a ti.' },
        ],
      },
      {
        id: 'contacto',
        title: '15. Contacto',
        blocks: [
          { p: `${MAIL} · ${PHONE} · ${ADDRESS}.` },
        ],
      },
    ],
  },

  terms: {
    title: 'Condiciones del servicio de Waiter',
    last_updated: UPDATED,
    notice: 'Estas condiciones resumen el contrato con los restaurantes y las reglas de uso de las funciones que ven sus clientes. El contrato comercial firmado con cada restaurante prevalece.',
    sections: [
      {
        id: 'servicio',
        title: '1. El servicio',
        blocks: [
          { p: `Waiter es un software en la nube de ProjectApp (${L.tradeName}, establecimiento de comercio de ${L.owner}, NIT ${L.nit}) que los restaurantes contratan por suscripción. Incluye:` },
          {
            ul: [
              'punto de venta, salón, cocina, inventario, reservas;',
              'clientes y puntos, facturación, reportes y consola del dueño;',
              'menú digital, pagos en línea y el asistente del menú y de WhatsApp.',
            ],
          },
          { p: 'Los módulos dependen del plan contratado.' },
        ],
      },
      {
        id: 'cuentas',
        title: '2. Cuentas y seguridad',
        blocks: [
          { p: 'El restaurante es responsable de:' },
          {
            ul: [
              'las cuentas de su personal, de mantener sus contraseñas en reserva y de desactivar a quien deje de trabajar con él;',
              'la exactitud de su carta, sus precios, sus impuestos y sus datos fiscales.',
            ],
          },
        ],
      },
      {
        id: 'uso-aceptable',
        title: '3. Uso aceptable',
        blocks: [
          { p: 'No se permite usar Waiter para:' },
          {
            ul: [
              'actividades ilegales;',
              'enviar mensajes no solicitados o masivos (spam);',
              'suplantar a otros;',
              'vulnerar la seguridad del servicio;',
              'tratar datos personales sin autorización de sus titulares.',
            ],
          },
        ],
      },
      {
        id: 'whatsapp',
        title: '4. WhatsApp',
        blocks: [
          { p: 'Al conectar su número, el restaurante:' },
          {
            ul: [
              'autoriza a Waiter a enviar y recibir mensajes de WhatsApp en su nombre;',
              {
                text: 'se obliga a cumplir las [políticas de WhatsApp Business](https://business.whatsapp.com/policy), en especial:',
                items: [
                  'contar con la aceptación de sus clientes para recibir mensajes;',
                  'usar plantillas aprobadas fuera de la ventana de atención;',
                  'atender las solicitudes de dejar de recibir mensajes.',
                ],
              },
            ],
          },
          { p: '**Costos:** los cargos que Meta cobra por los mensajes los paga el restaurante directamente a Meta, salvo que el plan diga otra cosa.' },
          { p: '**Desconexión:** el restaurante puede desconectar su número en cualquier momento.' },
        ],
      },
      {
        id: 'asistente',
        title: '5. Asistente de inteligencia artificial',
        blocks: [
          { p: 'El asistente propone respuestas y pedidos con base en la carta del restaurante:' },
          {
            ul: [
              'puede equivocarse;',
              'no cobra, no da descuentos ni cambia precios;',
              'los pedidos solo se envían a la cocina con la confirmación del cliente;',
              'los precios y totales los calcula el sistema.',
            ],
          },
          { p: 'El restaurante debe revisar la información de su carta (ingredientes y alérgenos) y atender por medio de una persona cuando el cliente lo pida.' },
        ],
      },
      {
        id: 'datos',
        title: '6. Datos',
        blocks: [
          {
            ul: [
              'El restaurante es el responsable de los datos de sus clientes y de su personal; ProjectApp los trata como encargado según la [política de privacidad](/waiter/privacy).',
              'El restaurante puede exportar su información y pedir su eliminación al terminar el servicio.',
            ],
          },
        ],
      },
      {
        id: 'pagos',
        title: '7. Pagos',
        blocks: [
          {
            ul: [
              'La suscripción se factura mensualmente según el plan y la lista de precios vigentes.',
              'El consumo por uso se cobra en la cuenta del mes siguiente (por ejemplo, pedidos del asistente de WhatsApp o mensajes del asistente del menú).',
              'La mora puede llevar a la suspensión del servicio, con aviso previo.',
              'Las comisiones de las pasarelas de pago las cobra cada pasarela.',
            ],
          },
        ],
      },
      {
        id: 'disponibilidad',
        title: '8. Disponibilidad y soporte',
        blocks: [
          {
            ul: [
              'Hacemos esfuerzos razonables para que Waiter esté disponible.',
              'El punto de venta sigue funcionando sin internet en las operaciones básicas, y la información se sincroniza al volver la conexión.',
              'Las caídas de terceros (DIAN, Meta, pasarelas, proveedores de internet) no dependen de ProjectApp.',
              `El soporte se presta por correo (${MAIL}) y por teléfono y WhatsApp (${PHONE}), de ${HOURS}.`,
            ],
          },
        ],
      },
      {
        id: 'responsabilidad',
        title: '9. Responsabilidad',
        blocks: [
          { p: 'ProjectApp responde por la prestación diligente del servicio, hasta el valor pagado por el restaurante en los 3 meses anteriores al hecho, salvo dolo o culpa grave. No responde por decisiones del restaurante, información cargada por él, ni fallas de terceros.' },
        ],
      },
      {
        id: 'terminacion',
        title: '10. Terminación',
        blocks: [
          { p: 'El restaurante puede cancelar con 30 días de aviso. ProjectApp puede suspender o terminar el servicio por incumplimiento de estas condiciones o por mora.' },
        ],
      },
      {
        id: 'ley-y-contacto',
        title: '11. Ley y contacto',
        blocks: [
          { p: 'Se rigen por la ley de Colombia.' },
          { p: `Contacto: ${MAIL} · ${PHONE}.` },
        ],
      },
    ],
  },

  data_deletion: {
    title: 'Cómo pedir la eliminación de tus datos',
    last_updated: UPDATED,
    sections: [
      {
        id: 'comensales',
        title: 'Si usaste Waiter como cliente de un restaurante',
        blocks: [
          { p: 'Aplica si usaste el menú digital, hiciste reservas o le escribiste a un restaurante por WhatsApp.' },
          {
            ol: [
              `Escribe a ${MAIL} con el asunto **«Eliminar mis datos»**.`,
              {
                text: 'Indica:',
                items: [
                  'el nombre del restaurante;',
                  'el correo o el número de WhatsApp con el que lo usaste;',
                  'si quieres eliminar todo o solo algo, por ejemplo la conversación con el asistente.',
                ],
              },
              'Te pediremos confirmar que eres tú con un código enviado a ese mismo correo o número.',
              {
                text: 'En un plazo máximo de **15 días hábiles** eliminamos o anonimizamos:',
                items: [
                  'tu cuenta del menú;',
                  'tus conversaciones con el asistente y por WhatsApp;',
                  'tus datos de contacto en los clientes del restaurante;',
                  'tus favoritos y preferencias.',
                ],
              },
              'Te enviamos una confirmación con un código de solicitud.',
            ],
          },
          { p: '**Lo que conservamos por obligación legal:** los pedidos, pagos y facturas que la ley obliga a guardar, sin tu nombre ni tus datos de contacto cuando eso sea posible.' },
        ],
      },
      {
        id: 'whatsapp',
        title: 'Si dejaste de escribirle a un restaurante por WhatsApp',
        blocks: [
          {
            ul: [
              'puedes bloquear su número en WhatsApp para no recibir más mensajes;',
              'para borrar lo que ya enviaste, sigue los pasos de arriba.',
            ],
          },
        ],
      },
      {
        id: 'restaurantes',
        title: 'Si eres un restaurante',
        blocks: [
          { p: `Puedes desconectar WhatsApp desde tu consola de Waiter y pedir la eliminación de la información de tu cuenta escribiendo a ${MAIL}.` },
        ],
      },
      {
        id: 'dudas',
        title: '¿Dudas?',
        blocks: [
          { p: `${MAIL} · ${PHONE}. Consulta también la [política de privacidad de Waiter](/waiter/privacy).` },
        ],
      },
    ],
  },
}
