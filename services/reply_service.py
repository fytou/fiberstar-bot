from typing import Optional

def generate_closed_reply_text(closing_note: Optional[str], original_text: Optional[str]) -> str:
    """
    Creates a copy-ready response formatted for Fiberstar WhatsApp group:
    <catatan teknisi di baris paling atas>
    <teks tiket asli>
    """
    note = (closing_note or "Back To Normal").strip()
    orig = (original_text or "").strip()

    if orig:
        return f"{note}\n{orig}"
    return note
