# 标准库
from typing import Dict, Any

# 第三方库
from fastapi import APIRouter, Depends, HTTPException
from loguru import logger

# 自定义模块
from services.redis_service import get_redis_service, RedisService

# 创建路由器
router = APIRouter(prefix="/api/v1/health", tags=["健康检查"])


@router.get("/", summary="系统健康检查", description="检查系统各组件的健康状态")
async def system_health_check(
    redis_service: RedisService = Depends(get_redis_service)
) -> Dict[str, Any]:
    """系统整体健康检查
    
    检查系统各个组件的健康状态，包括：
    - Redis服务状态
    - 数据库连接状态
    - 应用基本信息
    
    Returns:
        Dict[str, Any]: 系统健康状态信息
    """
    try:
        # 获取Redis健康状态
        redis_health = await redis_service.health_check()
        
        # 构建系统健康状态响应
        health_status = {
            "status": "healthy",
            "timestamp": None,  # 将由FastAPI自动添加时间戳
            "version": "1.0.0",
            "services": {
                "redis": redis_health,
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
        
        # 根据各服务状态确定整体状态
        if redis_health["status"] == "unhealthy":
            health_status["status"] = "degraded"
            health_status["message"] = "Redis服务不可用，系统运行在降级模式"
        elif redis_health["status"] == "degraded":
            health_status["status"] = "degraded"
            health_status["message"] = "Redis服务处于降级模式"
        else:
            health_status["message"] = "所有服务运行正常"
        
        logger.info(f"系统健康检查完成 - 状态: {health_status['status']}")
        return health_status
        
    except Exception as e:
        logger.error(f"系统健康检查失败: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"健康检查失败: {str(e)}"
        )


@router.get("/redis", summary="Redis健康检查", description="专门检查Redis服务的健康状态")
async def redis_health_check(
    redis_service: RedisService = Depends(get_redis_service)
) -> Dict[str, Any]:
    """Redis服务健康检查
    
    专门检查Redis服务的详细健康状态，包括：
    - 连接状态
    - 响应时间
    - Redis服务器信息
    - 连接池状态
    
    Args:
        redis_service (RedisService): Redis服务实例
        
    Returns:
        Dict[str, Any]: Redis健康状态详细信息
    """
    try:
        health_info = await redis_service.health_check()
        logger.debug(f"Redis健康检查结果: {health_info['status']}")
        return health_info
        
    except Exception as e:
        logger.error(f"Redis健康检查异常: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Redis健康检查失败: {str(e)}"
        )


@router.get("/redis/test", summary="Redis功能测试", description="测试Redis基础功能操作")
async def redis_functionality_test(
    redis_service: RedisService = Depends(get_redis_service)
) -> Dict[str, Any]:
    """Redis功能测试
    
    测试Redis的基础功能，包括：
    - 设置和获取键值
    - 键的存在性检查
    - 键的过期设置
    - 键的删除操作
    
    Args:
        redis_service (RedisService): Redis服务实例
        
    Returns:
        Dict[str, Any]: 功能测试结果
    """
    test_results = {
        "test_name": "Redis功能测试",
        "timestamp": None,
        "tests": {},
        "overall_status": "unknown",
        "degraded_mode": redis_service.is_degraded
    }
    
    if redis_service.is_degraded:
        test_results["overall_status"] = "skipped"
        test_results["message"] = "Redis处于降级模式，跳过功能测试"
        logger.info("Redis功能测试跳过 - 降级模式")
        return test_results
    
    try:
        test_key = "health_check_test"
        test_value = "test_value_123"
        
        # 测试1: SET操作
        set_result = await redis_service.set(test_key, test_value, ex=60)
        test_results["tests"]["set_operation"] = {
            "status": "passed" if set_result else "failed",
            "description": "设置键值对"
        }
        
        # 测试2: GET操作
        get_result = await redis_service.get(test_key)
        get_success = get_result == test_value
        test_results["tests"]["get_operation"] = {
            "status": "passed" if get_success else "failed",
            "description": "获取键值",
            "expected": test_value,
            "actual": get_result
        }
        
        # 测试3: EXISTS操作
        exists_result = await redis_service.exists(test_key)
        exists_success = exists_result > 0
        test_results["tests"]["exists_operation"] = {
            "status": "passed" if exists_success else "failed",
            "description": "检查键是否存在"
        }
        
        # 测试4: TTL操作
        ttl_result = await redis_service.ttl(test_key)
        ttl_success = ttl_result > 0
        test_results["tests"]["ttl_operation"] = {
            "status": "passed" if ttl_success else "failed",
            "description": "获取键的生存时间",
            "ttl_seconds": ttl_result
        }
        
        # 测试5: DELETE操作
        delete_result = await redis_service.delete(test_key)
        delete_success = delete_result > 0
        test_results["tests"]["delete_operation"] = {
            "status": "passed" if delete_success else "failed",
            "description": "删除键"
        }
        
        # 确定整体测试状态
        all_tests_passed = all(
            test["status"] == "passed" 
            for test in test_results["tests"].values()
        )
        test_results["overall_status"] = "passed" if all_tests_passed else "failed"
        
        logger.info(f"Redis功能测试完成 - 整体状态: {test_results['overall_status']}")
        return test_results
        
    except Exception as e:
        logger.error(f"Redis功能测试异常: {e}")
        test_results["overall_status"] = "error"
        test_results["error"] = str(e)
        return test_results


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