"""Read only the public CCE dataset. No portal login or mailbox credentials."""
from datetime import timedelta
from decimal import Decimal, InvalidOperation
from zoneinfo import ZoneInfo

import requests
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from procurement.filters import normalize_unspsc

ENDPOINT = 'https://www.datos.gov.co/resource/p6dx-8zbt.json'
BOGOTA = ZoneInfo('America/Bogota')
PAGE_SIZE = 250


def source_datetime(value):
    if not value:
        return None
    result = parse_datetime(str(value))
    if result is not None and timezone.is_naive(result):
        result = timezone.make_aware(result, BOGOTA)
    return result


def quote(value):
    return "'" + str(value).replace("'", "''") + "'"


class PublicClient:
    def page(self, *, offset=0, since=None, lookback=90, ids=None):
        if ids is not None:
            where = 'id_del_proceso in (' + ','.join(quote(value) for value in ids) + ')'
        elif since:
            # Do not restrict status here: cancellations/awards must update locally.
            where = 'fecha_de_ultima_publicaci >= ' + quote(since)
        else:
            floor = (timezone.now() - timedelta(days=lookback)).date().isoformat()
            where = "estado_del_procedimiento in ('Abierto','Publicado') AND fecha_de_publicacion_del >= " + quote(floor)
        response = requests.get(ENDPOINT, params={
            '$where': where, '$limit': PAGE_SIZE, '$offset': offset,
            '$order': 'id_del_proceso ASC, fecha_de_ultima_publicaci DESC',
        }, timeout=(5, 25))
        response.raise_for_status()
        data = response.json()
        if not isinstance(data, list):
            raise ValueError('Respuesta pública no válida.')
        return data


def normalized_record(record):
    if not isinstance(record, dict):
        raise ValueError('Registro público no válido.')
    source_id = str(record.get('id_del_proceso') or '').strip()
    if not source_id or len(source_id) > 100:
        raise ValueError('Proceso sin identificador válido.')
    fields = {
        'referencia_del_proceso': ('reference', 250), 'nombre_del_procedimiento': ('title', 1000),
        'entidad': ('entity_name', 500), 'nit_entidad': ('entity_nit', 100),
        'departamento_entidad': ('department', 120), 'ciudad_entidad': ('city', 150),
        'modalidad_de_contratacion': ('method', 250), 'tipo_de_contrato': ('contract_type', 150),
        'estado_del_procedimiento': ('source_status', 100),
    }
    data = {target: str(record.get(source) or '')[:limit] for source, (target, limit) in fields.items()}
    data['description'] = str(record.get('descripci_n_del_procedimiento') or '')[:50000]
    data['unspsc_code'] = normalize_unspsc(record.get('codigo_principal_de_categoria'))[:100]
    for source, target in [('fecha_de_publicacion_del', 'published_at'),
                           ('fecha_de_ultima_publicaci', 'source_updated_at'),
                           ('fecha_de_recepcion_de', 'closing_at')]:
        data[target] = source_datetime(record.get(source))
    try:
        amount = Decimal(str(record.get('precio_base', '')))
        data['budget'] = amount if amount.is_finite() and 0 <= amount < Decimal('1e20') else None
    except InvalidOperation:
        data['budget'] = None
    url = record.get('urlproceso') or ''
    url = url.get('url', '') if isinstance(url, dict) else str(url)
    # The only links rendered are official HTTPS portal links.
    from urllib.parse import urlsplit
    parsed = urlsplit(url)
    data['source_url'] = url[:1000] if parsed.scheme == 'https' and parsed.hostname in {
        'community.secop.gov.co', 'www.colombiacompra.gov.co', 'www.contratos.gov.co',
    } else ''
    data['source_data'] = record
    return source_id, data
