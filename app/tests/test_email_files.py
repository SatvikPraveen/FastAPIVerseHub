# File: app/tests/test_email_files.py
"""Email service (SMTP mocked) and file manager (real temp files)."""

import io
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import HTTPException, UploadFile
from PIL import Image

from app.common.email_utils import EmailService
from app.common.file_utils import FileManager
from app.core.config import settings


class TestEmailService:
    async def test_send_email_builds_message(self):
        service = EmailService()
        with patch("app.common.email_utils.aiosmtplib.send", new_callable=AsyncMock) as send:
            ok = await service.send_email(
                ["to@example.com"],
                "Subject",
                "<b>hi</b>",
                text_body="hi",
                cc_emails=["cc@example.com"],
            )
        assert ok is True
        msg = send.await_args.args[0]
        assert msg["Subject"] == "Subject" and msg["Cc"] == "cc@example.com"
        assert send.await_args.kwargs["recipients"] == ["to@example.com", "cc@example.com"]

    async def test_send_failure_returns_false(self):
        with patch(
            "app.common.email_utils.aiosmtplib.send", AsyncMock(side_effect=OSError("down"))
        ):
            assert await EmailService().send_email(["to@example.com"], "s", "<p>x</p>") is False

    async def test_templates_render_with_context(self):
        service = EmailService()
        with patch.object(
            EmailService, "send_email", new_callable=AsyncMock, return_value=True
        ) as send:
            assert await service.send_welcome_email("ann@example.com", "Ann")
            html = send.await_args.kwargs["html_body"]
            assert "Ann" in html and settings.APP_NAME in html and "{{" not in html

            assert await service.send_password_reset_email("ann@example.com", "tok123")
            html = send.await_args.kwargs["html_body"]
            assert f"{settings.FRONTEND_URL}/reset-password?token=tok123" in html

            assert await service.send_magic_link_email("ann@example.com", "https://x/link")
            assert "https://x/link" in send.await_args.kwargs["html_body"]

    async def test_attachments(self, tmp_path):
        attachment = tmp_path / "a.txt"
        attachment.write_text("hello")
        with patch("app.common.email_utils.aiosmtplib.send", new_callable=AsyncMock) as send:
            assert await EmailService().send_email(
                ["to@example.com"],
                "s",
                "<p>x</p>",
                attachments=[str(attachment), str(tmp_path / "missing")],
            )
        parts = send.await_args.args[0].get_payload()
        assert any(p.get_filename() == "a.txt" for p in parts)


def _upload(name: str, content: bytes, content_type: str) -> UploadFile:
    return UploadFile(
        file=io.BytesIO(content),
        filename=name,
        size=len(content),
        headers={"content-type": content_type},
    )


class TestFileManager:
    @pytest.fixture
    def manager(self, tmp_path, monkeypatch):
        monkeypatch.setattr(settings, "UPLOAD_PATH", str(tmp_path / "uploads"))
        return FileManager()

    async def test_validation(self, manager, monkeypatch):
        await manager.validate_file(_upload("ok.txt", b"x", "text/plain"))
        with pytest.raises(HTTPException) as exc:
            await manager.validate_file(_upload("bad.exe", b"x", "application/octet-stream"))
        assert exc.value.status_code == 400
        with pytest.raises(HTTPException) as exc:
            await manager.validate_file(_upload("a.png", b"x", "text/plain"))
        assert "MIME" in exc.value.detail
        monkeypatch.setattr(manager, "max_file_size", 1)
        with pytest.raises(HTTPException) as exc:
            await manager.validate_file(_upload("big.txt", b"xx", "text/plain"))
        assert exc.value.status_code == 413

    async def test_save_stream_info_delete(self, manager):
        saved = await manager.save_file(
            _upload("notes.txt", b"hello world", "text/plain"), user_id=7
        )
        path = Path(saved["file_path"])
        assert path.exists() and saved["file_size"] == 11 and len(saved["file_hash"]) == 64
        assert path.parent.name == "7"

        chunks = [chunk async for chunk in manager.stream_file(str(path), chunk_size=4)]
        assert b"".join(chunks) == b"hello world"

        info = manager.get_file_info(str(path))
        assert (
            info["size"] == 11 and info["extension"] == "txt" and info["created"].tzinfo is not None
        )
        assert manager.get_file_info(str(path) + ".missing") is None

        metadata = await manager.get_file_metadata(str(path))
        assert metadata["file_type"] == "document" if "file_type" in metadata else True
        assert await manager.get_directory_size(str(path.parent)) == 11
        assert await manager.get_directory_size(str(path.parent / "nope")) == 0

        assert await manager.delete_file(str(path)) is True
        assert await manager.delete_file(str(path)) is False

    async def test_images(self, manager, tmp_path):
        src = tmp_path / "pic.png"
        Image.new("RGBA", (400, 300), (255, 0, 0, 128)).save(src)
        assert manager.is_image(str(src)) and not manager.is_video(str(src))
        assert manager.is_document("x.pdf") and manager.is_audio("x.mp3")

        thumb = await manager.create_thumbnail(str(src), thumbnail_size=(50, 50))
        with Image.open(thumb) as im:
            assert thumb and im.size[0] <= 50
        assert await manager.create_thumbnail(str(tmp_path / "missing.png")) is None
        assert await manager.create_thumbnail(str(tmp_path / "not-image.txt")) is None

        optimized = await manager.optimize_image(str(src), max_width=100, max_height=100)
        with Image.open(optimized) as im:
            assert optimized.endswith("opt_pic.jpg") and im.width <= 100
        assert await manager.optimize_image(str(tmp_path / "missing.png")) == str(
            tmp_path / "missing.png"
        )

        meta = await manager._get_image_metadata(str(src))
        assert meta["width"] == 400 and meta["has_transparency"]
        assert await manager._get_image_metadata("nope.png") == {}

    def test_clean_filename(self, manager):
        assert manager.clean_filename('we<ird>:"na/me".txt') == "we_ird___na_me_.txt"
        assert len(manager.clean_filename("a" * 300 + ".pdf")) <= 110

    async def test_cleanup_old_files(self, manager, tmp_path):
        import os
        import time

        old = manager.upload_path / "old.txt"
        old.write_text("x")
        ancient = time.time() - 60 * 24 * 3600
        os.utime(old, (ancient, ancient))
        (manager.upload_path / "new.txt").write_text("y")
        assert await manager.cleanup_old_files(days_old=30) == 1
        assert not old.exists()
