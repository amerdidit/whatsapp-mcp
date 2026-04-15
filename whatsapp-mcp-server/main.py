from typing import List, Dict, Any, Optional
import subprocess
import os
from mcp.server.fastmcp import FastMCP
from whatsapp import (
    search_contacts as whatsapp_search_contacts,
    list_messages as whatsapp_list_messages,
    list_chats as whatsapp_list_chats,
    get_chat as whatsapp_get_chat,
    get_direct_chat_by_contact as whatsapp_get_direct_chat_by_contact,
    get_contact_chats as whatsapp_get_contact_chats,
    get_last_interaction as whatsapp_get_last_interaction,
    get_message_context as whatsapp_get_message_context,
    send_message as whatsapp_send_message,
    send_file as whatsapp_send_file,
    send_audio_message as whatsapp_audio_voice_message,
    download_media as whatsapp_download_media,
    get_profile_picture as whatsapp_get_profile_picture,
    send_reaction as whatsapp_send_reaction,
    edit_message as whatsapp_edit_message,
    revoke_message as whatsapp_revoke_message,
    send_chat_presence as whatsapp_send_chat_presence,
    list_labels as whatsapp_list_labels,
    get_chat_labels as whatsapp_get_chat_labels,
    get_chats_by_label as whatsapp_get_chats_by_label
)

# Initialize FastMCP server
mcp = FastMCP("whatsapp")

@mcp.tool()
def search_contacts(query: str) -> List[Dict[str, Any]]:
    """Search WhatsApp contacts by name or phone number.
    
    Args:
        query: Search term to match against contact names or phone numbers
    """
    contacts = whatsapp_search_contacts(query)
    return contacts

@mcp.tool()
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
) -> List[Dict[str, Any]]:
    """Get WhatsApp messages matching specified criteria with optional context.
    
    Args:
        after: Optional ISO-8601 formatted string to only return messages after this date
        before: Optional ISO-8601 formatted string to only return messages before this date
        sender_phone_number: Optional phone number to filter messages by sender
        chat_jid: Optional chat JID to filter messages by chat
        query: Optional search term to filter messages by content
        limit: Maximum number of messages to return (default 20)
        page: Page number for pagination (default 0)
        include_context: Whether to include messages before and after matches (default True)
        context_before: Number of messages to include before each match (default 1)
        context_after: Number of messages to include after each match (default 1)
    """
    messages = whatsapp_list_messages(
        after=after,
        before=before,
        sender_phone_number=sender_phone_number,
        chat_jid=chat_jid,
        query=query,
        limit=limit,
        page=page,
        include_context=include_context,
        context_before=context_before,
        context_after=context_after
    )
    return messages

@mcp.tool()
def list_chats(
    query: Optional[str] = None,
    limit: int = 20,
    page: int = 0,
    include_last_message: bool = True,
    sort_by: str = "last_active",
    label_id: Optional[str] = None
) -> List[Dict[str, Any]]:
    """Get WhatsApp chats matching specified criteria.

    Args:
        query: Optional search term to filter chats by name or JID
        limit: Maximum number of chats to return (default 20)
        page: Page number for pagination (default 0)
        include_last_message: Whether to include the last message in each chat (default True)
        sort_by: Field to sort results by, either "last_active" or "name" (default "last_active")
        label_id: Optional label ID to filter chats by (only returns chats with this label)
    """
    chats = whatsapp_list_chats(
        query=query,
        limit=limit,
        page=page,
        include_last_message=include_last_message,
        sort_by=sort_by,
        label_id=label_id
    )
    return chats

@mcp.tool()
def get_chat(chat_jid: str, include_last_message: bool = True) -> Dict[str, Any]:
    """Get WhatsApp chat metadata by JID.
    
    Args:
        chat_jid: The JID of the chat to retrieve
        include_last_message: Whether to include the last message (default True)
    """
    chat = whatsapp_get_chat(chat_jid, include_last_message)
    return chat

@mcp.tool()
def get_direct_chat_by_contact(sender_phone_number: str) -> Dict[str, Any]:
    """Get WhatsApp chat metadata by sender phone number.
    
    Args:
        sender_phone_number: The phone number to search for
    """
    chat = whatsapp_get_direct_chat_by_contact(sender_phone_number)
    return chat

@mcp.tool()
def get_contact_chats(jid: str, limit: int = 20, page: int = 0) -> List[Dict[str, Any]]:
    """Get all WhatsApp chats involving the contact.
    
    Args:
        jid: The contact's JID to search for
        limit: Maximum number of chats to return (default 20)
        page: Page number for pagination (default 0)
    """
    chats = whatsapp_get_contact_chats(jid, limit, page)
    return chats

@mcp.tool()
def get_last_interaction(jid: str) -> str:
    """Get most recent WhatsApp message involving the contact.
    
    Args:
        jid: The JID of the contact to search for
    """
    message = whatsapp_get_last_interaction(jid)
    return message

