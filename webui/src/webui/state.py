from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import reflex as rx
from reflex.event import EventSpec


class AuthState(rx.State):
    """Session-based authentication state."""

    is_authenticated: bool = False
    user_email: str = ""

    @rx.var
    def login_disabled(self) -> bool:
        """Check if login is disabled via env var."""
        return os.getenv("GENOBEAR_LOGIN", "false").lower() == "none"

    def login(self, form_data: dict[str, Any]) -> EventSpec:
        """Set the session auth flag."""
        login_config = os.getenv("GENOBEAR_LOGIN", "false").lower()
        
        email_raw = form_data.get("email")
        password_raw = form_data.get("password")
        email = (str(email_raw) if email_raw is not None else "").strip()
        password = (str(password_raw) if password_raw is not None else "").strip()

        if not email:
            return rx.toast.error("Email is required")

        # Handle restricted login if GENOBEAR_LOGIN=user:pass
        if login_config != "false" and ":" in login_config:
            valid_user, valid_pass = login_config.split(":", 1)
            if email != valid_user or password != valid_pass:
                return rx.toast.error("Invalid credentials")

        self.is_authenticated = True
        self.user_email = email
        return rx.toast.success(f"Welcome, {email}!")

    def logout(self) -> EventSpec:
        self.is_authenticated = False
        self.user_email = ""
        return rx.toast.info("Logged out")


class UploadState(rx.State):
    """Handle VCF uploads."""

    uploading: bool = False
    files: list[str] = []

    async def handle_upload(self, files: list[rx.UploadFile]):
        """Handle the upload of VCF files."""
        self.uploading = True
        yield

        # Create data/input if it doesn't exist
        upload_dir = Path("data/input")
        upload_dir.mkdir(parents=True, exist_ok=True)

        for file in files:
            if file.filename:
                # Save the file to data/input
                content = await file.read()
                file_path = upload_dir / file.filename
                with open(file_path, "wb") as f:
                    f.write(content)
                self.files.append(file.filename)

        self.uploading = False
        yield rx.toast.success(f"Uploaded {len(files)} files")
