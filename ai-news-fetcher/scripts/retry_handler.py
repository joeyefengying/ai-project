#!/usr/bin/env python3
"""
retry_handler.py — 统一错误处理和重试机制模块

提供：
1. 网络请求重试装饰器
2. 错误日志记录
3. 错误统计和报告
4. 指数退避策略
"""

import json
import logging
import time
import functools
import traceback
from datetime import datetime
from pathlib import Path
from typing import Callable, Dict, List, Optional, Any
from enum import Enum
import requests

# 配置路径
LOG_PATH = Path(__file__).parent.parent / "logs"
ERROR_LOG_FILE = LOG_PATH / "errors.log"
ERROR_STATS_FILE = LOG_PATH / "error_stats.json"


class ErrorType(Enum):
    """错误类型分类"""
    NETWORK = "network"           # 网络连接错误
    TIMEOUT = "timeout"           # 请求超时
    HTTP_ERROR = "http_error"     # HTTP 错误 (4xx, 5xx)
    PARSE_ERROR = "parse_error"   # 解析错误
    FILE_ERROR = "file_error"     # 文件操作错误
    UNKNOWN = "unknown"           # 未知错误


class RetryHandler:
    """重试处理器"""

    def __init__(
        self,
        max_retries: int = 3,
        base_delay: float = 1.0,
        max_delay: float = 30.0,
        exponential_base: float = 2.0,
        retryable_errors: List[ErrorType] = None
    ):
        """
        初始化重试处理器

        Args:
            max_retries: 最大重试次数
            base_delay: 基础延迟时间（秒）
            max_delay: 最大延迟时间（秒）
            exponential_base: 指数退避基数
            retryable_errors: 可重试的错误类型列表
        """
        self.max_retries = max_retries
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.exponential_base = exponential_base
        self.retryable_errors = retryable_errors or [
            ErrorType.NETWORK,
            ErrorType.TIMEOUT,
            ErrorType.HTTP_ERROR
        ]

        # 确保日志目录存在
        LOG_PATH.mkdir(parents=True, exist_ok=True)

        # 设置日志
        self._setup_logging()

    def _setup_logging(self):
        """配置日志"""
        self.logger = logging.getLogger("retry_handler")
        self.logger.setLevel(logging.INFO)

        if not self.logger.handlers:
            handler = logging.FileHandler(ERROR_LOG_FILE, encoding='utf-8')
            formatter = logging.Formatter(
                '%(asctime)s - %(levelname)s - %(message)s',
                datefmt='%Y-%m-%d %H:%M:%S'
            )
            handler.setFormatter(formatter)
            self.logger.addHandler(handler)

    def classify_error(self, error: Exception) -> ErrorType:
        """
        分类错误类型

        Args:
            error: 异常对象

        Returns:
            ErrorType 枚举值
        """
        error_name = type(error).__name__

        # 网络连接错误
        if error_name in ['ConnectionError', 'ConnectTimeout']:
            return ErrorType.NETWORK

        # 超时错误
        if error_name in ['Timeout', 'ReadTimeout', 'TimeoutError']:
            return ErrorType.TIMEOUT

        # HTTP 错误
        if error_name in ['HTTPError', 'TooManyRedirects']:
            return ErrorType.HTTP_ERROR

        # 解析错误
        if error_name in ['JSONDecodeError', 'ParseError', 'ET.ParseError']:
            return ErrorType.PARSE_ERROR

        # 文件错误
        if error_name in ['FileNotFoundError', 'PermissionError', 'IOError']:
            return ErrorType.FILE_ERROR

        return ErrorType.UNKNOWN

    def calculate_delay(self, retry_count: int) -> float:
        """
        计算指数退避延迟时间

        Args:
            retry_count: 当前重试次数（从1开始）

        Returns:
            延迟时间（秒）
        """
        delay = self.base_delay * (self.exponential_base ** (retry_count - 1))
        return min(delay, self.max_delay)

    def should_retry(self, error_type: ErrorType) -> bool:
        """
        判断是否应该重试

        Args:
            error_type: 错误类型

        Returns:
            是否重试
        """
        return error_type in self.retryable_errors

    def log_error(
        self,
        error: Exception,
        context: str,
        source: str,
        retry_count: int = 0,
        final_failure: bool = False
    ):
        """
        记录错误日志

        Args:
            error: 异常对象
            context: 错误上下文描述
            source: 数据源名称
            retry_count: 重试次数
            final_failure: 是否最终失败
        """
        error_type = self.classify_error(error)

        if final_failure:
            level = logging.ERROR
            msg = f"[{source}] 最终失败: {context} | 类型: {error_type.value} | 重试: {retry_count}次 | 错误: {str(error)}"
        else:
            level = logging.WARNING
            delay = self.calculate_delay(retry_count + 1)
            msg = f"[{source}] 重试 {retry_count}/{self.max_retries}: {context} | 类型: {error_type.value} | 等待: {delay:.1f}s | 错误: {str(error)}"

        self.logger.log(level, msg)

        # 同时更新错误统计
        self._update_stats(error_type, source, final_failure)

    def _update_stats(self, error_type: ErrorType, source: str, final_failure: bool):
        """
        更新错误统计文件

        Args:
            error_type: 错误类型
            source: 数据源
            final_failure: 是否最终失败
        """
        stats = self._load_stats()

        # 更新统计
        key = f"{source}:{error_type.value}"
        if key not in stats:
            stats[key] = {
                "count": 0,
                "final_failures": 0,
                "first_occurrence": datetime.now().isoformat(),
                "last_occurrence": None
            }

        stats[key]["count"] += 1
        stats[key]["last_occurrence"] = datetime.now().isoformat()

        if final_failure:
            stats[key]["final_failures"] += 1

        self._save_stats(stats)

    def _load_stats(self) -> Dict:
        """加载错误统计"""
        if ERROR_STATS_FILE.exists():
            try:
                with open(ERROR_STATS_FILE, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except:
                return {}
        return {}

    def _save_stats(self, stats: Dict):
        """保存错误统计"""
        with open(ERROR_STATS_FILE, 'w', encoding='utf-8') as f:
            json.dump(stats, f, ensure_ascii=False, indent=2)

    def get_stats_report(self) -> str:
        """
        生成错误统计报告

        Returns:
            统计报告文本
        """
        stats = self._load_stats()

        if not stats:
            return "无错误记录"

        report = ["=" * 50, "错误统计报告", "=" * 50, ""]

        # 按来源分组
        by_source = {}
        for key, data in stats.items():
            source, error_type = key.split(':')
            if source not in by_source:
                by_source[source] = []
            by_source[source].append({
                "type": error_type,
                "count": data["count"],
                "failures": data["final_failures"],
                "last": data["last_occurrence"]
            })

        for source, errors in by_source.items():
            report.append(f"\n[{source}]")
            for err in errors:
                report.append(f"  - {err['type']}: {err['count']}次 ({err['failures']}次最终失败)")
                report.append(f"    最后发生: {err['last']}")

        report.append("")
        report.append("=" * 50)

        return "\n".join(report)

    def clear_stats(self):
        """清空错误统计"""
        self._save_stats({})
        self.logger.info("错误统计已清空")


def with_retry(
    max_retries: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 30.0,
    retryable_errors: List[ErrorType] = None
):
    """
    重试装饰器

    Args:
        max_retries: 最大重试次数
        base_delay: 基础延迟
        max_delay: 最大延迟
        retryable_errors: 可重试的错误类型

    Returns:
        装饰后的函数

    使用示例:
        @with_retry(max_retries=3)
        def fetch_url(url):
            return requests.get(url, timeout=10)
    """
    handler = RetryHandler(
        max_retries=max_retries,
        base_delay=base_delay,
        max_delay=max_delay,
        retryable_errors=retryable_errors
    )

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            # 获取 source 参数（如果存在）
            source = kwargs.get('source', args[0] if args else 'unknown')
            context = f"函数: {func.__name__}"

            last_error = None

            for retry_count in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)

                except Exception as e:
                    last_error = e
                    error_type = handler.classify_error(e)

                    if retry_count < max_retries and handler.should_retry(error_type):
                        delay = handler.calculate_delay(retry_count + 1)
                        handler.log_error(e, context, source, retry_count, final_failure=False)
                        time.sleep(delay)
                    else:
                        handler.log_error(e, context, source, retry_count, final_failure=True)
                        raise

            raise last_error

        return wrapper
    return decorator