@mcp.tool()
def get_message_context(
    message_id: str,
    before: int = 5,
    after: int = 5
) -> Dict[str, Any]:
    """Get context around a specific WhatsApp message.
    
    Args:
        message_id: The ID of the message to get context for
        before: Number of messages to include before the target message (default 5)
        after: Number of messages to include after the target message (default 5)
    """
    context = whatsapp_get_message_context(message_id, before, after)
    return context

@mcp.tool()
def send_message(
    recipient: str,
    message: str
) -> Dict[str, Any]:
    """Send a WhatsApp message to a person or group. For group chats use the JID.

    Args:
        recipient: The recipient - either a phone number with country code but no + or other symbols,
                 or a JID (e.g., "123456789@s.whatsapp.net" or a group JID like "123456789@g.us")
        message: The message text to send

    Returns:
        A dictionary containing success status, a status message, and the message_id if successful
    """
    # Validate input
    if not recipient:
        return {
            "success": False,
            "message": "Recipient must be provided"
        }

    # Call the whatsapp_send_message function with the unified recipient parameter
    success, status_message, message_id = whatsapp_send_message(recipient, message)
    result = {
        "success": success,
        "message": status_message
    }
    if message_id:
        result["message_id"] = message_id
    return result

@mcp.tool()
def send_file(recipient: str, media_path: str) -> Dict[str, Any]:
    """Send a file such as a picture, raw audio, video or document via WhatsApp to the specified recipient. For group messages use the JID.
    
    Args:
        recipient: The recipient - either a phone number with country code but no + or other symbols,
                 or a JID (e.g., "123456789@s.whatsapp.net" or a group JID like "123456789@g.us")
        media_path: The absolute path to the media file to send (image, video, document)
    
    Returns:
        A dictionary containing success status and a status message
    """
    
    # Call the whatsapp_send_file function
    success, status_message = whatsapp_send_file(recipient, media_path)
    return {
        "success": success,
        "message": status_message
    }

@mcp.tool()
def send_audio_message(recipient: str, media_path: str) -> Dict[str, Any]:
    """Send any audio file as a WhatsApp audio message to the specified recipient. For group messages use the JID. If it errors due to ffmpeg not being installed, use send_file instead.
    
    Args:
        recipient: The recipient - either a phone number with country code but no + or other symbols,
                 or a JID (e.g., "123456789@s.whatsapp.net" or a group JID like "123456789@g.us")
        media_path: The absolute path to the audio file to send (will be converted to Opus .ogg if it's not a .ogg file)
    
    Returns:
        A dictionary containing success status and a status message
    """
    success, status_message = whatsapp_audio_voice_message(recipient, media_path)
    return {
        "success": success,
        "message": status_message
    }

@mcp.tool()
def download_media(message_id: str, chat_jid: str) -> Dict[str, Any]:
    """Download media from a WhatsApp message and get the local file path.

    Args:
        message_id: The ID of the message containing the media
        chat_jid: The JID of the chat containing the message

    Returns:
        A dictionary containing success status, a status message, and the file path if successful
    """
    file_path = whatsapp_download_media(message_id, chat_jid)

    if file_path:
        return {
            "success": True,
            "message": "Media downloaded successfully",
            "file_path": file_path
        }
    else:
        return {
            "success": False,
            "message": "Failed to download media"
        }

@mcp.tool()
def transcribe_audio(message_id: str, chat_jid: str, model: str = "small", language: Optional[str] = None) -> Dict[str, Any]:
    """Download and transcribe a voice note or audio message using Whisper.

    Args:
        message_id: The ID of the message containing the audio
        chat_jid: The JID of the chat containing the message
        model: Whisper model size: tiny, base, small, medium, large (default: small)
        language: Optional language code (e.g., "en", "ar", "de"). Auto-detected if not set.

    Returns:
        A dictionary with the transcription text and metadata
    """
    # Download the audio file first
    file_path = whatsapp_download_media(message_id, chat_jid)
    if not file_path:
        return {"success": False, "message": "Failed to download audio"}

    if not os.path.exists(file_path):
        return {"success": False, "message": f"Downloaded file not found: {file_path}"}

    # Build whisper command
    cmd = ["whisper", file_path, "--model", model, "--output_format", "json", "--output_dir", "/tmp/whisper_out"]
    if language:
        cmd.extend(["--language", language])

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        if result.returncode != 0:
            return {"success": False, "message": f"Whisper failed: {result.stderr[-500:] if result.stderr else 'unknown error'}"}

        # Read the JSON output
        import json
        base_name = os.path.splitext(os.path.basename(file_path))[0]
        json_path = f"/tmp/whisper_out/{base_name}.json"

        if not os.path.exists(json_path):
            # Fall back to txt output
            txt_path = f"/tmp/whisper_out/{base_name}.txt"
            if os.path.exists(txt_path):
                with open(txt_path) as f:
                    return {"success": True, "text": f.read().strip(), "file_path": file_path}
            return {"success": False, "message": "Whisper produced no output"}

        with open(json_path) as f:
            whisper_output = json.load(f)

        return {
            "success": True,
            "text": whisper_output.get("text", "").strip(),
            "language": whisper_output.get("language", "unknown"),
            "segments": [{"start": s["start"], "end": s["end"], "text": s["text"]} for s in whisper_output.get("segments", [])],
            "file_path": file_path
        }

    except subprocess.TimeoutExpired:
        return {"success": False, "message": "Transcription timed out (5 min limit)"}
    except Exception as e:
        return {"success": False, "message": f"Transcription error: {str(e)}"}

