#!/usr/bin/env python3
# -*- coding: UTF-8 -*-
################################################################################
#
# Copyright (c) 2022 Baidu.com, Inc. All Rights Reserved
#
################################################################################

from typing import List, Dict, Any, Optional
import datetime
import time
import copy
import paddle
import numpy as np

from paddlets.logger import Logger
import paddlets.utils.utils as utils

logger = Logger(__name__)


class Callback(object):
    """Abstract base class used to build new callbacks.

    Attributes:
        _trainer(PaddleBaseModel): A model instance.
    """

    def __init__(self):
        pass

    def set_trainer(self, model: "PaddleBaseModel"):
        """Set model instance.

        Args:
            model(PaddleBaseModel): A model instance.
        """
        self._trainer = model

    def on_epoch_begin(self, epoch: int, logs: Optional[Dict[str, Any]]=None):
        """Called at the beginning of each epoch.

        Args:
            epoch(int): The index of epoch.
            logs(Dict[str, Any]|None): The logs is a dict or None.
        """
        pass

    def on_epoch_end(self, epoch: int, logs: Optional[Dict[str, Any]]=None):
        """Called at the end of each epoch.

        Args:
            epoch(int): The index of epoch.
            logs(Dict[str, Any]|None): The logs is a dict or None.
                contains `loss` and `metrics`.
        """
        pass

    def on_batch_begin(self, batch: int, logs: Optional[Dict[str, Any]]=None):
        """Called at the beginning of each batch in training.

        Args:
            batch(int): The index of batch.
            logs(Dict[str, Any]|None): The logs is a dict or None.
        """
        pass

    def on_batch_end(self, batch: int, logs: Optional[Dict[str, Any]]=None):
        """Called at the end of each batch in training.

        Args:
            batch(int): The index of batch.
            logs(Dict[str, Any]|None): The logs is a dict or None. 
                contains `loss` and `batch_size`.
        """
        pass

    def on_train_begin(self, logs: Optional[Dict[str, Any]]=None):
        """Called at the start of training.

        Args:
            logs(Dict[str, Any]|None): The logs is a dict or None.
        """
        pass

    def on_train_end(self, logs: Optional[Dict[str, Any]]=None):
        """Called at the end of training.

        Args:
            logs(Dict[str, Any]|None): The logs is a dict or None. 
        """
        pass


class CallbackContainer(object):
    """Container holding a list of callbacks.

    Args:
        callbacks(List[Callback]): List of callbacks.

    Attributes:
        _callbacks(List[Callback]): List of callbacks.
    """

    def __init__(self, callbacks: List[Callback]):
        self._callbacks = callbacks

    def append(self, callback: Callback):
        """Append callback to the container.

        Args:
            callback(Callback): Callback instance.
        """
        self._callbacks.append(callback)

    def set_trainer(self, model: "PaddleBaseModel"):
        """Set model instance.

        Args:
            model(PaddleBaseModel): A model instance.
        """
        self._trainer = model
        for callback in self._callbacks:
            callback.set_trainer(model)

    def on_epoch_begin(self, epoch: int, logs: Optional[Dict[str, Any]]=None):
        """Called at the beginning of each epoch.

        Args:
            epoch(int): The index of epoch.
            logs(Dict[str, Any]|None): The logs is a dict or None.
        """
        logs = logs or {}
        for callback in self._callbacks:
            callback.on_epoch_begin(epoch, logs)

    def on_epoch_end(self, epoch: int, logs: Optional[Dict[str, Any]]=None):
        """Called at the end of each epoch.

        Args:
            epoch(int): The index of epoch.
            logs(Dict[str, Any]|None): The logs is a dict or None.
                contains `loss` and `metrics`.
        """
        logs = logs or {}
        for callback in self._callbacks:
            callback.on_epoch_end(epoch, logs)

    def on_batch_begin(self, batch: int, logs: Optional[Dict[str, Any]]=None):
        """Called at the beginning of each batch in training.

        Args:
            batch(int): The index of batch.
            logs(Dict[str, Any]|None): The logs is a dict or None.
        """
        logs = logs or {}
        for callback in self._callbacks:
            callback.on_batch_begin(batch, logs)

    def on_batch_end(self, batch: int, logs: Optional[Dict[str, Any]]=None):
        """Called at the end of each batch in training.

        Args:
            batch(int): The index of batch.
            logs(Dict[str, Any]|None): The logs is a dict or None.
                contains `loss` and `batch_size`.
        """
        logs = logs or {}
        for callback in self._callbacks:
            callback.on_batch_end(batch, logs)

    def on_train_begin(self, logs: Optional[Dict[str, Any]]=None):
        """Called at the start of training.

        Args:
            logs(Dict[str, Any]|None): The logs is a dict or None.
        """
        logs = logs or {}
        for callback in self._callbacks:
            callback.on_train_begin(logs)

    def on_train_end(self, logs: Optional[Dict[str, Any]]=None):
        """Called at the end of training.

        Args:
            logs(Dict[str, Any]|None): The logs is a dict or None.
        """
        logs = logs or {}
        for callback in self._callbacks:
            callback.on_train_end(logs)


