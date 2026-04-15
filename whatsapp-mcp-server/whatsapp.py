import sqlite3
from datetime import datetime
from dataclasses import dataclass
from typing import Optional, List, Tuple
import os.path
import requests
import json
import audio

MESSAGES_DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'whatsapp-bridge', 'store', 'messages.db')
WHATSMEOW_DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'whatsapp-bridge', 'store', 'whatsapp.db')
WHATSAPP_API_BASE_URL = "http://localhost:8080/api"


def resolve_lid_to_phone(lid_user: str) -> Optional[str]:
    """Look up a phone number for a LID user from the whatsmeow LID map.

    Args:
        lid_user: The user part of a LID JID (without @lid)

    Returns:
        The phone number (user part of @s.whatsapp.net JID) or None if not found
    """
    try:
        conn = sqlite3.connect(WHATSMEOW_DB_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT pn FROM whatsmeow_lid_map WHERE lid = ?", (lid_user,))
        result = cursor.fetchone()
        if result and result[0]:
            return result[0]
        return None
    except sqlite3.Error:
        return None
    finally:
        if 'conn' in locals():
            conn.close()


def resolve_phone_to_lid(phone_user: str) -> Optional[str]:
    """Look up a LID for a phone number from the whatsmeow LID map.

    Args:
        phone_user: The user part of a phone JID (without @s.whatsapp.net)

    Returns:
        The LID user part (without @lid) or None if not found
    """
    try:
        conn = sqlite3.connect(WHATSMEOW_DB_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT lid FROM whatsmeow_lid_map WHERE pn = ?", (phone_user,))
        result = cursor.fetchone()
        if result and result[0]:
            return result[0]
        return None
    except sqlite3.Error:
        return None
    finally:
        if 'conn' in locals():
            conn.close()

@dataclass
class Message:
    timestamp: datetime
    sender: str
    content: str
    is_from_me: bool
    chat_jid: str
    id: str
    chat_name: Optional[str] = None
    media_type: Optional[str] = None

@dataclass
class Chat:
    jid: str
    name: Optional[str]
    last_message_time: Optional[datetime]
    last_message: Optional[str] = None
    last_sender: Optional[str] = None
    last_is_from_me: Optional[bool] = None

    @property
    def is_group(self) -> bool:
        """Determine if chat is a group based on JID pattern."""
        return self.jid.endswith("@g.us")

@dataclass
class Contact:
    phone_number: str
    name: Optional[str]
    jid: str

@dataclass
class MessageContext:
    message: Message
    before: List[Message]
    after: List[Message]


@dataclass
class Label:
    id: str
    name: str
    color: int
    predefined_id: Optional[str] = None
    order_index: int = 0

def get_sender_name(sender_jid: str) -> str:
    try:
        conn = sqlite3.connect(MESSAGES_DB_PATH)
        cursor = conn.cursor()

        # First try matching by exact JID
        cursor.execute("""
            SELECT name
            FROM chats
            WHERE jid = ?
            LIMIT 1
        """, (sender_jid,))

        result = cursor.fetchone()

        # If no result, try looking for the number within JIDs
        if not result:
            # Extract the phone number part if it's a JID
            if '@' in sender_jid:
                phone_part = sender_jid.split('@')[0]
            else:
                phone_part = sender_jid

            cursor.execute("""
                SELECT name
                FROM chats
                WHERE jid LIKE ?
                LIMIT 1
            """, (f"%{phone_part}%",))

            result = cursor.fetchone()

        # If still no result and it looks like a LID, try resolving to phone
        if not result:
            if '@' in sender_jid:
                user_part = sender_jid.split('@')[0]
                server_part = sender_jid.split('@')[1] if '@' in sender_jid else ''
            else:
                user_part = sender_jid
                server_part = ''

            # Try LID -> phone resolution
            if server_part == 'lid' or not result:
                resolved_phone = resolve_lid_to_phone(user_part)
                if resolved_phone:
                    # Look up the phone-number-based JID
                    pn_jid = f"{resolved_phone}@s.whatsapp.net"
                    cursor.execute("""
                        SELECT name
                        FROM chats
                        WHERE jid = ?
                        LIMIT 1
                    """, (pn_jid,))
                    result = cursor.fetchone()

                    if not result:
                        # Return the phone number as a fallback
                        return resolved_phone

        if result and result[0]:
            return result[0]
        else:
            return sender_jid

    except sqlite3.Error as e:
        print(f"Database error while getting sender name: {e}")
        return sender_jid
    finally:
        if 'conn' in locals():
            conn.close()

def format_message(message: Message, show_chat_info: bool = True) -> None:
    """Print a single message with consistent formatting."""
    output = ""

    if show_chat_info and message.chat_name:
        output += f"[{message.timestamp:%Y-%m-%d %H:%M:%S}] Chat: {message.chat_name} "
    else:
        output += f"[{message.timestamp:%Y-%m-%d %H:%M:%S}] "

    # Always include message ID and chat JID for reactions, plus media type if present
    if hasattr(message, 'media_type') and message.media_type:
        msg_info = f"[{message.media_type}] "
    else:
        msg_info = ""

    try:
        sender_name = get_sender_name(message.sender) if not message.is_from_me else "Me"
        sender_jid = message.sender if not message.is_from_me else None
        from_me_flag = "from_me=True" if message.is_from_me else "from_me=False"
        sender_info = f", sender={sender_jid}" if sender_jid and message.chat_jid.endswith("@g.us") else ""
        output += f"From: {sender_name}: {msg_info}{message.content} (msg_id={message.id}, chat_jid={message.chat_jid}, {from_me_flag}{sender_info})\n"
    except Exception as e:
        print(f"Error formatting message: {e}")
    return output

def format_messages_list(messages: List[Message], show_chat_info: bool = True) -> None:
    output = ""
    if not messages:
        output += "No messages to display."
        return output
    
    for message in messages:
        output += format_message(message, show_chat_info)
    return output

def list_messages(
    after: Optional[str] = None,
    before: Optional[str] = None,
    sender_phone_number: Optional[str] = None,
    chat_jid: Optional[str] = None,
    query: Optional[str] = None,
    limit: int = 20,
    page: int = 0,
    include_context: bool = True,
    context_before: int = 1,
    context_after: int = 1
) -> List[Message]:
    """Get messages matching the specified criteria with optional context."""
    try:
        conn = sqlite3.connect(MESSAGES_DB_PATH)
        cursor = conn.cursor()
        
        # Build base query
        query_parts = ["SELECT messages.timestamp, messages.sender, chats.name, messages.content, messages.is_from_me, chats.jid, messages.id, messages.media_type FROM messages"]
        query_parts.append("JOIN chats ON messages.chat_jid = chats.jid")
        where_clauses = []
        params = []
        
        # Add filters
        if after:
            try:
                after = datetime.fromisoformat(after)
            except ValueError:
                raise ValueError(f"Invalid date format for 'after': {after}. Please use ISO-8601 format.")
            
            where_clauses.append("messages.timestamp > ?")
            params.append(after)

        if before:
            try:
                before = datetime.fromisoformat(before)
            except ValueError:
                raise ValueError(f"Invalid date format for 'before': {before}. Please use ISO-8601 format.")
            
            where_clauses.append("messages.timestamp < ?")
            params.append(before)

        if sender_phone_number:
            where_clauses.append("messages.sender = ?")
            params.append(sender_phone_number)
            
        if chat_jid:
            where_clauses.append("messages.chat_jid = ?")
            params.append(chat_jid)
            
        if query:
            where_clauses.append("LOWER(messages.content) LIKE LOWER(?)")
            params.append(f"%{query}%")
            
        if where_clauses:
            query_parts.append("WHERE " + " AND ".join(where_clauses))
            
        # Add pagination
        offset = page * limit
        query_parts.append("ORDER BY messages.timestamp DESC")
        query_parts.append("LIMIT ? OFFSET ?")
        params.extend([limit, offset])
        
        cursor.execute(" ".join(query_parts), tuple(params))
        messages = cursor.fetchall()
        
        result = []
        for msg in messages:
            message = Message(
                timestamp=datetime.fromisoformat(msg[0]),
                sender=msg[1],
                chat_name=msg[2],
                content=msg[3],
                is_from_me=msg[4],
                chat_jid=msg[5],
                id=msg[6],
                media_type=msg[7]
            )
            result.append(message)
            
        if include_context and result:
            # Add context for each message
            messages_with_context = []
            for msg in result:
                context = get_message_context(msg.id, context_before, context_after)
                messages_with_context.extend(context.before)
                messages_with_context.append(context.message)
                messages_with_context.extend(context.after)
            
            return format_messages_list(messages_with_context, show_chat_info=True)
            
        # Format and display messages without context
        return format_messages_list(result, show_chat_info=True)    
        
    except sqlite3.Error as e:
        print(f"Database error: {e}")
        return []
    finally:
        if 'conn' in locals():
            conn.close()


def get_message_context(
    message_id: str,
    before: int = 5,
    after: int = 5
) -> MessageContext:
    """Get context around a specific message."""
    try:
        conn = sqlite3.connect(MESSAGES_DB_PATH)
        cursor = conn.cursor()
        
        # Get the target message first
        cursor.execute("""
            SELECT messages.timestamp, messages.sender, chats.name, messages.content, messages.is_from_me, chats.jid, messages.id, messages.chat_jid, messages.media_type
            FROM messages
            JOIN chats ON messages.chat_jid = chats.jid
            WHERE messages.id = ?
        """, (message_id,))
        msg_data = cursor.fetchone()
        
        if not msg_data:
            raise ValueError(f"Message with ID {message_id} not found")
            
        target_message = Message(
            timestamp=datetime.fromisoformat(msg_data[0]),
            sender=msg_data[1],
            chat_name=msg_data[2],
            content=msg_data[3],
            is_from_me=msg_data[4],
            chat_jid=msg_data[5],
            id=msg_data[6],
            media_type=msg_data[8]
        )
        
        # Get messages before
        cursor.execute("""
            SELECT messages.timestamp, messages.sender, chats.name, messages.content, messages.is_from_me, chats.jid, messages.id, messages.media_type
            FROM messages
            JOIN chats ON messages.chat_jid = chats.jid
            WHERE messages.chat_jid = ? AND messages.timestamp < ?
            ORDER BY messages.timestamp DESC
            LIMIT ?
        """, (msg_data[7], msg_data[0], before))
        
        before_messages = []
        for msg in cursor.fetchall():
            before_messages.append(Message(
                timestamp=datetime.fromisoformat(msg[0]),
                sender=msg[1],
                chat_name=msg[2],
                content=msg[3],
                is_from_me=msg[4],
                chat_jid=msg[5],
                id=msg[6],
                media_type=msg[7]
            ))
        
        # Get messages after
        cursor.execute("""
            SELECT messages.timestamp, messages.sender, chats.name, messages.content, messages.is_from_me, chats.jid, messages.id, messages.media_type
            FROM messages
            JOIN chats ON messages.chat_jid = chats.jid
            WHERE messages.chat_jid = ? AND messages.timestamp > ?
            ORDER BY messages.timestamp ASC
            LIMIT ?
        """, (msg_data[7], msg_data[0], after))
        
        after_messages = []
        for msg in cursor.fetchall():
            after_messages.append(Message(
                timestamp=datetime.fromisoformat(msg[0]),
                sender=msg[1],
                chat_name=msg[2],
                content=msg[3],
                is_from_me=msg[4],
                chat_jid=msg[5],
                id=msg[6],
                media_type=msg[7]
            ))
        
        return MessageContext(
            message=target_message,
            before=before_messages,
            after=after_messages
        )
        
    except sqlite3.Error as e:
        print(f"Database error: {e}")
        raise
    finally:
        if 'conn' in locals():
            conn.close()


def list_chats(
    query: Optional[str] = None,
    limit: int = 20,
    page: int = 0,
    include_last_message: bool = True,
    sort_by: str = "last_active",
    label_id: Optional[str] = None
) -> List[Chat]:
    """Get chats matching the specified criteria."""
    try:
        conn = sqlite3.connect(MESSAGES_DB_PATH)
        cursor = conn.cursor()

        # Build base query
        query_parts = ["""
            SELECT
                chats.jid,
                chats.name,
                chats.last_message_time,
                messages.content as last_message,
                messages.sender as last_sender,
                messages.is_from_me as last_is_from_me
            FROM chats
        """]

        if include_last_message:
            query_parts.append("""
                LEFT JOIN messages ON chats.jid = messages.chat_jid
                AND chats.last_message_time = messages.timestamp
            """)

        # Add label filter join if needed
        if label_id:
            query_parts.append("JOIN chat_labels ON chats.jid = chat_labels.chat_jid")

        where_clauses = []
        params = []

        if query:
            where_clauses.append("(LOWER(chats.name) LIKE LOWER(?) OR chats.jid LIKE ?)")
            params.extend([f"%{query}%", f"%{query}%"])

        if label_id:
            where_clauses.append("chat_labels.label_id = ?")
            params.append(label_id)

        if where_clauses:
            query_parts.append("WHERE " + " AND ".join(where_clauses))

        # Add sorting
        order_by = "chats.last_message_time DESC" if sort_by == "last_active" else "chats.name"
        query_parts.append(f"ORDER BY {order_by}")

        # Add pagination
        offset = (page ) * limit
        query_parts.append("LIMIT ? OFFSET ?")
        params.extend([limit, offset])

        cursor.execute(" ".join(query_parts), tuple(params))
        chats = cursor.fetchall()

        result = []
        for chat_data in chats:
            chat = Chat(
                jid=chat_data[0],
                name=chat_data[1],
                last_message_time=datetime.fromisoformat(chat_data[2]) if chat_data[2] else None,
                last_message=chat_data[3],
                last_sender=chat_data[4],
                last_is_from_me=chat_data[5]
            )
            result.append(chat)

        return result

    except sqlite3.Error as e:
        print(f"Database error: {e}")
        return []
    finally:
        if 'conn' in locals():
            conn.close()


def search_contacts(query: str) -> List[Contact]:
    """Search contacts by name or phone number.

    Also searches the whatsmeow LID map to find contacts whose chats
    may be stored under LID JIDs.
    """
    try:
        conn = sqlite3.connect(MESSAGES_DB_PATH)
        cursor = conn.cursor()

        # Split query into characters to support partial matching
        search_pattern = '%' + query + '%'

        cursor.execute("""
            SELECT DISTINCT
                jid,
                name
            FROM chats
            WHERE
                (LOWER(name) LIKE LOWER(?) OR LOWER(jid) LIKE LOWER(?))
                AND jid NOT LIKE '%@g.us'
            ORDER BY name, jid
            LIMIT 50
        """, (search_pattern, search_pattern))

        contacts = cursor.fetchall()

        result = []
        seen_jids = set()
        for contact_data in contacts:
            jid = contact_data[0]
            seen_jids.add(jid)
            # For LID JIDs, try to resolve to phone number for display
            phone_number = jid.split('@')[0]
            if jid.endswith('@lid'):
                resolved_phone = resolve_lid_to_phone(phone_number)
                if resolved_phone:
                    phone_number = resolved_phone
            contact = Contact(
                phone_number=phone_number,
                name=contact_data[1],
                jid=jid
            )
            result.append(contact)

        # Also search by phone number via LID map - if user searches for a phone
        # number, find if there's a LID chat for it
        try:
            lid_conn = sqlite3.connect(WHATSMEOW_DB_PATH)
            lid_cursor = lid_conn.cursor()
            lid_cursor.execute("""
                SELECT lid, pn FROM whatsmeow_lid_map
                WHERE pn LIKE ?
                LIMIT 20
            """, (search_pattern,))
            lid_mappings = lid_cursor.fetchall()

            for lid, pn in lid_mappings:
                lid_jid = f"{lid}@lid"
                pn_jid = f"{pn}@s.whatsapp.net"
                # Check if there's a chat under the LID JID that we haven't already found
                if lid_jid not in seen_jids and pn_jid not in seen_jids:
                    cursor.execute("SELECT jid, name FROM chats WHERE jid = ?", (lid_jid,))
                    chat_data = cursor.fetchone()
                    if chat_data:
                        seen_jids.add(lid_jid)
                        result.append(Contact(
                            phone_number=pn,
                            name=chat_data[1],
                            jid=chat_data[0]
                        ))
            lid_conn.close()
        except sqlite3.Error:
            pass  # LID map lookup is best-effort

        return result

    except sqlite3.Error as e:
        print(f"Database error: {e}")
        return []
    finally:
        if 'conn' in locals():
            conn.close()


def get_contact_chats(jid: str, limit: int = 20, page: int = 0) -> List[Chat]:
    """Get all chats involving the contact.
    
    Args:
        jid: The contact's JID to search for
        limit: Maximum number of chats to return (default 20)
        page: Page number for pagination (default 0)
    """
    try:
        conn = sqlite3.connect(MESSAGES_DB_PATH)
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT DISTINCT
                c.jid,
                c.name,
                c.last_message_time,
                m.content as last_message,
                m.sender as last_sender,
                m.is_from_me as last_is_from_me
            FROM chats c
            JOIN messages m ON c.jid = m.chat_jid
            WHERE m.sender = ? OR c.jid = ?
            ORDER BY c.last_message_time DESC
            LIMIT ? OFFSET ?
        """, (jid, jid, limit, page * limit))
        
        chats = cursor.fetchall()
        
        result = []
        for chat_data in chats:
            chat = Chat(
                jid=chat_data[0],
                name=chat_data[1],
                last_message_time=datetime.fromisoformat(chat_data[2]) if chat_data[2] else None,
                last_message=chat_data[3],
                last_sender=chat_data[4],
                last_is_from_me=chat_data[5]
            )
            result.append(chat)
            
        return result
        
    except sqlite3.Error as e:
        print(f"Database error: {e}")
        return []
    finally:
        if 'conn' in locals():
            conn.close()


def get_last_interaction(jid: str) -> str:
    """Get most recent message involving the contact."""
    try:
        conn = sqlite3.connect(MESSAGES_DB_PATH)
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT 
                m.timestamp,
                m.sender,
                c.name,
                m.content,
                m.is_from_me,
                c.jid,
                m.id,
                m.media_type
            FROM messages m
            JOIN chats c ON m.chat_jid = c.jid
            WHERE m.sender = ? OR c.jid = ?
            ORDER BY m.timestamp DESC
            LIMIT 1
        """, (jid, jid))
        
        msg_data = cursor.fetchone()
        
        if not msg_data:
            return None
            
        message = Message(
            timestamp=datetime.fromisoformat(msg_data[0]),
            sender=msg_data[1],
            chat_name=msg_data[2],
            content=msg_data[3],
            is_from_me=msg_data[4],
            chat_jid=msg_data[5],
            id=msg_data[6],
            media_type=msg_data[7]
        )
        
        return format_message(message)
        
    except sqlite3.Error as e:
        print(f"Database error: {e}")
        return None
    finally:
        if 'conn' in locals():
            conn.close()


def get_chat(chat_jid: str, include_last_message: bool = True) -> Optional[Chat]:
    """Get chat metadata by JID."""
    try:
        conn = sqlite3.connect(MESSAGES_DB_PATH)
        cursor = conn.cursor()
        
        query = """
            SELECT 
                c.jid,
                c.name,
                c.last_message_time,
                m.content as last_message,
                m.sender as last_sender,
                m.is_from_me as last_is_from_me
            FROM chats c
        """
        
        if include_last_message:
            query += """
                LEFT JOIN messages m ON c.jid = m.chat_jid 
                AND c.last_message_time = m.timestamp
            """
            
        query += " WHERE c.jid = ?"
        
        cursor.execute(query, (chat_jid,))
        chat_data = cursor.fetchone()
        
        if not chat_data:
            return None
            
        return Chat(
            jid=chat_data[0],
            name=chat_data[1],
            last_message_time=datetime.fromisoformat(chat_data[2]) if chat_data[2] else None,
            last_message=chat_data[3],
            last_sender=chat_data[4],
            last_is_from_me=chat_data[5]
        )
        
    except sqlite3.Error as e:
        print(f"Database error: {e}")
        return None
    finally:
        if 'conn' in locals():
            conn.close()


def get_direct_chat_by_contact(sender_phone_number: str) -> Optional[Chat]:
    """Get chat metadata by sender phone number.

    Also checks LID-based chats by looking up the LID mapping for the phone number.
    """
    try:
        conn = sqlite3.connect(MESSAGES_DB_PATH)
        cursor = conn.cursor()

        cursor.execute("""
            SELECT
                c.jid,
                c.name,
                c.last_message_time,
                m.content as last_message,
                m.sender as last_sender,
                m.is_from_me as last_is_from_me
            FROM chats c
            LEFT JOIN messages m ON c.jid = m.chat_jid
                AND c.last_message_time = m.timestamp
            WHERE c.jid LIKE ? AND c.jid NOT LIKE '%@g.us'
            LIMIT 1
        """, (f"%{sender_phone_number}%",))

        chat_data = cursor.fetchone()

        # If not found by phone number, try LID lookup
        if not chat_data:
            lid_user = resolve_phone_to_lid(sender_phone_number)
            if lid_user:
                cursor.execute("""
                    SELECT
                        c.jid,
                        c.name,
                        c.last_message_time,
                        m.content as last_message,
                        m.sender as last_sender,
                        m.is_from_me as last_is_from_me
                    FROM chats c
                    LEFT JOIN messages m ON c.jid = m.chat_jid
                        AND c.last_message_time = m.timestamp
                    WHERE c.jid = ?
                    LIMIT 1
                """, (f"{lid_user}@lid",))
                chat_data = cursor.fetchone()

        if not chat_data:
            return None

        return Chat(
            jid=chat_data[0],
            name=chat_data[1],
            last_message_time=datetime.fromisoformat(chat_data[2]) if chat_data[2] else None,
            last_message=chat_data[3],
            last_sender=chat_data[4],
            last_is_from_me=chat_data[5]
        )

    except sqlite3.Error as e:
        print(f"Database error: {e}")
        return None
    finally:
        if 'conn' in locals():
            conn.close()

def send_message(recipient: str, message: str) -> Tuple[bool, str, Optional[str]]:
    try:
        # Validate input
        if not recipient:
            return False, "Recipient must be provided", None

        url = f"{WHATSAPP_API_BASE_URL}/send"
        payload = {
            "recipient": recipient,
            "message": message,
        }

        response = requests.post(url, json=payload)

        # Check if the request was successful
        if response.status_code == 200:
            result = response.json()
            return result.get("success", False), result.get("message", "Unknown response"), result.get("message_id")
        else:
            return False, f"Error: HTTP {response.status_code} - {response.text}", None

    except requests.RequestException as e:
        return False, f"Request error: {str(e)}", None
    except json.JSONDecodeError:
        return False, f"Error parsing response: {response.text}", None
    except Exception as e:
        return False, f"Unexpected error: {str(e)}", None

def send_file(recipient: str, media_path: str) -> Tuple[bool, str]:
    try:
        # Validate input
        if not recipient:
            return False, "Recipient must be provided"
        
        if not media_path:
            return False, "Media path must be provided"
        
        if not os.path.isfile(media_path):
            return False, f"Media file not found: {media_path}"
        
        url = f"{WHATSAPP_API_BASE_URL}/send"
        payload = {
            "recipient": recipient,
            "media_path": media_path
        }
        
        response = requests.post(url, json=payload)
        
        # Check if the request was successful
        if response.status_code == 200:
            result = response.json()
            return result.get("success", False), result.get("message", "Unknown response")
        else:
            return False, f"Error: HTTP {response.status_code} - {response.text}"
            
    except requests.RequestException as e:
        return False, f"Request error: {str(e)}"
    except json.JSONDecodeError:
        return False, f"Error parsing response: {response.text}"
    except Exception as e:
        return False, f"Unexpected error: {str(e)}"

def send_audio_message(recipient: str, media_path: str) -> Tuple[bool, str]:
    try:
        # Validate input
        if not recipient:
            return False, "Recipient must be provided"
        
        if not media_path:
            return False, "Media path must be provided"
        
        if not os.path.isfile(media_path):
            return False, f"Media file not found: {media_path}"

        if not media_path.endswith(".ogg"):
            try:
                media_path = audio.convert_to_opus_ogg_temp(media_path)
            except Exception as e:
                return False, f"Error converting file to opus ogg. You likely need to install ffmpeg: {str(e)}"
        
        url = f"{WHATSAPP_API_BASE_URL}/send"
        payload = {
            "recipient": recipient,
            "media_path": media_path
        }
        
        response = requests.post(url, json=payload)
        
        # Check if the request was successful
        if response.status_code == 200:
            result = response.json()
            return result.get("success", False), result.get("message", "Unknown response")
        else:
            return False, f"Error: HTTP {response.status_code} - {response.text}"
            
    except requests.RequestException as e:
        return False, f"Request error: {str(e)}"
    except json.JSONDecodeError:
        return False, f"Error parsing response: {response.text}"
    except Exception as e:
        return False, f"Unexpected error: {str(e)}"

def download_media(message_id: str, chat_jid: str) -> Optional[str]:
    """Download media from a message and return the local file path.
    
    Args:
        message_id: The ID of the message containing the media
        chat_jid: The JID of the chat containing the message
    
    Returns:
        The local file path if download was successful, None otherwise
    """
    try:
        url = f"{WHATSAPP_API_BASE_URL}/download"
        payload = {
            "message_id": message_id,
            "chat_jid": chat_jid
        }
        
        response = requests.post(url, json=payload)
        
        if response.status_code == 200:
            result = response.json()
            if result.get("success", False):
                path = result.get("path")
                print(f"Media downloaded successfully: {path}")
                return path
            else:
                print(f"Download failed: {result.get('message', 'Unknown error')}")
                return None
        else:
            print(f"Error: HTTP {response.status_code} - {response.text}")
            return None
            
    except requests.RequestException as e:
        print(f"Request error: {str(e)}")
        return None
    except json.JSONDecodeError:
        print(f"Error parsing response: {response.text}")
        return None
    except Exception as e:
        print(f"Unexpected error: {str(e)}")
        return None

def get_profile_picture(jid: str, is_community: bool = False) -> Tuple[bool, str, Optional[str]]:
    """
    Get the profile picture URL for a WhatsApp user or group.

    Args:
        jid: The JID of the user or group (e.g., "1234567890@s.whatsapp.net" or "123456789@g.us")
        is_community: Set to True if requesting a community's profile picture

    Returns:
        Tuple of (success, message, url). URL is None if unsuccessful.
    """
    try:
        if not jid:
            return False, "JID must be provided", None

        url = f"{WHATSAPP_API_BASE_URL}/profile-picture"
        payload = {
            "jid": jid,
            "is_community": is_community
        }

        response = requests.post(url, json=payload)
        result = response.json()

        if response.status_code == 200 and result.get("success"):
            return True, result.get("message", "Success"), result.get("url")
        else:
            return False, result.get("message", f"HTTP {response.status_code}"), None

    except requests.RequestException as e:
        return False, f"Request error: {str(e)}", None
    except json.JSONDecodeError:
        return False, f"Error parsing response: {response.text}", None
    except Exception as e:
        return False, f"Unexpected error: {str(e)}", None


def send_reaction(chat_jid: str, message_id: str, emoji: str, from_me: bool, sender: Optional[str] = None) -> Tuple[bool, str]:
    """
    Send a reaction to a WhatsApp message.

    Args:
        chat_jid: The JID of the chat containing the message
        message_id: The ID of the message to react to
        emoji: The emoji to react with (empty string to remove reaction)
        from_me: Whether the message being reacted to was sent by me
        sender: The sender JID (required for group messages when reacting to others' messages)

    Returns:
        Tuple of (success, message)
    """
    try:
        if not chat_jid:
            return False, "Chat JID must be provided"
        if not message_id:
            return False, "Message ID must be provided"

        url = f"{WHATSAPP_API_BASE_URL}/react"
        payload = {
            "chat_jid": chat_jid,
            "message_id": message_id,
            "emoji": emoji,
            "from_me": from_me
        }

        if sender:
            payload["sender"] = sender

        response = requests.post(url, json=payload)
        result = response.json()

        if response.status_code == 200 and result.get("success"):
            return True, result.get("message", "Reaction sent")
        else:
            return False, result.get("message", f"HTTP {response.status_code}")

    except requests.RequestException as e:
        return False, f"Request error: {str(e)}"
    except json.JSONDecodeError:
        return False, f"Error parsing response: {response.text}"
    except Exception as e:
        return False, f"Unexpected error: {str(e)}"


def revoke_message(chat_jid: str, message_id: str) -> Tuple[bool, str]:
    """
    Revoke/delete a WhatsApp message for everyone.

    Args:
        chat_jid: The JID of the chat containing the message
        message_id: The ID of the message to delete

    Returns:
        Tuple of (success, message)
    """
    try:
        if not chat_jid:
            return False, "Chat JID must be provided"
        if not message_id:
            return False, "Message ID must be provided"

        url = f"{WHATSAPP_API_BASE_URL}/revoke"
        payload = {
            "chat_jid": chat_jid,
            "message_id": message_id
        }

        response = requests.post(url, json=payload)
        result = response.json()

        if response.status_code == 200 and result.get("success"):
            return True, result.get("message", "Message deleted")
        else:
            return False, result.get("message", f"HTTP {response.status_code}")

    except requests.RequestException as e:
        return False, f"Request error: {str(e)}"
    except json.JSONDecodeError:
        return False, f"Error parsing response: {response.text}"
    except Exception as e:
        return False, f"Unexpected error: {str(e)}"


def send_chat_presence(chat_jid: str, state: str) -> Tuple[bool, str]:
    """
    Send chat presence (typing indicator) to a chat.

    Args:
        chat_jid: The JID of the chat
        state: The presence state - "composing" (typing) or "paused" (stopped typing)

    Returns:
        Tuple of (success, message)
    """
    try:
        if not chat_jid:
            return False, "Chat JID must be provided"
        if state not in ("composing", "paused"):
            return False, "State must be 'composing' or 'paused'"

        url = f"{WHATSAPP_API_BASE_URL}/presence"
        payload = {
            "chat_jid": chat_jid,
            "state": state
        }

        response = requests.post(url, json=payload)
        result = response.json()

        if response.status_code == 200 and result.get("success"):
            return True, result.get("message", "Presence sent")
        else:
            return False, result.get("message", f"HTTP {response.status_code}")

    except requests.RequestException as e:
        return False, f"Request error: {str(e)}"
    except json.JSONDecodeError:
        return False, f"Error parsing response: {response.text}"
    except Exception as e:
        return False, f"Unexpected error: {str(e)}"


def edit_message(chat_jid: str, message_id: str, new_content: str) -> Tuple[bool, str]:
    """
    Edit a WhatsApp message.

    Args:
        chat_jid: The JID of the chat containing the message
        message_id: The ID of the message to edit
        new_content: The new content for the message

    Returns:
        Tuple of (success, message)
    """
    try:
        if not chat_jid:
            return False, "Chat JID must be provided"
        if not message_id:
            return False, "Message ID must be provided"
        if not new_content:
            return False, "New content must be provided"

        url = f"{WHATSAPP_API_BASE_URL}/edit"
        payload = {
            "chat_jid": chat_jid,
            "message_id": message_id,
            "new_content": new_content
        }

        response = requests.post(url, json=payload)
        result = response.json()

        if response.status_code == 200 and result.get("success"):
            return True, result.get("message", "Message edited")
        else:
            return False, result.get("message", f"HTTP {response.status_code}")

    except requests.RequestException as e:
        return False, f"Request error: {str(e)}"
    except json.JSONDecodeError:
        return False, f"Error parsing response: {response.text}"
    except Exception as e:
        return False, f"Unexpected error: {str(e)}"


def list_labels() -> List[Label]:
    """Get all WhatsApp labels."""
    try:
        conn = sqlite3.connect(MESSAGES_DB_PATH)
        cursor = conn.cursor()

        cursor.execute("""
            SELECT id, name, color, predefined_id, order_index
            FROM labels
            WHERE deleted = 0
            ORDER BY order_index
        """)

        labels_data = cursor.fetchall()

        result = []
        for label_data in labels_data:
            label = Label(
                id=label_data[0],
                name=label_data[1],
                color=label_data[2],
                predefined_id=label_data[3],
                order_index=label_data[4]
            )
            result.append(label)

        return result

    except sqlite3.Error as e:
        print(f"Database error: {e}")
        return []
    finally:
        if 'conn' in locals():
            conn.close()


def get_chat_labels(chat_jid: str) -> List[Label]:
    """Get labels assigned to a specific chat."""
    try:
        conn = sqlite3.connect(MESSAGES_DB_PATH)
        cursor = conn.cursor()

        cursor.execute("""
            SELECT l.id, l.name, l.color, l.predefined_id, l.order_index
            FROM labels l
            JOIN chat_labels cl ON l.id = cl.label_id
            WHERE cl.chat_jid = ? AND l.deleted = 0
            ORDER BY l.order_index
        """, (chat_jid,))

        labels_data = cursor.fetchall()

        result = []
        for label_data in labels_data:
            label = Label(
                id=label_data[0],
                name=label_data[1],
                color=label_data[2],
                predefined_id=label_data[3],
                order_index=label_data[4]
            )
            result.append(label)

        return result

    except sqlite3.Error as e:
        print(f"Database error: {e}")
        return []
    finally:
        if 'conn' in locals():
            conn.close()


def get_chats_by_label(label_id: str, limit: int = 20, page: int = 0) -> List[Chat]:
    """Get chats that have a specific label assigned."""
    try:
        conn = sqlite3.connect(MESSAGES_DB_PATH)
        cursor = conn.cursor()

        offset = page * limit

        cursor.execute("""
            SELECT
                c.jid,
                c.name,
                c.last_message_time,
                m.content as last_message,
                m.sender as last_sender,
                m.is_from_me as last_is_from_me
            FROM chats c
            JOIN chat_labels cl ON c.jid = cl.chat_jid
            LEFT JOIN messages m ON c.jid = m.chat_jid
                AND c.last_message_time = m.timestamp
            WHERE cl.label_id = ?
            ORDER BY c.last_message_time DESC
            LIMIT ? OFFSET ?
        """, (label_id, limit, offset))

        chats = cursor.fetchall()

        result = []
        for chat_data in chats:
            chat = Chat(
                jid=chat_data[0],
                name=chat_data[1],
                last_message_time=datetime.fromisoformat(chat_data[2]) if chat_data[2] else None,
                last_message=chat_data[3],
                last_sender=chat_data[4],
                last_is_from_me=chat_data[5]
            )
            result.append(chat)

        return result

    except sqlite3.Error as e:
        print(f"Database error: {e}")
        return []
    finally:
        if 'conn' in locals():
            conn.close()
