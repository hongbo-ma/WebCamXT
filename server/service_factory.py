"""
ComputeService 工厂: 按需重建 + 内存 LRU 缓存 + 按文件加锁
替代原全局变量 current_service, 实现多用户隔离

说明:
- 缓存的 Service 实例是共享的, 而仿真接口会修改实例字段
  (M / phi_tail / Ntail_eff / coeffs 等), 因此所有会触达 Service
  的读写都必须通过 locked_service() 以文件为粒度串行化,
  否则同一文件的并发请求会互相污染状态。
- 锁必须在获取 Service 之前取得, 保证 "加锁 -> 取缓存/重建" 的原子性。
"""
import threading
from contextlib import contextmanager

from compute_service import ComputeService

_lock = threading.Lock()
_cache = {}
_file_locks = {}
_CACHE_MAX = 20


def _get_file_lock(file_id):
    with _lock:
        if file_id not in _file_locks:
            _file_locks[file_id] = threading.Lock()
        return _file_locks[file_id]


def _evict_oldest():
    if len(_cache) >= _CACHE_MAX:
        oldest_key = next(iter(_cache))
        _cache.pop(oldest_key, None)


def get_service(file_id, file_path):
    with _lock:
        if file_id in _cache:
            return _cache[file_id]
        service = ComputeService()
        service._set_compute_file(file_path)
        _evict_oldest()
        _cache[file_id] = service
        return service


@contextmanager
def locked_service(file_id, file_path):
    """以文件为粒度加锁地获取 Service, with 期间独占该文件的计算状态"""
    with _get_file_lock(file_id):
        yield get_service(file_id, file_path)


def invalidate(file_id):
    with _lock:
        _cache.pop(file_id, None)
        _file_locks.pop(file_id, None)


def set_cached_service(file_id, service):
    with _lock:
        _evict_oldest()
        _cache[file_id] = service


def invalidate_user(user_id, file_records):
    with _lock:
        for record in file_records:
            _cache.pop(record.id, None)
            _file_locks.pop(record.id, None)
