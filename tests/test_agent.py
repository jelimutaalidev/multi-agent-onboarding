import pytest

from src.agent import (
    load_image_as_base64,
    get_image_mime_type,
    extract_document_data,
)


class TestLoadImageAsBase64:
    def test_nonexistent_file_raises(self):
        with pytest.raises(FileNotFoundError):
            load_image_as_base64("nonexistent.jpg")


class TestGetImageMimeType:
    def test_jpg(self):
        assert get_image_mime_type("photo.jpg") == "image/jpeg"

    def test_jpeg(self):
        assert get_image_mime_type("photo.jpeg") == "image/jpeg"

    def test_png(self):
        assert get_image_mime_type("photo.png") == "image/png"

    def test_webp(self):
        assert get_image_mime_type("photo.webp") == "image/webp"

    def test_unknown_extension_defaults_to_jpeg(self):
        assert get_image_mime_type("photo.tiff") == "image/jpeg"


class TestExtractDocumentData:
    def test_nonexistent_file_raises(self):
        with pytest.raises(FileNotFoundError):
            extract_document_data("nonexistent.jpg")

    def test_invalid_extension_raises(self, tmp_path):
        f = tmp_path / "test.txt"
        f.write_text("not an image")
        with pytest.raises(ValueError, match="Format file tidak didukung"):
            extract_document_data(str(f))
