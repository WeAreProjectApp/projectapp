#!/usr/bin/env python3
"""Imprime los archivos de test que le tocan a un shard del backend.

Reparte por DURACION MEDIDA, no por cantidad de tests ni por directorio. La
medicion del 31-ago-2026 sobre 381 archivos mostro por que importa:
`content/tests/services` concentra el 29% de los tests y solo el 9% del tiempo,
mientras `accounts/tests` tiene el 18% de los tests y el 43% del tiempo. Repartir
por conteo — o por dominio de negocio, que sigue al conteo — arma shards
desbalanceados 3 a 1 y el mas lento marca el wall clock igual.

Los pesos viven en `backend/ci-shard-weights.json`, que genera
`backend-shard-plan.py --emit-weights` a partir del junit que el CI ya sube. Un
archivo nuevo, sin peso registrado, entra con la mediana: no puede quedar afuera.

Uso (desde `backend/`):
    pytest $(python3 ../scripts/ci/backend-shard-files.py --shard 1/4)

Garantia de completitud: el reparto se hace sobre TODOS los archivos que
encuentra el descubrimiento, y cada uno cae en exactamente un shard. Con
`--check` se verifica que la union de los N shards sea la coleccion entera.
"""
from __future__ import annotations

import argparse
import json
import statistics
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[2] / 'backend'
WEIGHTS = BACKEND / 'ci-shard-weights.json'

# Los cuatro roots de tests. `backend/tests/` y `backend/projectapp/tests/` son
# faciles de olvidar — el propio test-quality-gate del repo los omitio y reporto
# 379 archivos en vez de 381. Listarlos aca es lo que hace ese olvido imposible.
ROOTS = ('accounts/tests', 'content/tests', 'tests', 'projectapp/tests', 'monitoring/tests', 'secure_links/tests')


def discover() -> list[str]:
    """Todos los archivos de test, en orden estable.

    Se descubre por glob y no con `pytest --collect-only` a proposito: importar
    la suite entera para repartirla costaria mas que varios shards, y el criterio
    de `python_files = test_*.py` de pytest.ini es exactamente este glob.
    """
    found: set[str] = set()
    for root in ROOTS:
        base = BACKEND / root
        if not base.is_dir():
            continue
        for path in base.rglob('test_*.py'):
            found.add(path.relative_to(BACKEND).as_posix())
    return sorted(found)


def assign(files: list[str], count: int, weights: dict[str, float]) -> list[list[str]]:
    """Bin-packing greedy: el archivo mas pesado va al shard mas liviano.

    Longest-processing-time-first. Con una distribucion plana como esta (el
    archivo mas lento son 1.8 min de 45) queda a pocos puntos del optimo, y no
    necesita ninguna dependencia.
    """
    default = statistics.median(weights.values()) if weights else 1.0
    bins: list[list[str]] = [[] for _ in range(count)]
    loads = [0.0] * count
    for path in sorted(files, key=lambda f: (-weights.get(f, default), f)):
        target = loads.index(min(loads))
        bins[target].append(path)
        loads[target] += weights.get(path, default)
    return [sorted(b) for b in bins]


def parse_shard(raw: str) -> tuple[int, int]:
    try:
        index, count = raw.split('/', 1)
        return int(index), int(count)
    except ValueError:
        raise SystemExit(f'ERROR: --shard espera "i/N", recibi {raw!r}')


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--shard', help='"i/N", 1-indexado, como la matriz del CI')
    parser.add_argument('--weights', type=Path, default=WEIGHTS)
    parser.add_argument('--check', type=int, metavar='N',
                        help='verificar que N shards cubran la coleccion entera')
    parser.add_argument('--summary', type=int, metavar='N',
                        help='mostrar el reparto de N shards, con su peso')
    args = parser.parse_args()

    weights: dict[str, float] = {}
    if args.weights.exists():
        weights = json.loads(args.weights.read_text(encoding='utf-8'))
    elif args.shard:
        # Sin pesos el reparto sigue siendo correcto (todos pesan igual), solo
        # deja de estar balanceado. Se avisa por stderr para no ensuciar la
        # lista de archivos que consume pytest.
        print(f'AVISO: no existe {args.weights}; reparto sin balancear.',
              file=sys.stderr)

    files = discover()
    if not files:
        print('ERROR: no se encontro ningun test.', file=sys.stderr)
        return 2

    if args.check:
        bins = assign(files, args.check, weights)
        union: list[str] = []
        for b in bins:
            union.extend(b)
        missing = set(files) - set(union)
        dupes = len(union) - len(set(union))
        print(f'archivos descubiertos: {len(files)}')
        print(f'archivos repartidos:   {len(union)} en {args.check} shards')
        if missing or dupes:
            print(f'ROTO: {len(missing)} sin asignar, {dupes} duplicados',
                  file=sys.stderr)
            for path in sorted(missing)[:10]:
                print(f'  falta: {path}', file=sys.stderr)
            return 1
        print('OK: cada archivo cae en exactamente un shard.')
        return 0

    if args.summary:
        bins = assign(files, args.summary, weights)
        default = statistics.median(weights.values()) if weights else 1.0
        total = sum(weights.get(f, default) for f in files)
        mean = total / args.summary
        for i, b in enumerate(bins, 1):
            load = sum(weights.get(f, default) for f in b)
            skew = (load - mean) / mean * 100 if mean else 0.0
            top = max(b, key=lambda f: weights.get(f, default)) if b else '—'
            print(f'  {i}/{args.summary}  {load / 60:5.2f} min  '
                  f'{len(b):3d} archivos  {skew:+5.1f}%   mayor: {Path(top).name}')
        print(f'\nwall clock proyectado: '
              f'{max(sum(weights.get(f, default) for f in b) for b in bins) / 60:.2f} min')
        return 0

    if not args.shard:
        raise SystemExit('ERROR: pasa --shard i/N, --check N o --summary N')

    index, count = parse_shard(args.shard)
    if not 1 <= index <= count:
        raise SystemExit(f'ERROR: shard {index} fuera de rango 1..{count}')
    print(' '.join(assign(files, count, weights)[index - 1]))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