class EarlyStopping(Callback):
    """EarlyStopping callback, allow the trainer to exit the training loop 
    if the given metric stopped improving during evaluation.

    Args:
        early_stopping_metric(str): Early stopping metric name.
        is_maximize(bool): Whether to maximize or not early_stopping_metric.
        tol(float): Minimum change in monitored value to qualify as improvement.
            This number should be positive.
        patience(int): Number of epochs to wait for improvement before terminating.
            the counter be reset after each improvement

    Attributes:
        _early_stopping_metric(str): Early stopping metric name.
        _is_maximize(bool): Whether to maximize or not early_stopping_metric.
        _tol(float): Minimum change in monitored value to qualify as improvement.
        _patience(int): Number of epochs to wait for improvement before terminating.
        _best_epoch(int): Best epoch.
        _stopped_epoch(int): Stopped epoch.
        _best_loss(float): Best loss.
        _wait(int): Number of times that the early_stopping_metric failed to improve.
    """

    def __init__(self,
                 early_stopping_metric: str,
                 is_maximize: bool,
                 tol: float=0.,
                 patience: int=1):
        super(EarlyStopping, self).__init__()
        self._early_stopping_metric = early_stopping_metric
        self._is_maximize = is_maximize
        self._tol = tol
        self._patience = patience
        self._best_epoch = 0
        self._stopped_epoch = 0
        self._best_weights = None
        self._best_loss = np.inf
        self._wait = 0
        if self._is_maximize:
            self._best_loss = -self._best_loss

    def on_epoch_end(self, epoch: int, logs: Optional[Dict[str, Any]]=None):
        """Called at the end of each epoch.

        Args:
            epoch(int): The index of epoch.
            logs(Dict[str, Any]|None): The logs is a dict or None.
                contains `loss` and `metrics`.
        """
        current_loss = logs.get(self._early_stopping_metric)
        if current_loss is None:
            # raise KeyError(f"{self._early_stopping_metric} is not available, choose in {self._trainer._metrics_names}.")
            return

        loss_change = current_loss - self._best_loss
        max_improved = self._is_maximize and loss_change > self._tol
        min_improved = (not self._is_maximize) and (-loss_change > self._tol)
        if max_improved or min_improved:
            self._best_weights = copy.deepcopy(
                self._trainer._network.state_dict())
            self._best_loss = current_loss
            self._best_epoch = epoch
            self._wait = 0
        else:
            self._wait += 1
            if self._wait >= self._patience:
                self._trainer._stop_training = True
                self._stopped_epoch = epoch

    def on_train_end(self, logs: Optional[Dict[str, Any]]=None):
        """Called at the end of training.

        Args:
            logs(Dict[str, Any]|None): The logs is a dict or None.
        """
        self._trainer._best_epoch = self._best_epoch
        self._trainer._best_cost = self._best_loss
        if self._best_weights is not None:
            self._trainer._network.set_state_dict(self._best_weights)
        if self._stopped_epoch > 0:
            msg = f"\nEarly stopping occurred at epoch {self._stopped_epoch}"
            msg += (
                f" with best_epoch = {self._best_epoch} and " \
                + f"best_{self._early_stopping_metric} = {self._best_loss:.6f}"
            )
            logger.info(msg)
        else:
            msg = (
                f"Stop training because you reached max_epochs = {self._trainer._max_epochs}" \
                + f" with best_epoch = {self._best_epoch} and " \
                + f"best_{self._early_stopping_metric} = {self._best_loss:.6f}"
            )
            logger.info(msg)
        logger.info("Best weights from best epoch are automatically used!")


