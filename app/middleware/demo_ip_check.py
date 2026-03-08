"""
Demo 模式 IP 白名单中间件

在 Demo 模式下，限制特定接口只允许白名单 IP 访问：
- POST /xpay/epay/mapi.php (支付接口)
- /xpay/epay/callback.php (回调接口)
"""

from fastapi import Request, HTTPException
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

from app.services.auth import is_demo_mode, is_ip_allowed


class DemoIPCheckMiddleware(BaseHTTPMiddleware):
    """Demo 模式下的 IP 白名单检查中间件"""
    
    # 需要 IP 白名单保护的路径
    PROTECTED_PATHS = [
        "/xpay/epay/mapi.php",
        "/xpay/epay/callback.php",
    ]
    
    async def dispatch(self, request: Request, call_next):
        # 只在 Demo 模式下检查
        if not is_demo_mode():
            return await call_next(request)
        
        # 检查是否是受保护的路径
        path = request.url.path
        is_protected = any(path.startswith(p) or path == p for p in self.PROTECTED_PATHS)
        
        if is_protected:
            # 获取客户端 IP
            client_ip = request.client.host if request.client else "unknown"
            
            # 检查 IP 是否在白名单中
            if not is_ip_allowed(client_ip):
                return Response(
                    content=f"Demo 模式下此接口仅允许白名单 IP 访问 (当前 IP: {client_ip})",
                    status_code=403,
                    media_type="text/plain"
                )
        
        # 继续处理请求
        return await call_next(request)
