#!/usr/bin/env python3
"""CLI wrapper for cable_modem_monitor entity cleanup.

This script provides a friendly, interactive CLI while delegating the
analysis logic to the integration module at
`custom_components/cable_modem_monitor/utils/entity_cleanup.py`.

Run this on your Home Assistant host (it operates on
/config/.storage/core.entity_registry). The wrapper keeps the original
CLI flags and colored output but centralizes logic in the integration
module so developers can reuse it programmatically.
"""
import argparse
import json
import sys
from pathlib import Path

# Ensure project root is on sys.path so we can import the integration module
PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

try:
    from custom_components.cable_modem_monitor.utils import entity_cleanup as ec
except Exception:
    ec = None


class Colors:
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKCYAN = '\033[96m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'


def print_header(text):
    print(f"\n{Colors.BOLD}{Colors.HEADER}{'=' * 70}{Colors.ENDC}")
    print(f"{Colors.BOLD}{Colors.HEADER}{text:^70}{Colors.ENDC}")
    print(f"{Colors.BOLD}{Colors.HEADER}{'=' * 70}{Colors.ENDC}\n")


def print_success(text):
    print(f"{Colors.OKGREEN}✓ {text}{Colors.ENDC}")


def print_warning(text):
    print(f"{Colors.WARNING}⚠ {text}{Colors.ENDC}")


def print_error(text):
    print(f"{Colors.FAIL}✗ {text}{Colors.ENDC}")


def print_info(text):
    print(f"{Colors.OKCYAN}ℹ {text}{Colors.ENDC}")


def load_entity_registry(path: Path):
    if not path.exists():
        print_error(f"Entity registry not found at {path}")
        print_error("Make sure you're running this on your Home Assistant server!")
        sys.exit(1)
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)


def print_status(stats):
    print_header("Cable Modem Monitor - Entity Status Report")
    print(f"Total entities in Home Assistant: {Colors.BOLD}{stats['total_entities']}{Colors.ENDC}")
    print(f"Cable Modem entities: {Colors.BOLD}{stats['cable_modem_total']}{Colors.ENDC}")
    print(f"  ├─ Active (connected to integration): {Colors.OKGREEN}{len(stats['active'])}{Colors.ENDC}")
    print(f"  └─ Orphaned (leftover from old installs): {Colors.WARNING}{len(stats['orphaned'])}{Colors.ENDC}")

    if len(stats['orphaned']) == 0:
        print_success("\nNo orphaned entities found! Your installation is clean.")
        return

    print(f"\n{Colors.BOLD}Entity History by Date:{Colors.ENDC}")
    for date, counts in sorted(stats['creation_dates'].items()):
        total = counts['active'] + counts['orphaned']
        active_str = f"{Colors.OKGREEN}{counts['active']} active{Colors.ENDC}"
        orphaned_str = f"{Colors.WARNING}{counts['orphaned']} orphaned{Colors.ENDC}"
        print(f"  {date}: {total} total ({active_str}, {orphaned_str})")

    print(f"\n{Colors.BOLD}Sample Orphaned Entities (first 10):{Colors.ENDC}")
    for i, entity in enumerate(stats['orphaned'][:10], 1):
        entity_id = entity.get('entity_id', 'unknown')
        created = entity.get('created_at', 'unknown')[:10]
        print(f"  {i:2d}. {entity_id} (created: {created})")

    if len(stats['orphaned']) > 10:
        print(f"  ... and {len(stats['orphaned']) - 10} more")

    avg_entity_size = 500
    orphaned_size_kb = (len(stats['orphaned']) * avg_entity_size) / 1024
    print_info(f"\nEstimated disk space wasted by orphans: ~{orphaned_size_kb:.1f} KB")


def analyze_entities_fallback(data: dict) -> dict:
    """Perform basic entity analysis when integration module is unavailable."""
    print_warning('Integration module not found; falling back to basic analysis')
    all_entities = data['data']['entities']
    cable_modem_entities = [
        e for e in all_entities
        if 'cable_modem' in e.get('unique_id', '').lower() or e.get('platform') == 'cable_modem_monitor'
    ]
    active = [e for e in cable_modem_entities if e.get('config_entry_id')]
    orphaned = [e for e in cable_modem_entities if not e.get('config_entry_id') or e.get('orphaned_timestamp')]
    creation_dates = {}
    for entity in cable_modem_entities:
        created = entity.get('created_at', 'unknown')[:10]
        creation_dates.setdefault(created, {'active': 0, 'orphaned': 0})
        if entity in active:
            creation_dates[created]['active'] += 1
        else:
            creation_dates[created]['orphaned'] += 1
    return {
        'total_entities': len(all_entities),
        'cable_modem_total': len(cable_modem_entities),
        'active': active,
        'orphaned': orphaned,
        'creation_dates': creation_dates,
    }


