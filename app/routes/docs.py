"""
文档路由：仅提供后台使用文档，不收录发布说明或维护者文档。
"""

from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException

from app.services.auth import get_current_admin

router = APIRouter(prefix="/api/admin/docs", tags=["docs"])

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
DOCS_DIR = PROJECT_ROOT / "docs"

# 新增仓库文档不会自动出现在后台；使用文档在此显式登记。
USER_DOCS = ("使用教程.md", "api-guide.md", "docker-timezone.md")


def _extract_title(filepath: Path) -> str:
    """从 md 文件提取第一个 # 标题，否则用文件名。"""
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line.startswith("# "):
                    return line[2:].strip()
    except Exception:
        pass
    return filepath.stem


def _collect_docs() -> list[dict]:
    """按使用顺序列出已登记且存在的文档。"""
    return [
        {"filename": name, "title": _extract_title(DOCS_DIR / name), "source": "docs"}
        for name in USER_DOCS if (DOCS_DIR / name).is_file()
    ]


def _resolve_filepath(filename: str, source: str) -> Path | None:
    """列表与内容接口共用范围，阻止直接读取未登记的维护文档。"""
    if source != "docs" or filename not in USER_DOCS:
        return None
    path = DOCS_DIR / filename
    if path.resolve().parent != DOCS_DIR.resolve():
        return None
    return path


@router.get("/list")
async def list_docs(admin: dict = Depends(get_current_admin)):
    """返回所有可用的 md 文档列表。"""
    return {"code": 0, "data": _collect_docs()}


@router.get("/content")
async def get_doc_content(
    filename: str,
    source: str = "docs",
    admin: dict = Depends(get_current_admin),
):
    """读取指定 md 文件内容。"""
    # 安全检查：防止路径穿越
    if ".." in filename or "/" in filename or "\\" in filename:
        raise HTTPException(status_code=400, detail="非法文件名")
    if source not in ("root", "docs"):
        raise HTTPException(status_code=400, detail="非法来源")

    filepath = _resolve_filepath(filename, source)
    if filepath is None or not filepath.exists() or filepath.suffix != ".md":
        raise HTTPException(status_code=404, detail="文档不存在")

    content = filepath.read_text(encoding="utf-8")
    return {"code": 0, "data": {"filename": filename, "content": content}}
