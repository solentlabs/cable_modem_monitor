***REMOVED***!/usr/bin/env python3
"""
Cable Modem Monitor - Entity Cleanup Utility

This script helps clean up orphaned entities that may accumulate during
upgrades from v1.x to v2.0 or after multiple integration reinstalls.

IMPORTANT: This script must be run on your Home Assistant server.

Usage:
  1. Copy this script to your Home Assistant server
  2. Run: python3 cleanup_entities.py --check
  3. Review the status report
  4. Run: python3 cleanup_entities.py --cleanup (to remove orphans)
     OR: python3 cleanup_entities.py --nuclear (to start completely fresh)
"""
import json
import sys
import os
import argparse
from datetime import datetime
from pathlib import Path

ENTITY_REGISTRY_PATH = Path("/config/.storage/core.entity_registry")
BACKUP_DIR = Path("/config/.storage")


class Colors:
    """ANSI color codes for terminal output."""
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
    """Print a formatted header."""
    print(f"\n{Colors.BOLD}{Colors.HEADER}{'=' * 70}{Colors.ENDC}")
    print(f"{Colors.BOLD}{Colors.HEADER}{text:^70}{Colors.ENDC}")
    print(f"{Colors.BOLD}{Colors.HEADER}{'=' * 70}{Colors.ENDC}\n")


def print_success(text):
    """Print success message."""
    print(f"{Colors.OKGREEN}✓ {text}{Colors.ENDC}")


def print_warning(text):
    """Print warning message."""
    print(f"{Colors.WARNING}⚠ {text}{Colors.ENDC}")


def print_error(text):
    """Print error message."""
    print(f"{Colors.FAIL}✗ {text}{Colors.ENDC}")


def print_info(text):
    """Print info message."""
    print(f"{Colors.OKCYAN}ℹ {text}{Colors.ENDC}")


def load_entity_registry():
    """Load the entity registry."""
    if not ENTITY_REGISTRY_PATH.exists():
        print_error(f"Entity registry not found at {ENTITY_REGISTRY_PATH}")
        print_error("Make sure you're running this on your Home Assistant server!")
        sys.exit(1)

    with open(ENTITY_REGISTRY_PATH, 'r') as f:
        return json.load(f)


def backup_entity_registry():
    """Create a backup of the entity registry."""
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    backup_path = BACKUP_DIR / f"core.entity_registry.backup-{timestamp}"

    with open(ENTITY_REGISTRY_PATH, 'r') as src:
        with open(backup_path, 'w') as dst:
            dst.write(src.read())

    return backup_path


def analyze_entities(data):
    """Analyze cable modem entities."""
    all_entities = data['data']['entities']

    ***REMOVED*** Find all cable modem entities
    cable_modem_entities = [
        e for e in all_entities
        if 'cable_modem' in e.get('unique_id', '').lower() or
           e.get('platform') == 'cable_modem_monitor'
    ]

    ***REMOVED*** Categorize entities
    active = [e for e in cable_modem_entities if e.get('config_entry_id')]
    orphaned = [
        e for e in cable_modem_entities
        if not e.get('config_entry_id') or e.get('orphaned_timestamp')
    ]

    ***REMOVED*** Group by creation date
    creation_dates = {}
    for entity in cable_modem_entities:
        created = entity.get('created_at', 'unknown')[:10]
        if created not in creation_dates:
            creation_dates[created] = {'active': 0, 'orphaned': 0}
        if entity in active:
            creation_dates[created]['active'] += 1
        else:
            creation_dates[created]['orphaned'] += 1

    return {
        'total_entities': len(all_entities),
        'cable_modem_total': len(cable_modem_entities),
        'active': active,
        'orphaned': orphaned,
        'creation_dates': creation_dates
    }


def print_status(stats):
    """Print detailed status report."""
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

    ***REMOVED*** Show sample of orphaned entities
    print(f"\n{Colors.BOLD}Sample Orphaned Entities (first 10):{Colors.ENDC}")
    for i, entity in enumerate(stats['orphaned'][:10], 1):
        entity_id = entity.get('entity_id', 'unknown')
        created = entity.get('created_at', 'unknown')[:10]
        print(f"  {i:2d}. {entity_id} (created: {created})")

    if len(stats['orphaned']) > 10:
        print(f"  ... and {len(stats['orphaned']) - 10} more")

    ***REMOVED*** Calculate disk space impact
    avg_entity_size = 500  ***REMOVED*** bytes per entity (rough estimate)
    orphaned_size_kb = (len(stats['orphaned']) * avg_entity_size) / 1024
    print_info(f"\nEstimated disk space wasted by orphans: ~{orphaned_size_kb:.1f} KB")

    print(f"\n{Colors.BOLD}Recommendations:{Colors.ENDC}")
    if len(stats['orphaned']) > 50:
        print_warning(f"You have {len(stats['orphaned'])} orphaned entities - cleanup recommended!")
        print("  Run: python3 cleanup_entities.py --cleanup")
    elif len(stats['orphaned']) > 0:
        print_info(f"You have {len(stats['orphaned'])} orphaned entities - cleanup optional")
        print("  Run: python3 cleanup_entities.py --cleanup")