def handle_cleanup_operation(data: dict, stats: dict, entity_registry_path: Path):
    """Handle cleanup operation to remove orphaned entities."""
    print_header('Cleaning Up Orphaned Entities')
    if not stats['orphaned']:
        print_success('No orphaned entities to clean up!')
        return

    print_info('Creating backup...')
    if ec is not None:
        backup_path = ec.backup_entity_registry()
        print_success(f'Backup created: {backup_path}')
    else:
        print_warning('Backup skipped because integration module is unavailable')

    all_entities = data['data']['entities']
    entities_to_keep = [e for e in all_entities if e not in stats['orphaned']]
    print(f"  Before: {len(all_entities)} total entities")
    print(f"  After:  {len(entities_to_keep)} total entities")
    print(f"  Removed: {len(all_entities) - len(entities_to_keep)} entities")

    print_info('\nSaving changes...')
    data['data']['entities'] = entities_to_keep
    with open(entity_registry_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2)

    print_success('\n✓ Cleanup complete!')


def handle_nuclear_operation(data: dict, stats: dict, entity_registry_path: Path):
    """Handle nuclear option to remove all cable modem entities."""
    print_header('NUCLEAR OPTION - Complete Reset')
    print_warning('⚠️  This will remove ALL cable modem entities!')
    print_warning('⚠️  You will lose ALL historical data!')
    print_warning('⚠️  The integration will create fresh entities on next restart.')
    response = input(
        f"\n{Colors.BOLD}Are you ABSOLUTELY sure? "
        f"Type 'DELETE EVERYTHING' to confirm: {Colors.ENDC}"
    )
    if response != 'DELETE EVERYTHING':
        print_error('Cancelled. No changes made.')
        sys.exit(0)

    print_info('\nCreating backup...')
    if ec is not None:
        backup_path = ec.backup_entity_registry()
        print_success(f'Backup created: {backup_path}')
    else:
        print_warning('Backup skipped because integration module is unavailable')

    # Recompute stats in case something changed
    if ec is not None:
        stats = ec.analyze_entities(data)
    all_entities = data['data']['entities']
    all_cable_modem = stats['active'] + stats['orphaned']
    entities_to_keep = [e for e in all_entities if e not in all_cable_modem]

    print(f"  Before: {len(all_entities)} total entities")
    print(f"  After:  {len(entities_to_keep)} total entities")
    print(f"  Removed: {len(all_entities) - len(entities_to_keep)} entities")

    print_info('\nSaving changes...')
    data['data']['entities'] = entities_to_keep
    with open(entity_registry_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2)

    print_success('\n✓ Nuclear option complete!')
    print_info('\nNext steps:')
    print('  1. Restart Home Assistant')
    print('  2. The integration will recreate all entities fresh')
    print('  3. Reconfigure any dashboards/automations that reference cable modem entities')


def main():
    parser = argparse.ArgumentParser(
        description='Cable Modem Monitor Entity Cleanup Utility',
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--check', action='store_true', help='Show status report only')
    group.add_argument('--cleanup', action='store_true', help='Remove orphaned entities')
    group.add_argument('--nuclear', action='store_true', help='Remove ALL cable modem entities (fresh start)')
    group.add_argument('--dry-run', action='store_true', help='Preview cleanup without making changes')
    args = parser.parse_args()

    # Determine entity registry path from module if available, else fallback
    entity_registry_path = getattr(ec, 'ENTITY_REGISTRY_PATH', Path('/config/.storage/core.entity_registry'))

    try:
        data = load_entity_registry(entity_registry_path)
    except Exception as e:
        print_error(f"Failed to load entity registry: {e}")
        sys.exit(1)

    try:
        # Use module analysis when available, else fallback
        stats = ec.analyze_entities(data) if ec is not None else analyze_entities_fallback(data)

        if args.check:
            print_status(stats)
        elif args.dry_run:
            print_header('Dry run - no changes will be written')
            print_status(stats)
        elif args.cleanup:
            handle_cleanup_operation(data, stats, entity_registry_path)
        elif args.nuclear:
            handle_nuclear_operation(data, stats, entity_registry_path)

    except KeyboardInterrupt:
        print_error('\n\nInterrupted by user. No changes made.')
        sys.exit(1)
    except Exception as e:
        print_error(f"\n\nError: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()
