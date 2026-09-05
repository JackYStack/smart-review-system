from __future__ import annotations

import io
import posixpath
import zipfile


MAX_DOCX_BYTES = 30 * 1024 * 1024
MAX_UNCOMPRESSED_BYTES = 200 * 1024 * 1024
MAX_ZIP_ENTRIES = 5000
MAX_SINGLE_ENTRY_BYTES = 100 * 1024 * 1024


class UploadValidationError(ValueError):
    pass


def validate_docx_upload(filename: str | None, data: bytes) -> None:
    name = (filename or "").strip()
    if not name.lower().endswith(".docx"):
        raise UploadValidationError("请上传 .docx 文件")
    if not data:
        raise UploadValidationError("上传文件为空")
    if len(data) > MAX_DOCX_BYTES:
        raise UploadValidationError("文件超过30MB限制")
    if not zipfile.is_zipfile(io.BytesIO(data)):
        raise UploadValidationError("文件不是有效的DOCX/OOXML文档")

    try:
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            infos = archive.infolist()
            if len(infos) > MAX_ZIP_ENTRIES:
                raise UploadValidationError("DOCX内部文件数量异常")
            names = {info.filename for info in infos}
            if "[Content_Types].xml" not in names or "word/document.xml" not in names:
                raise UploadValidationError("DOCX缺少必要的OOXML结构")
            total = 0
            for info in infos:
                normalized = posixpath.normpath(info.filename.replace("\\", "/"))
                if normalized == ".." or normalized.startswith("../") or normalized.startswith("/"):
                    raise UploadValidationError("DOCX包含不安全的文件路径")
                if info.file_size > MAX_SINGLE_ENTRY_BYTES:
                    raise UploadValidationError("DOCX内部单个文件过大")
                total += max(0, int(info.file_size))
                if total > MAX_UNCOMPRESSED_BYTES:
                    raise UploadValidationError("DOCX解压后体积超过安全限制")
                if info.compress_size > 0 and info.file_size / info.compress_size > 2000:
                    raise UploadValidationError("DOCX压缩比异常，疑似压缩炸弹")
    except zipfile.BadZipFile as exc:
        raise UploadValidationError("DOCX压缩结构损坏") from exc