def safe_request(
    url: str,
    method: str = "GET",
    headers: Dict = None,
    timeout: int = 30,
    max_retries: int = 3,
    source: str = "unknown",
    **kwargs
) -> Optional[requests.Response]:
    """
    安全的网络请求函数（带重试）

    Args:
        url: 请求 URL
        method: HTTP 方法
        headers: 请求头
        timeout: 超时时间
        max_retries: 最大重试次数
        source: 数据源名称（用于日志）
        **kwargs: 其他 requests 参数

    Returns:
        Response 对象或 None

    使用示例:
        resp = safe_request("https://example.com", source="Anthropic")
        if resp:
            content = resp.text
    """
    handler = RetryHandler(max_retries=max_retries)

    headers = headers or {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
    }

    last_error = None

    for retry_count in range(max_retries + 1):
        try:
            resp = requests.request(
                method,
                url,
                headers=headers,
                timeout=timeout,
                **kwargs
            )
            resp.raise_for_status()
            return resp

        except Exception as e:
            last_error = e
            error_type = handler.classify_error(e)

            context = f"请求: {method} {url}"

            if retry_count < max_retries and handler.should_retry(error_type):
                delay = handler.calculate_delay(retry_count + 1)
                handler.log_error(e, context, source, retry_count, final_failure=False)
                time.sleep(delay)
            else:
                handler.log_error(e, context, source, retry_count, final_failure=True)
                return None

    return None


def get_error_handler() -> RetryHandler:
    """获取全局错误处理器实例"""
    return RetryHandler()


def main():
    """测试入口"""
    print("=" * 50)
    print("错误处理和重试机制测试")
    print("=" * 50)
    print()

    handler = RetryHandler()

    # 测试错误分类
    print("[测试] 错误分类:")
    errors = [
        requests.ConnectionError("连接失败"),
        requests.Timeout("请求超时"),
        requests.HTTPError("404 Not Found"),
        json.JSONDecodeError("解析失败", "", 0),
        FileNotFoundError("文件不存在"),
    ]

    for err in errors:
        type_ = handler.classify_error(err)
        print(f"  {type(err).__name__} -> {type_.value}")

    print()
    print("[测试] 指数退避:")
    for i in range(1, 5):
        delay = handler.calculate_delay(i)
        print(f"  重试 {i}: 等待 {delay:.1f}s")

    print()
    print("[测试] 统计报告:")
    print(handler.get_stats_report())

    print()
    print("[测试] safe_request 示例:")
    print("  resp = safe_request('https://example.com', source='Test')")


if __name__ == "__main__":
    main()