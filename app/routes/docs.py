"""
文档路由：提供 docs 目录下 Markdown 文件及根目录 README 的列表和内容读取。
"""

from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException

from app.services.auth import get_current_admin

router = APIRouter(prefix="/api/admin/docs", tags=["docs"])

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
DOCS_DIR = PROJECT_ROOT / "docs"


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
    """收集所有可用的 md 文档：根目录 README + docs 目录下的文件。"""
    files = []

    # 根目录 README.md
    readme = PROJECT_ROOT / "README.md"
    if readme.exists():
        files.append({
            "filename": "README.md",
            "title": _extract_title(readme),
            "source": "root",
        })

    # docs 目录下的 md 文件
    if DOCS_DIR.exists():
        for f in sorted(DOCS_DIR.glob("*.md")):
            files.append({
                "filename": f.name,
                "title": _extract_title(f),
                "source": "docs",
            })

    return files


def _resolve_filepath(filename: str, source: str) -> Path | None:
    """根据 source 解析文件实际路径。"""
    if source == "root":
        return PROJECT_ROOT / filename
    return DOCS_DIR / filename


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
