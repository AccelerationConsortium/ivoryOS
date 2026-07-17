import threading

from ivoryos.runtime.runner_runtime import ensure_deck


class ScriptRunnerQueueMixin:
    def handle_input_submission(self, value):
        """Resume execution with user input"""
        if self.waiting_for_input:
            self.input_value = value
            self.pause_event.set()
            return True
        return False

    def toggle_pause(self):
        """Toggles between pausing and resuming the script"""
        if self.paused or self.queue_paused:
            self.paused = False
            self.queue_paused = False
            self.pause_event.set()  # Resume the script
            if self.logger:
                self.logger.info('Resume script')
            if self.socketio:
                self.socketio.emit('pause_status', {'paused': False})
            self._process_queue()
            return "Resumed"
        else:
            self.paused = True
            self.queue_paused = True
            if self.logger:
                self.logger.info('Pause script')
            self.pause_event.clear()  # Pause the script
            if self.socketio:
                self.socketio.emit('pause_status', {'paused': True})
            return "Paused"

    def pause_status(self):
        """Toggles between pausing and resuming the script"""
        return self.paused or self.queue_paused

    def reset_stop_event(self):
        """Resets the stop event"""
        self.stop_pending_event.clear()
        self.stop_current_event.clear()
        self.stop_cleanup_event.clear()
        self.pause_event.set()

    def get_queue_status(self):
        """Returns the current queue status"""
        queue_status = []
        for i, task in enumerate(self.execution_queue):
            # Basic info
            info = {
                "id": i,
                "name": task.get("run_name", "untitled"),
                "status": "pending",
                "args": f"{task.get('repeat_count', 1)} iteration(s)" if not task.get('config') else f"Config: {len(task.get('config'))} entries"
            }
            
            # Add detailed info for the modal
            details = {}
            if task.get("repeat_count"):
                details["Mode"] = "Repeated Execution"
                details["Repeat Count"] = task.get("repeat_count")
            
            if task.get("config"):
                details["Mode"] = "Configuration List"
                config_data = task.get("config")
                details["Config Entries"] = len(config_data)
                # Show a preview of the first 5 entries to avoid sending too much data
                details["Config Preview (First 5)"] = config_data[:5]
                # If it's a list of dicts, maybe show the first one or just say it's a list
                # For CSV loaded configs, it is a list of dicts
            
            if task.get("batch_size"):
                details["Batch Size"] = task.get("batch_size")
                
            if task.get("history"):
                 details["History File"] = task.get("history")

            # Optimization details
            if task.get("optimizer_cls"):
                details["Mode"] = "Bayesian Optimization"
                details["Optimizer"] = task.get("optimizer_cls").__name__
                
            if task.get("objectives"):
                details["Objectives"] = task.get("objectives")
                
            if task.get("parameters"):
                details["Parameters"] = task.get("parameters")
                
            if task.get("constraints"):
                details["Constraints"] = task.get("constraints")
                
            if task.get("additional_params"):
                details["Additional Params"] = task.get("additional_params")

            info["details"] = details
            
            # Use display_name if available for the main "name" field
            if task.get("display_name"):
                 info["name"] = task.get("display_name")
                 details["Run Name"] = task.get("run_name") # Keep internal name in details
                 
            queue_status.append(info)

        return queue_status

    def get_current_task_details(self):
        """Returns the full details for the currently executing task"""
        try:
            if self.current_task:
                task = self.current_task
                details = {}
                if task.get("repeat_count"):
                    details["Mode"] = "Repeated Execution"
                    details["Repeat Count"] = task.get("repeat_count")

                if task.get("config"):
                    details["Mode"] = "Configuration List"
                    details["Config Entries"] = len(task.get("config"))
                    details["Full Config"] = task.get("config")

                if task.get("batch_size"):
                    details["Batch Size"] = task.get("batch_size")

                if task.get("history"):
                    details["History File"] = task.get("history")

                # Optimization details
                if task.get("optimizer_cls"):
                    details["Mode"] = "Bayesian Optimization"
                    details["Optimizer"] = task.get("optimizer_cls").__name__

                if task.get("objectives"):
                    details["Objectives"] = task.get("objectives")

                if task.get("parameters"):
                    details["Parameters"] = task.get("parameters")

                if task.get("constraints"):
                    details["Constraints"] = task.get("constraints")

                if task.get("additional_params"):
                    details["Additional Params"] = task.get("additional_params")

                return details
        except Exception as e:
            if self.logger:
                self.logger.error(f"Error getting current task details: {e}")
        return None

    def get_task_details(self, task_index):
        """Returns the full details for a specific task"""
        try:
            task_index = int(task_index)
            if 0 <= task_index < len(self.execution_queue):
                task = self.execution_queue[task_index]
                details = {}
                details["Task Name"] = task.get("display_name") or task.get("run_name", "untitled")
                if task.get("repeat_count"):
                    details["Mode"] = "Repeated Execution"
                    details["Repeat Count"] = task.get("repeat_count")
                
                if task.get("config"):
                    details["Mode"] = "Configuration List"
                    details["Config Entries"] = len(task.get("config"))
                    # Return full config here
                    details["Full Config"] = task.get("config")
                
                if task.get("batch_size"):
                    details["Batch Size"] = task.get("batch_size")
                    
                if task.get("history"):
                     details["History File"] = task.get("history")

                # Optimization details
                if task.get("optimizer_cls"):
                    details["Mode"] = "Bayesian Optimization"
                    details["Optimizer"] = task.get("optimizer_cls").__name__
                    
                if task.get("objectives"):
                    details["Objectives"] = task.get("objectives")
                    
                if task.get("parameters"):
                    details["Parameters"] = task.get("parameters")
                    
                if task.get("constraints"):
                    details["Constraints"] = task.get("constraints")
                    
                if task.get("additional_params"):
                    details["Additional Params"] = task.get("additional_params")
                    
                return details
        except Exception as e:
            if self.logger:
                self.logger.error(f"Error getting task details: {e}")
        return None

    def update_task_name(self, task_index, new_name):
        """Updates the display name of a task in the queue"""
        try:
            task_index = int(task_index)
            if 0 <= task_index < len(self.execution_queue):
                task = self.execution_queue[task_index]
                task["display_name"] = new_name
                if self.logger:
                    self.logger.info(f"Updated task {task_index} name to: {new_name}")
                self._emit_queue_status()
                return True
        except Exception as e:
            if self.logger:
                self.logger.error(f"Error updating task name: {e}")
        return False

    def remove_task(self, task_index):
        """Removes a task from the queue"""
        try:
            task_index = int(task_index)
            if 0 <= task_index < len(self.execution_queue):
                task = self.execution_queue.pop(task_index)
                if self.logger:
                    self.logger.info(f"Removed task from queue: {task.get('run_name')}")
                self._emit_queue_status()
                return True
        except Exception as e:
            if self.logger:
                self.logger.error(f"Error removing task: {e}")
        return False

    def reorder_tasks(self, task_index, direction):
        """Reorder tasks in the queue"""
        try:
            task_index = int(task_index)
            if direction == "up" and task_index > 0:
                self.execution_queue[task_index], self.execution_queue[task_index - 1] = \
                    self.execution_queue[task_index - 1], self.execution_queue[task_index]
                self._emit_queue_status()
                return True
            elif direction == "down" and task_index < len(self.execution_queue) - 1:
                self.execution_queue[task_index], self.execution_queue[task_index + 1] = \
                    self.execution_queue[task_index + 1], self.execution_queue[task_index]
                self._emit_queue_status()
                return True
        except Exception as e:
            if self.logger:
                self.logger.error(f"Error reordering tasks: {e}")
        return False


    def abort_pending(self, continue_queue=True):
        """Abort the pending iteration after the current is finished"""
        self.stop_pending_event.set()
        if self.logger:
            self.logger.info("Abort pending tasks")
            
        has_pending = len(self.execution_queue) > 0
        if not continue_queue and has_pending:
            self.queue_paused = True
            if self.socketio:
                self.socketio.emit('pause_status', {'paused': True})
        else:
            self.queue_paused = False
            # self.paused = False
            if not self.pause_event.is_set():
                self.pause_event.set()
            if self.socketio:
                self.socketio.emit('pause_status', {'paused': False})

    def abort_cleanup(self):
        """Abort the pending iteration after the current is finished"""
        self.stop_cleanup_event.set()
        self.logger.info("Abort cleanup")

    def stop_execution(self, continue_queue=True):
        """Force stop everything, including ongoing tasks."""
        if self.logger:
            self.logger.info("Stop execution")
        self.stop_current_event.set()
        self.abort_pending()
        self.abort_cleanup()
        
        has_pending = len(self.execution_queue) > 0
        if continue_queue or not has_pending:
            self.queue_paused = False
            # self.paused = False
            if not self.pause_event.is_set():
                self.pause_event.set()
            if self.socketio:
                self.socketio.emit('pause_status', {'paused': False})
        else:
            self.queue_paused = True
            if self.socketio:
                self.socketio.emit('pause_status', {'paused': True})


    def run_script(self, script, repeat_count=1, run_name=None, logger=None, socketio=None, config=None,
                   output_path="", compiled=False, current_app=None, history=None, optimizer=None, batch_mode=None,
                   batch_size=1, objectives=None, parameters=None, constraints=None, steps=None, optimizer_cls=None,
                   additional_params=None, on_start=None, display_name=None):


        self.socketio = socketio
        self.logger = logger
        ensure_deck()

        # print("history", history)
        if self.current_app is None:
            self.current_app = current_app
        # time.sleep(1)  # Optional: may help ensure deck readiness

        
        # Clear residual config for simple repeat runs, but preserve it for 
        # Bayesian optimization which might use both repeat_count and config in the future
        if repeat_count and not optimizer_cls and not optimizer:
            config = None

        task = {
            "script": script,
            "repeat_count": repeat_count,
            "run_name": run_name,
            "config": config,
            "output_path": output_path,
            "current_app": current_app,
            "compiled": compiled,
            "history": history,
            "optimizer": optimizer,
            "batch_mode": batch_mode,
            "batch_size": batch_size,
            "objectives": objectives,
            "parameters": parameters,
            "constraints": constraints,
            "steps": steps,
            "optimizer_cls": optimizer_cls,
            "additional_params": additional_params,
            "on_start": on_start,
            "display_name": display_name
        }
        # handle status when workflow queued during single task execution
        was_busy = self.lock.locked() or self.queue_paused
        self.execution_queue.append(task)
        self._emit_queue_status()
        if self.logger:
            self.logger.info(f"Added task to queue: {run_name}")

        if not was_busy:
            # Start immediately when the runner is idle.
            self.paused = False
            self.queue_paused = False
            self.pause_event.set()
            if self.socketio:
                self.socketio.emit('pause_status', {'paused': False})
            
        return self._process_queue()
        
    def _emit_busy_status(self):
        """Emit the current execution busy status to frontend"""
        if self.socketio:
            self.socketio.emit('busy_status', {
                'is_running': self.lock.locked(),
                'queue_length': len(self.execution_queue),
                'paused': self.paused or self.queue_paused
            })

    def _emit_queue_status(self):
        """Emit the current queue to frontend"""
        if self.socketio:
            self.socketio.emit('queue_status', self.get_queue_status())

    def _process_queue(self):
        """Process the next task in the queue if the runner is free"""
        # Try to acquire lock without blocking
        if not self.lock.acquire(blocking=False):
            self._emit_busy_status()
            return "queued"

        if not self.execution_queue:
            self.lock.release()
            return "empty"
            
        if self.paused or self.queue_paused:
            self.lock.release()
            return "paused"
            
        # Get next task
        task = self.execution_queue.pop(0)
        self._emit_queue_status()
        self.current_task = task # Store current task details
        # todo should check if stop event was set and then check with user to make sure
        #  they want to continue with the queue or abort or pause the queue? in case they need to
        #  manually fix something before continuing
        self.reset_stop_event()

        thread = threading.Thread(
            target=self._run_with_stop_check,
            kwargs=task
        )
        self._emit_busy_status()
        thread.start()
        return thread
