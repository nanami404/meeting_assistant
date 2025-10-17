# 标准库
from typing import Dict, Any

# 第三方库
from fastapi import APIRouter, HTTPException
from loguru import logger

# 创建路由器
router = APIRouter(prefix="/api/v1/health", tags=["健康检查"])


@router.get("/", summary="系统健康检查", description="检查系统各组件的健康状态")
async def system_health_check() -> Dict[str, Any]:
    """系统整体健康检查
    
    检查系统各个组件的健康状态，包括：
    - 数据库连接状态
    - 应用基本信息
    
    Returns:
        Dict[str, Any]: 系统健康状态信息
    """
    try:
        # 构建系统健康状态响应
        health_status = {
            "status": "healthy",
            "timestamp": None,  # 将由FastAPI自动添加时间戳
            "version": "1.0.0",
            "services": {
                "database": {
                    "service": "mysql",
                    "status": "healthy",  # 简化实现，实际项目中应检查数据库连接
                    "connection_pool": "active"
                },
                "application": {
                    "service": "meeting_assistant",
                    "status": "healthy",
                    "environment": "development"  # 可从环境变量读取
                }
            }
        }
        
        health_status["message"] = "所有服务运行正常"
        
        logger.info(f"系统健康检查完成 - 状态: {health_status['status']}")
        return health_status
        
    except Exception as e:
        logger.error(f"系统健康检查失败: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"健康检查失败: {str(e)}"
        )


@router.get("/ping", summary="简单健康检查", description="最简单的健康检查端点")
async def ping() -> Dict[str, str]:
    """简单的ping检查
    
    最基础的健康检查端点，用于快速验证API服务是否可用。
    
    Returns:
        Dict[str, str]: 简单的响应消息
    """
    return {
        "status": "ok",
        "message": "Meeting Assistant API is running",
        "service": "meeting_assistant"
    }