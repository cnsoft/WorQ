"""In-memory queue broker, normally used for testing."""
import logging
from pymq.core import AbstractMessageQueue, AbstractResultStore, DEFAULT
from Queue import Queue
from weakref import WeakValueDictionary, WeakKeyDictionary

log = logging.getLogger(__name__)

_REFS = WeakValueDictionary()

def _get_ref(key, cls, url, *args, **kw):
    obj = _REFS.get((url, key))
    if obj is None:
        obj = _REFS[(url, key)] = cls(url, *args, **kw)
    return obj

class MemoryQueue(AbstractMessageQueue):
    """Simple in-memory message queue implementation

    Does not support named queues.
    """

    @classmethod
    def factory(*args, **kw):
        return _get_ref('queue', *args, **kw)

    def __init__(self, *args, **kw):
        super(MemoryQueue, self).__init__(*args, **kw)
        if self.queues != [DEFAULT]:
            log.warn('MemoryQueue does not support named queues')
        self.queue = Queue()

    def __iter__(self):
        while True:
            yield self.queue.get()

    def enqueue_task(self, queue, message):
        self.queue.put((queue, message))


class MemoryResults(AbstractResultStore):
    # this result store is not thread-safe

    @classmethod
    def factory(*args, **kw):
        return _get_ref('results', *args, **kw)

    def __init__(self, *args, **kw):
        super(MemoryResults, self).__init__(*args, **kw)
        self.results_by_task = WeakValueDictionary()
        self.results = WeakKeyDictionary()

    def deferred_result(self, task_id):
        result = self.results_by_task.get(task_id)
        if result is None:
            result = super(MemoryResults, self).deferred_result(task_id)
            self.results_by_task[task_id] = result
        return result

    def set_result(self, task_id, message, timeout):
        result_obj = self.results_by_task[task_id]
        self.results[result_obj] = message

    def pop_result(self, task_id):
        result_obj = self.results_by_task[task_id]
        return self.results.pop(result_obj, None)

    def update(self, taskset_id, num, message, timeout):
        # not thread-safe
        result = self.deferred_result(taskset_id)
        key = getattr(result, 'taskset_results_key', None)
        if key is None:
            key = type('TaskSet-%s' % taskset_id, (object,), {})
            result.taskset_results_key = key
        value = self.results.setdefault(key, [])
        value.append(message)
        if len(value) == num:
            return self.results.pop(key)