@mcp.tool()
def get_profile_picture(jid: str, is_community: bool = False) -> Dict[str, Any]:
    """Get the profile picture URL for a WhatsApp user or group.

    Args:
        jid: The JID of the user or group (e.g., "1234567890@s.whatsapp.net" or "123456789@g.us")
        is_community: Set to True if requesting a community's profile picture

    Returns:
        A dictionary containing success status, a message, and the profile picture URL if successful
    """
    success, message, url = whatsapp_get_profile_picture(jid, is_community)

    result = {
        "success": success,
        "message": message
    }

    if url:
        result["url"] = url

    return result

@mcp.tool()
def react_to_message(
    chat_jid: str,
    message_id: str,
    emoji: str,
    from_me: bool,
    sender: Optional[str] = None
) -> Dict[str, Any]:
    """React to a WhatsApp message with an emoji.

    Args:
        chat_jid: The JID of the chat containing the message (e.g., "123456789@s.whatsapp.net" or "123456789@g.us")
        message_id: The ID of the message to react to
        emoji: The emoji to react with (e.g., "👍", "❤️", "😂"). Use empty string to remove reaction.
        from_me: Whether the message being reacted to was sent by you (True) or received (False)
        sender: The sender's JID - required for group chats when reacting to others' messages

    Returns:
        A dictionary containing success status and a status message
    """
    success, message = whatsapp_send_reaction(chat_jid, message_id, emoji, from_me, sender)
    return {
        "success": success,
        "message": message
    }

@mcp.tool()
def edit_message(
    chat_jid: str,
    message_id: str,
    new_content: str
) -> Dict[str, Any]:
    """Edit a WhatsApp message you previously sent.

    Args:
        chat_jid: The JID of the chat containing the message (e.g., "123456789@s.whatsapp.net" or "123456789@g.us")
        message_id: The ID of the message to edit (must be your own message)
        new_content: The new text content for the message

    Returns:
        A dictionary containing success status and a status message
    """
    success, message = whatsapp_edit_message(chat_jid, message_id, new_content)
    return {
        "success": success,
        "message": message
    }

@mcp.tool()
def revoke_message(
    chat_jid: str,
    message_id: str
) -> Dict[str, Any]:
    """Delete a WhatsApp message for everyone (revoke).

    Args:
        chat_jid: The JID of the chat containing the message (e.g., "123456789@s.whatsapp.net" or "123456789@g.us")
        message_id: The ID of the message to delete (must be your own message)

    Returns:
        A dictionary containing success status and a status message
    """
    success, message = whatsapp_revoke_message(chat_jid, message_id)
    return {
        "success": success,
        "message": message
    }

@mcp.tool()
def send_typing_indicator(
    chat_jid: str,
    state: str = "composing"
) -> Dict[str, Any]:
    """Send a typing indicator to a WhatsApp chat.

    Args:
        chat_jid: The JID of the chat (e.g., "123456789@s.whatsapp.net" or "123456789@g.us")
        state: The typing state - "composing" (typing) or "paused" (stopped typing). Defaults to "composing".

    Returns:
        A dictionary containing success status and a status message
    """
    success, message = whatsapp_send_chat_presence(chat_jid, state)
    return {
        "success": success,
        "message": message
    }


@mcp.tool()
def list_labels() -> List[Dict[str, Any]]:
    """List all WhatsApp labels.

    Returns:
        A list of labels with their id, name, color, and order_index
    """
    labels = whatsapp_list_labels()
    return [
        {
            "id": label.id,
            "name": label.name,
            "color": label.color,
            "predefined_id": label.predefined_id,
            "order_index": label.order_index
        }
        for label in labels
    ]


@mcp.tool()
def get_chat_labels(chat_jid: str) -> List[Dict[str, Any]]:
    """Get labels assigned to a specific WhatsApp chat.

    Args:
        chat_jid: The JID of the chat (e.g., "123456789@s.whatsapp.net" or "123456789@g.us")

    Returns:
        A list of labels assigned to the chat
    """
    labels = whatsapp_get_chat_labels(chat_jid)
    return [
        {
            "id": label.id,
            "name": label.name,
            "color": label.color,
            "predefined_id": label.predefined_id,
            "order_index": label.order_index
        }
        for label in labels
    ]


@mcp.tool()
def get_chats_by_label(
    label_id: str,
    limit: int = 20,
    page: int = 0
) -> List[Dict[str, Any]]:
    """Get WhatsApp chats that have a specific label assigned.

    Args:
        label_id: The ID of the label to filter by
        limit: Maximum number of chats to return (default 20)
        page: Page number for pagination (default 0)

    Returns:
        A list of chats with the specified label
    """
    chats = whatsapp_get_chats_by_label(label_id, limit, page)
    return chats


if __name__ == "__main__":
    # Initialize and run the server
    mcp.run(transport='stdio')