def cleanup_orphans(data, dry_run=False):
    """Remove orphaned cable modem entities."""
    print_header("Cleaning Up Orphaned Entities")

    if not dry_run:
        ***REMOVED*** Create backup
        print_info("Creating backup...")
        backup_path = backup_entity_registry()
        print_success(f"Backup created: {backup_path}")

    ***REMOVED*** Analyze
    stats = analyze_entities(data)

    if len(stats['orphaned']) == 0:
        print_success("No orphaned entities to clean up!")
        return data

    print(f"\n{Colors.BOLD}Removing {len(stats['orphaned'])} orphaned entities...{Colors.ENDC}")

    ***REMOVED*** Remove orphaned entities
    all_entities = data['data']['entities']
    entities_to_keep = [e for e in all_entities if e not in stats['orphaned']]

    print(f"  Before: {len(all_entities)} total entities")
    print(f"  After:  {len(entities_to_keep)} total entities")
    print(f"  Removed: {len(all_entities) - len(entities_to_keep)} entities")

    if dry_run:
        print_warning("\n[DRY RUN] No changes made. Use --cleanup to actually remove orphans.")
        return data

    ***REMOVED*** Update data
    data['data']['entities'] = entities_to_keep

    ***REMOVED*** Save
    print_info("\nSaving changes...")
    with open(ENTITY_REGISTRY_PATH, 'w') as f:
        json.dump(data, f, indent=2)

    print_success("\n✓ Cleanup complete!")
    return data


def nuclear_option(data):
    """Remove ALL cable modem entities and start fresh."""
    print_header("NUCLEAR OPTION - Complete Reset")
    print_warning("⚠️  This will remove ALL cable modem entities!")
    print_warning("⚠️  You will lose ALL historical data!")
    print_warning("⚠️  The integration will create fresh entities on next restart.")

    response = input(f"\n{Colors.BOLD}Are you ABSOLUTELY sure? Type 'DELETE EVERYTHING' to confirm: {Colors.ENDC}")
    if response != "DELETE EVERYTHING":
        print_error("Cancelled. No changes made.")
        sys.exit(0)

    ***REMOVED*** Create backup
    print_info("\nCreating backup...")
    backup_path = backup_entity_registry()
    print_success(f"Backup created: {backup_path}")

    ***REMOVED*** Analyze
    stats = analyze_entities(data)

    print(f"\n{Colors.BOLD}Removing ALL {stats['cable_modem_total']} cable modem entities...{Colors.ENDC}")

    ***REMOVED*** Remove ALL cable modem entities
    all_entities = data['data']['entities']
    all_cable_modem = stats['active'] + stats['orphaned']
    entities_to_keep = [e for e in all_entities if e not in all_cable_modem]

    print(f"  Before: {len(all_entities)} total entities")
    print(f"  After:  {len(entities_to_keep)} total entities")
    print(f"  Removed: {len(all_entities) - len(entities_to_keep)} entities")

    ***REMOVED*** Update data
    data['data']['entities'] = entities_to_keep

    ***REMOVED*** Save
    print_info("\nSaving changes...")
    with open(ENTITY_REGISTRY_PATH, 'w') as f:
        json.dump(data, f, indent=2)

    print_success("\n✓ Nuclear option complete!")
    print_info("\nNext steps:")
    print("  1. Restart Home Assistant")
    print("  2. The integration will recreate all entities fresh")
    print("  3. Reconfigure any dashboards/automations that reference cable modem entities")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description='Cable Modem Monitor Entity Cleanup Utility',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python3 cleanup_entities.py --check          ***REMOVED*** View status report
  python3 cleanup_entities.py --cleanup        ***REMOVED*** Remove orphaned entities
  python3 cleanup_entities.py --nuclear        ***REMOVED*** Remove ALL entities (fresh start)
  python3 cleanup_entities.py --dry-run        ***REMOVED*** Preview cleanup without making changes

For help, visit: https://github.com/kwschulz/cable_modem_monitor/issues
        """
    )

    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--check', action='store_true', help='Show status report only')
    group.add_argument('--cleanup', action='store_true', help='Remove orphaned entities')
    group.add_argument('--nuclear', action='store_true', help='Remove ALL cable modem entities (fresh start)')
    group.add_argument('--dry-run', action='store_true', help='Preview cleanup without making changes')

    args = parser.parse_args()

    ***REMOVED*** Load data
    try:
        data = load_entity_registry()
    except Exception as e:
        print_error(f"Failed to load entity registry: {e}")
        sys.exit(1)

    ***REMOVED*** Execute requested action
    try:
        if args.check:
            stats = analyze_entities(data)
            print_status(stats)

        elif args.dry_run:
            cleanup_orphans(data, dry_run=True)

        elif args.cleanup:
            cleanup_orphans(data, dry_run=False)
            print_info("\n📋 Next steps:")
            print("   1. Restart Home Assistant (Settings → System → Restart)")
            print("   2. Verify entities look correct")
            print("   3. Old entity_ids may have changed - update dashboards if needed")

        elif args.nuclear:
            nuclear_option(data)
            print_warning("\n⚠️  IMPORTANT: Restart Home Assistant now!")
            print("   After restart, the integration will create fresh entities.")

    except KeyboardInterrupt:
        print_error("\n\nInterrupted by user. No changes made.")
        sys.exit(1)
    except Exception as e:
        print_error(f"\n\nError: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()
