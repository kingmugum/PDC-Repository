
from __future__ import annotations

from PySide6.QtCore import QObject, QRunnable, Signal, Slot


class WorkerSignals(QObject):
    success = Signal(str)
    error = Signal(str)
    finished = Signal()


class TaskWorker(QRunnable):
    def __init__(self, task):
        super().__init__()
        self.task = task
        self.signals = WorkerSignals()

    @Slot()
    def run(self):
        try:
            result = self.task()
            self.signals.success.emit(str(result))
        except Exception as exc:
            self.signals.error.emit(str(exc))
        finally:
            self.signals.finished.emit()


class ConnectionWorkerSignals(QObject):
    progress = Signal(int, str)
    success = Signal(str)
    error = Signal(str)
    finished = Signal()


class ConnectionTestWorker(QRunnable):
    def __init__(self, client):
        super().__init__()
        self.client = client
        self.signals = ConnectionWorkerSignals()

    @Slot()
    def run(self):
        try:
            result = self.client.test_connection(
                progress_callback=lambda percent, message: self.signals.progress.emit(int(percent), str(message))
            )
            self.signals.success.emit(str(result))
        except Exception as exc:
            self.signals.error.emit(str(exc))
        finally:
            self.signals.finished.emit()


class PipelineWorkerSignals(QObject):
    stage = Signal(int, str)
    progress = Signal(int, int, str)
    log = Signal(str)
    success = Signal(object)
    error = Signal(str)
    finished = Signal()


class PipelineWorker(QRunnable):
    def __init__(self, task):
        super().__init__()
        self.task = task
        self.signals = PipelineWorkerSignals()
        self.cancel_requested = False

    def cancel(self):
        self.cancel_requested = True

    @Slot()
    def run(self):
        try:
            result = self.task(
                stage_callback=lambda no, title: self.signals.stage.emit(int(no), str(title)),
                progress_callback=lambda overall, current, message: self.signals.progress.emit(int(overall), int(current), str(message)),
                log_callback=lambda message: self.signals.log.emit(str(message)),
                cancel_callback=lambda: self.cancel_requested,
            )
            self.signals.success.emit(result)
        except Exception as exc:
            self.signals.error.emit(str(exc))
        finally:
            self.signals.finished.emit()
