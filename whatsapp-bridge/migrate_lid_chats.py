#!/usr/bin/env python3
"""
One-time migration script: Merge @lid chat records into phone-number equivalents.

This script reads the whatsmeow LID-to-phone mapping from the session database
(whatsapp.db) and updates the messages database (messages.db) to use phone-number
JIDs instead of LID JIDs.

Usage:
    cd whatsapp-bridge
    python3 migrate_lid_chats.py [--dry-run]

The --dry-run flag shows what would be changed without modifying the database.
"""

import sqlite3
import shutil
import sys
import os

STORE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'store')
MESSAGES_DB = os.path.join(STORE_DIR, 'messages.db')
WHATSMEOW_DB = os.path.join(STORE_DIR, 'whatsapp.db')


def get_lid_mappings():
    """Read all LID-to-phone mappings from the whatsmeow session database."""
    conn = sqlite3.connect(WHATSMEOW_DB)
    cursor = conn.cursor()
    cursor.execute("SELECT lid, pn FROM whatsmeow_lid_map")
    mappings = {lid: pn for lid, pn in cursor.fetchall()}
    conn.close()
    return mappings


def get_lid_chats(conn):
    """Find all chats stored under @lid JIDs."""
    cursor = conn.cursor()
    cursor.execute("SELECT jid, name, last_message_time FROM chats WHERE jid LIKE '%@lid'")
    return cursor.fetchall()


def get_lid_messages(conn, lid_jid):
    """Get all messages in a LID-based chat."""
    cursor = conn.cursor()
    cursor.execute("SELECT id, chat_jid, sender FROM messages WHERE chat_jid = ?", (lid_jid,))
    return cursor.fetchall()


def get_lid_senders(conn):
    """Find all messages with LID-based senders."""
    cursor = conn.cursor()
    cursor.execute("SELECT DISTINCT sender FROM messages WHERE sender LIKE '%@lid' OR sender LIKE '%@lid:%'")
    return [row[0] for row in cursor.fetchall()]


