#!/usr/bin/env python3
"""Recordatorio automático de partidos de Alianza Lima Vóley.

Uso:
    python sync.py check          # ver los próximos partidos (no toca nada)
    python sync.py ics            # generar docs/alianza-lima.ics
    python sync.py login          # autorizar Google Calendar (una sola vez)
    python sync.py sync           # crear/actualizar eventos en tu calendario
    python sync.py sync --dry-run # simular, sin escribir en el calendario

No necesita instalar nada: usa solo la librería estándar de Python 3.10+.
"""

from __future__ import annotations

import sys

# En Windows la consola usa cp1252 y los emojis/tildes rompen el print.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import argparse
from datetime import datetime, timezone

from voley import auth, config, gcal, ics, service, tz


def _fmt(item) -> str:
    """Línea legible de un partido, en la zona horaria configurada."""
    when = tz.describe_short(item.start)
    return f"  {when}  {item.summary}\n   📍 {item.venue or 'sede por confirmar'}"


def cmd_check(args: argparse.Namespace) -> int:
    print(f"\n🔎 Consultando la FPV para {config.TEAM_NAME} (equipo ID {config.TEAM_ID})...")
    pending, finished = service.load_matches()

    if not pending:
        print("No hay partidos próximos publicados todavía.")
        return 0

    print(f"\n✅ {len(pending)} partido(s) por jugar:\n")
    for item in pending:
        print(_fmt(item))
    if finished and args.verbose:
        print(f"\n   ({len(finished)} partido(s) ya jugados en la ventana consultada)")
    print()
    return 0


def cmd_ics(args: argparse.Namespace) -> int:
    pending, _ = service.load_matches()
    path = ics.write_calendar(pending)
    print(f"✅ Archivo generado: {path}  ({len(pending)} partidos)")
    print("   Ábrelo con Apple Calendar / Outlook, o súbelo a GitHub Pages")
    print("   y suscríbete a la URL desde tu teléfono.")
    return 0


def cmd_login(args: argparse.Namespace) -> int:
    auth.login()
    print("\nSiguiente paso:  python sync.py sync --dry-run")
    return 0


def cmd_sync(args: argparse.Namespace) -> int:
    print(f"\n🔎 Consultando la FPV para {config.TEAM_NAME}...")
    pending, _ = service.load_matches()

    if not pending:
        print("No hay partidos próximos. No se toca el calendario.")
        return 0

    print(f"   {len(pending)} partido(s) próximo(s).\n")
    report = gcal.sync(pending, dry_run=args.dry_run, prune=args.prune)

    print(f"📅 Calendario: {report['calendar']}")
    if args.dry_run:
        print("   (modo simulación: no se escribió nada)\n")

    for label, key, icon in [
        ("Creados", "created", "➕"),
        ("Actualizados", "updated", "✏️ "),
        ("Sin cambios", "unchanged", "✅"),
        ("Borrados", "pruned", "🗑️ "),
    ]:
        items = report[key]
        if items:
            print(f"\n{icon} {label}: {len(items)}")
            for summary in items:
                print(f"   · {summary}")

    if report["errors"]:
        print(f"\n⚠️  Errores: {len(report['errors'])}")
        for error in report["errors"]:
            print(f"   · {error}")
        return 1

    print()
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="sync.py",
        description="Recordatorio en Google Calendar de los partidos de "
                    f"{config.TEAM_NAME} (FPV / LNSV).",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_check = sub.add_parser("check", help="ver los próximos partidos sin escribir nada")
    p_check.add_argument("-v", "--verbose", action="store_true")
    p_check.set_defaults(func=cmd_check)

    p_ics = sub.add_parser("ics", help="generar un archivo .ics con los partidos")
    p_ics.set_defaults(func=cmd_ics)

    p_login = sub.add_parser("login", help="autorizar Google Calendar (una vez)")
    p_login.set_defaults(func=cmd_login)

    p_sync = sub.add_parser("sync", help="crear/actualizar los eventos en el calendario")
    p_sync.add_argument("--dry-run", action="store_true", help="simular sin escribir")
    p_sync.add_argument("--prune", action="store_true",
                        help="borrar eventos de partidos que ya no existen en la FPV")
    p_sync.set_defaults(func=cmd_sync)

    args = parser.parse_args(argv)

    if args.command == "check":
        print(f"FPV: {config.FPV_BASE}")
        print(f"Hoy: {tz.to_display(datetime.now(timezone.utc)).strftime('%Y-%m-%d %H:%M')} "
              f"({tz.display_label()})")

    try:
        return args.func(args)
    except KeyboardInterrupt:
        print("\nCancelado.")
        return 130
    except (auth.AuthError, gcal.CalendarError, service.fpv.FpvError) as error:
        print(f"\n❌ {error}\n")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
