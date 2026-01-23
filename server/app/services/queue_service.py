"""请求队列管理服务

用于串行处理 TTS 请求，避免 GPU 显存溢出。
"""

import asyncio
import logging
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Callable, Coroutine, Dict, Optional

logger = logging.getLogger(__name__)


@dataclass
class QueueItem:
    """队列项"""
    request_id: str
    task: Callable[[], Coroutine[Any, Any, Any]]
    future: asyncio.Future
    created_at: float = field(default_factory=time.time)


class TTSQueue:
    """TTS 请求队列管理器

    确保 GPU 推理请求串行执行，避免并发导致的显存溢出。
    """

    def __init__(
        self,
        max_queue_size: int = 50,
        request_timeout: float = 300,  # 5分钟
        avg_process_time: float = 15,  # 预估每个请求处理时间
    ):
        """
        初始化队列

        Args:
            max_queue_size: 最大队列长度
            request_timeout: 单个请求超时时间（秒）
            avg_process_time: 预估平均处理时间（秒）
        """
        self.max_queue_size = max_queue_size
        self.request_timeout = request_timeout
        self.avg_process_time = avg_process_time

        self._queue: asyncio.Queue[QueueItem] = asyncio.Queue(maxsize=max_queue_size)
        self._processing = False
        self._worker_task: Optional[asyncio.Task] = None
        self._current_request_id: Optional[str] = None
        self._stats: Dict[str, Any] = {
            "total_processed": 0,
            "total_failed": 0,
            "total_timeout": 0,
        }

    @property
    def queue_length(self) -> int:
        """当前队列长度"""
        return self._queue.qsize()

    @property
    def is_full(self) -> bool:
        """队列是否已满"""
        return self._queue.full()

    def estimated_wait_time(self, position: int) -> float:
        """预估等待时间"""
        return position * self.avg_process_time

    async def start(self) -> None:
        """启动队列处理器"""
        if self._worker_task is None or self._worker_task.done():
            self._worker_task = asyncio.create_task(self._process_queue())
            logger.info("队列处理器已启动")

    async def stop(self) -> None:
        """停止队列处理器"""
        if self._worker_task and not self._worker_task.done():
            self._worker_task.cancel()
            try:
                await self._worker_task
            except asyncio.CancelledError:
                pass
            logger.info("队列处理器已停止")

    async def submit(
        self,
        task: Callable[[], Coroutine[Any, Any, Any]],
        request_id: Optional[str] = None,
    ) -> tuple[Any, int]:
        """
        提交任务到队列

        Args:
            task: 异步任务函数
            request_id: 请求ID（可选）

        Returns:
            (任务结果, 队列位置)

        Raises:
            asyncio.QueueFull: 队列已满
            asyncio.TimeoutError: 请求超时
        """
        if request_id is None:
            request_id = str(uuid.uuid4())

        if self._queue.full():
            raise asyncio.QueueFull("服务繁忙，请稍后重试")

        future: asyncio.Future = asyncio.Future()
        item = QueueItem(request_id=request_id, task=task, future=future)

        # 非阻塞入队
        try:
            self._queue.put_nowait(item)
        except asyncio.QueueFull:
            raise asyncio.QueueFull("服务繁忙，请稍后重试")

        position = self._queue.qsize()
        logger.info(f"请求 {request_id} 已入队, 位置={position}")

        # 确保处理器在运行
        await self.start()

        # 等待结果（带超时）
        try:
            # 超时控制在 worker 侧执行，submit 侧只等待结果。
            # 这样可以避免“HTTP 已超时返回，但后台仍在跑卡死任务”导致队列被拖死。
            result = await future
            return result, position
        except asyncio.TimeoutError:
            self._stats["total_timeout"] += 1
            logger.warning(f"请求 {request_id} 超时")
            raise

    async def _process_queue(self) -> None:
        """处理队列（后台任务）"""
        self._processing = True
        logger.info("开始处理队列")

        while True:
            try:
                # 等待队列项
                item = await self._queue.get()
                self._current_request_id = item.request_id

                # 检查是否已超时
                elapsed = time.time() - item.created_at
                if elapsed > self.request_timeout:
                    logger.warning(f"请求 {item.request_id} 在队列中等待超时，跳过")
                    if not item.future.done():
                        item.future.set_exception(
                            asyncio.TimeoutError("请求在队列中等待超时")
                        )
                    self._queue.task_done()
                    continue

                logger.info(f"开始处理请求 {item.request_id}")
                start_time = time.time()

                try:
                    # 重要：在 worker 侧对实际执行做超时控制。
                    # 如果底层推理引擎卡死，这里能保证队列恢复继续处理后续请求。
                    result = await asyncio.wait_for(
                        item.task(), timeout=self.request_timeout
                    )
                    if not item.future.done():
                        item.future.set_result(result)
                    self._stats["total_processed"] += 1

                    # 更新平均处理时间（指数移动平均）
                    process_time = time.time() - start_time
                    self.avg_process_time = (
                        0.8 * self.avg_process_time + 0.2 * process_time
                    )

                except asyncio.TimeoutError:
                    self._stats["total_timeout"] += 1
                    logger.warning(f"处理请求 {item.request_id} 超时")
                    if not item.future.done():
                        item.future.set_exception(
                            asyncio.TimeoutError("请求处理超时")
                        )

                except Exception as e:
                    logger.exception(f"处理请求 {item.request_id} 失败: {e}")
                    if not item.future.done():
                        item.future.set_exception(e)
                    self._stats["total_failed"] += 1

                finally:
                    self._current_request_id = None
                    self._queue.task_done()

            except asyncio.CancelledError:
                logger.info("队列处理器被取消")
                break
            except Exception as e:
                logger.exception(f"队列处理器异常: {e}")
                await asyncio.sleep(1)

        self._processing = False

    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        return {
            **self._stats,
            "queue_length": self.queue_length,
            "max_queue_size": self.max_queue_size,
            "avg_process_time": self.avg_process_time,
            "current_request": self._current_request_id,
        }