def migrate(dry_run=False):
    """Perform the migration."""
    if not os.path.exists(MESSAGES_DB):
        print(f"Error: Messages database not found at {MESSAGES_DB}")
        sys.exit(1)

    if not os.path.exists(WHATSMEOW_DB):
        print(f"Error: WhatsApp session database not found at {WHATSMEOW_DB}")
        sys.exit(1)

    # Load LID mappings
    lid_to_phone = get_lid_mappings()
    print(f"Loaded {len(lid_to_phone)} LID-to-phone mappings from whatsmeow database")

    if not lid_to_phone:
        print("No LID mappings found. Nothing to migrate.")
        return

    # Back up the database before making changes
    if not dry_run:
        backup_path = MESSAGES_DB + '.bak'
        shutil.copy2(MESSAGES_DB, backup_path)
        print(f"Backed up database to {backup_path}")

    conn = sqlite3.connect(MESSAGES_DB)
    conn.execute("PRAGMA foreign_keys = OFF")  # Disable FK constraints during migration

    # Phase 1: Find and migrate LID chats
    lid_chats = get_lid_chats(conn)
    print(f"\nFound {len(lid_chats)} chats with @lid JIDs")

    migrated_chats = 0
    migrated_messages = 0
    migrated_senders = 0
    merged_chats = 0

    cursor = conn.cursor()

    for lid_jid, name, last_message_time in lid_chats:
        lid_user = lid_jid.split('@')[0]
        phone = lid_to_phone.get(lid_user)

        if not phone:
            print(f"  SKIP: No phone mapping for {lid_jid}")
            continue

        pn_jid = f"{phone}@s.whatsapp.net"
        print(f"  {lid_jid} -> {pn_jid} (name: {name})")

        if dry_run:
            migrated_chats += 1
            # Count messages that would be migrated
            messages = get_lid_messages(conn, lid_jid)
            migrated_messages += len(messages)
            continue

        # Check if the phone-number chat already exists
        cursor.execute("SELECT jid, name, last_message_time FROM chats WHERE jid = ?", (pn_jid,))
        existing = cursor.fetchone()

        if existing:
            # Merge: keep the existing phone-number chat, update messages to point to it
            print(f"    MERGE: Phone chat already exists (name: {existing[1]})")

            # Update name if the LID chat had a name and the existing one doesn't
            if name and not existing[1]:
                cursor.execute("UPDATE chats SET name = ? WHERE jid = ?", (name, pn_jid))

            # Keep the more recent last_message_time
            if last_message_time and existing[2]:
                if last_message_time > existing[2]:
                    cursor.execute("UPDATE chats SET last_message_time = ? WHERE jid = ?",
                                   (last_message_time, pn_jid))
            elif last_message_time and not existing[2]:
                cursor.execute("UPDATE chats SET last_message_time = ? WHERE jid = ?",
                               (last_message_time, pn_jid))

            merged_chats += 1
        else:
            # No existing phone chat - simply rename the LID chat
            cursor.execute("INSERT INTO chats (jid, name, last_message_time) VALUES (?, ?, ?)",
                           (pn_jid, name, last_message_time))

        # Migrate messages: update chat_jid from LID to phone number
        # Handle potential message ID conflicts by using INSERT OR IGNORE + DELETE pattern
        cursor.execute("""
            UPDATE messages SET chat_jid = ?
            WHERE chat_jid = ?
            AND id NOT IN (SELECT id FROM messages WHERE chat_jid = ?)
        """, (pn_jid, lid_jid, pn_jid))
        moved = cursor.rowcount

        # Log and delete any remaining messages under the old LID JID (duplicates)
        cursor.execute("SELECT id, sender, timestamp FROM messages WHERE chat_jid = ?", (lid_jid,))
        dupe_rows = cursor.fetchall()
        dupes = len(dupe_rows)
        for dupe_id, dupe_sender, dupe_ts in dupe_rows:
            print(f"    DUPE DROPPED: msg_id={dupe_id} sender={dupe_sender} ts={dupe_ts}")
        if dupes > 0:
            cursor.execute("DELETE FROM messages WHERE chat_jid = ?", (lid_jid,))

        # Migrate chat_labels
        cursor.execute("""
            UPDATE OR IGNORE chat_labels SET chat_jid = ? WHERE chat_jid = ?
        """, (pn_jid, lid_jid))
        cursor.execute("DELETE FROM chat_labels WHERE chat_jid = ?", (lid_jid,))

        # Remove the old LID chat entry
        cursor.execute("DELETE FROM chats WHERE jid = ?", (lid_jid,))

        migrated_chats += 1
        migrated_messages += moved
        if dupes > 0:
            print(f"    Moved {moved} messages, removed {dupes} duplicates")
        else:
            print(f"    Moved {moved} messages")

    # Phase 2: Fix LID-based senders in messages (in all chats, including groups)
    print("\nPhase 2: Resolving LID-based senders in messages...")
    lid_senders = get_lid_senders(conn)
    print(f"Found {len(lid_senders)} distinct LID senders")

    for lid_sender in lid_senders:
        # Extract user part from sender (could be "user@lid" or just "user" with @lid)
        if '@' in lid_sender:
            lid_user = lid_sender.split('@')[0]
        else:
            lid_user = lid_sender

        # Strip device info if present (e.g., "user:0" or "user.0:1")
        lid_user_clean = lid_user.split(':')[0].split('.')[0]

        phone = lid_to_phone.get(lid_user_clean)
        if not phone:
            print(f"  SKIP: No phone mapping for sender {lid_sender}")
            continue

        if dry_run:
            cursor.execute("SELECT COUNT(*) FROM messages WHERE sender = ?", (lid_sender,))
            count = cursor.fetchone()[0]
            print(f"  Sender {lid_sender} -> {phone} ({count} messages)")
            migrated_senders += count
        else:
            cursor.execute("UPDATE messages SET sender = ? WHERE sender = ?",
                           (phone, lid_sender))
            migrated_senders += cursor.rowcount
            print(f"  Sender {lid_sender} -> {phone} ({cursor.rowcount} messages)")

    if not dry_run:
        conn.commit()

    conn.close()

    # Summary
    print(f"\n{'DRY RUN ' if dry_run else ''}Migration Summary:")
    print(f"  Chats migrated: {migrated_chats}")
    print(f"  Chats merged (both LID and phone existed): {merged_chats}")
    print(f"  Messages updated: {migrated_messages}")
    print(f"  Sender references updated: {migrated_senders}")

    if dry_run:
        print("\nThis was a dry run. No changes were made.")
        print("Run without --dry-run to apply changes.")
    else:
        print("\nMigration complete!")


if __name__ == '__main__':
    dry_run = '--dry-run' in sys.argv
    if dry_run:
        print("=== DRY RUN MODE ===\n")

    migrate(dry_run=dry_run)