class History(Callback):
    """Callback that records events into a `History` object.

    Args:
        verbose(int): Print results every verbose iteration.

    Attributes:
        _verbose(int): Print results every verbose iteration.
        _history(Dict[str, Any]): Record all information of metrics of each epoch.
        _start_time(float): Start time of training.
        _epoch_loss(float): Average loss per epoch.
        _epoch_metrics(Dict[str, Any]): Record all information of metrics of each epoch.
        _samples_seen(int): Traversed samples.
    """

    def __init__(self, verbose: int=1):
        super(History, self).__init__()
        self._verbose = verbose

    def on_train_begin(self, logs: Optional[Dict[str, Any]]=None):
        """Called at the start of training.

        Args:
            logs(Dict[str, Any]|None): The logs is a dict or None.
        """
        self._history = {"loss": [], "lr": []}
        self._start_time = logs["start_time"]
        self._epoch_loss = 0.  # nqa

    def on_epoch_begin(self, epoch: int, logs: Optional[Dict[str, Any]]=None):
        """Called at the beginning of each epoch.

        Args:
            epoch(int): The index of epoch.
            logs(Dict[str, Any]|None): The logs is a dict or None.
        """
        self._epoch_metrics = {"loss": 0.}  # nqa
        self._samples_seen = 0.
        self._train_run_cost = 0.
        self._train_reader_cost = 0.

    def on_epoch_end(self, epoch: int, logs: Optional[Dict[str, Any]]=None):
        """Called at the end of each epoch.

        Args:
            epoch(int): The index of epoch.
            logs(Dict[str, Any]|None): The logs is a dict or None.
                contains `loss` and `metrics`.
        """
        self._epoch_metrics["loss"] = self._epoch_loss
        msg = f"[Train] [Epoch {epoch:0>3}]"
        for metric_name, metric_value in self._epoch_metrics.items():
            msg += f", {metric_name:<3}: {metric_value:.6f}"
        logger.info(msg)

    def on_batch_end(self, batch: int, logs: Optional[Dict[str, Any]]=None):
        """Called at the end of each batch in training.

        Args:
            batch(int): The index of batch.
            logs(Dict[str, Any]|None): The logs is a dict or None.
                contains `loss` and `batch_size`.
        """
        # get batch information
        batch_size = logs["batch_size"]
        batch_loss = logs["loss"]
        epoch = logs["epoch"]
        max_epochs = logs["max_epochs"]
        steps = logs["steps"]
        lr = logs["lr"]

        # update average loss of each epoch
        self._epoch_loss = (
            self._samples_seen * self._epoch_loss + batch_size * batch_loss
        ) / (self._samples_seen + batch_size)
        self._samples_seen += batch_size

        # update log information
        msg = f"[Train] [Epoch {epoch}/{max_epochs}], Step: {steps}, lr: {lr:.6f}, loss: {batch_loss:.6f}, samples: {batch_size}"
        reader_cost = logs.get('train_reader_cost', None)
        if reader_cost is not None:
            msg += f", reader_cost: {reader_cost:.6f} sec"
        batch_cost = logs.get('train_run_cost', None)
        if batch_cost is not None:
            ips = batch_size / batch_cost
            msg += f", batch_cost: {batch_cost:.6f} sec, ips: {ips:.6f} sequences/sec"
        max_mem_reserved_str = ""
        max_mem_allocated_str = ""
        if paddle.device.is_compiled_with_cuda() and utils.print_mem_info:
            if paddle.device.cuda.max_memory_reserved() / (1024**2) < 1:
                max_mem_reserved_str = f", max_mem_reserved: {paddle.device.cuda.max_memory_reserved() // 1024} KB"
                max_mem_allocated_str = f", max_mem_allocated: {paddle.device.cuda.max_memory_allocated() // 1024} KB"
            else:
                max_mem_reserved_str = f", max_mem_reserved: {paddle.device.cuda.max_memory_reserved() // (1024 ** 2)} MB"
                max_mem_allocated_str = f", max_mem_allocated: {paddle.device.cuda.max_memory_allocated() // (1024 ** 2)} MB"

        msg += f"{max_mem_reserved_str}{max_mem_allocated_str}"
        total_time = int(time.time() - self._start_time)
        msg += f" | {str(datetime.timedelta(seconds=total_time)) + 's':<6}"
        logger.info(msg)
