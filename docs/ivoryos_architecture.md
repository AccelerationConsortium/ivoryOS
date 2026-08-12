# IvoryOS Architecture and Features Documentation

This document outlines the core features, architecture, and behavior of the current IvoryOS repository. It is intended to serve as a comprehensive reference for modernizing or migrating the application to a new technology stack. 

> [!NOTE]
> IvoryOS is currently built as a Flask application, heavily relying on server-side rendering, session states, and SQLAlchemy for persistence. This documentation abstracts the code implementation to focus on features and workflows that need to be supported in a modernized architecture.

---

## 1. Introspection and Type Support

The system uses Python's `inspect` module to dynamically parse the signatures, arguments, and docstrings of instrument/hardware classes (often referred to as "decks" or "modules"). This introspection forms the backbone of the dynamic UI generation, ensuring the interface always matches the hardware's Python API.

### Supported Types & Features
* **Standard Python Types**: `int`, `float`, `str`, `bool`, `list`, `dict`, `tuple`.
* **Advanced Typing**: `Optional`, `Union`.
* **Enums**: Supported and parsed by resolving the module name and Enum class name (e.g., `Enum:module.MyEnum`). This allows the UI to render dropdowns with fixed options.
* **Literals**: Handled via `typing.Literal` (e.g., `Literal:val1,val2`). Translates nicely to select inputs or constrained choices on the frontend.
* **Return Types**: Parsed and categorized into `scalar`, `tuple` (with arity detection), `dict`, or `none`.

### Unsupported Features
* **File/Stream Objects**: Parameter types like `BinaryIO`, `TextIO`, `BytesIO`, or `typing.IO` are explicitly flagged as incompatible and skipped during introspection.

### Output Generation
* The introspection engine outputs an "Interface Schema" (`interface_schema`) and "Building Blocks" (`building_blocks`), caching them (sometimes as pickled `.pkl` files for offline mode) or providing them directly to the control routes to auto-generate forms.

---

## 2. Workflow Engine & Execution Assumptions

The workflow engine executes experiments (scripts) in a structured, phased manner. It supports complex control flows and nested loops over hardware operations.

### Workflow Phases
A workflow script execution is strictly divided into three phases:
1. **Prep Phase**: Runs exactly once at the beginning of the experiment (e.g., initializing instruments, homing robots, opening valves).
2. **Main (Script) Phase**: The core logic that gets executed. Depending on the configuration, this phase can repeat multiple times.
3. **Cleanup Phase**: Runs exactly once at the end of the experiment (e.g., shutting off heaters, flushing lines, closing connections). *Note: The system supports an optional flag to skip the cleanup phase if the user manually aborts early.*

### Driven Config Modes
The Main Phase repeats based on three different driving mechanisms (`repeat_mode`):

1. **Standard Repeat**: Executes the script a static `repeat_count` number of times.
2. **CSV-Driven (Batch) Config**: 
   * A configuration (often uploaded as CSV) is passed into the engine. 
   * The config is chunked by `batch_size`.
   * Each batch iteration feeds a set of parameters (`kwargs_list`) to the Main Phase.
   * Useful for high-throughput screening where predefined parameter sets are run sequentially.
3. **BO-Driven (Optimizer) Config**: 
   * Driven by Bayesian Optimization (BO) via `bo_campaign.py`.
   * The user defines **Parameters** (ranges, choices, fixed), **Objectives** (minimize/maximize, weights), and **Configuration Steps** (model, sample sizes) via a dynamic form.
   * Instead of a static list, the `optimizer.suggest()` method dynamically provides parameters.
   * After execution, the results are fed back using `optimizer.observe()`, allowing the engine to pick the next best parameters intelligently.
   * Supports early stopping based on objective thresholds.

---

## 3. Detailed Logging and Data Records

IvoryOS maintains extensive execution records for auditing, querying, and post-analysis.

### Database Hierarchy
* **`WorkflowRun`**: Represents the entire experiment. Tracks `name`, `platform`, `start_time`, `end_time`, `repeat_mode`, and the `data_path` (associated CSV/log file).
* **`WorkflowPhase`**: Represents a specific phase (`prep`, `main`, `cleanup`) within a run. Tracks the iteration index (`repeat_index`), parameters used for that iteration, outputs returned, and start/end times.
* **`WorkflowStep`**: Represents individual function calls made during a phase, capturing method name, run errors, outputs, and timestamps.
* **`SingleStep`**: Similar to `WorkflowStep`, but used for ad-hoc, manual commands executed directly from the Control Panel.

### File Logging
* Each `WorkflowRun` spins up a dedicated `logging.FileHandler`. 
* Logs are saved under a specific `LOG_FOLDER` formatted as `{run_name}_{YYYY-MM-DD HH-MM-SS}.log`.
* This ensures that every automated run has a fully isolated text log of system stdout, warnings, and errors separate from the main application server logs.
* Outputs are often compiled and written to an associated CSV file, allowing users to track the history of data generated by the campaign.

---

## 4. Library System

The Library is the centralized repository for managing workflow scripts.

* **Database Storage**: Scripts are saved to the database (via the `Script` model), tracking metadata like author, creation/modification times, deck association, and status.
* **Query and Filter**: Supports filtering by deck name, searching by keyword, and sorting by attributes (name, status, modified time).
* **Versioning & Protection**: 
   * Scripts marked as "finalized" are protected from direct edits.
   * Users can only edit scripts they authored.
   * "Save As" functionality allows users to fork or duplicate a script, establishing a new copy under their authorship.
* **Global Registration**: Scripts can be flagged as `registered`, exposing them as accessible workflows across different parts of the system.

---

## 5. Control Panel & Direct Interaction

The Control Panel provides real-time, manual interaction with the hardware ("instruments") independent of automated workflows.

* **Dynamic Forms**: Based on the introspection layer, the control panel automatically renders a form card for every available hardware method. 
* **UI Customization**: 
   * Users can reorder method cards using drag-and-drop. This order is saved to the user's session (`card_order`).
   * Users can selectively hide specific functions they don't use often (`hidden_functions`), decluttering the interface.
* **Direct Execution**: Form submissions trigger single-step execution against the hardware. Outputs and success/failure states are flashed back to the UI.
* **Console Sandbox**: Provides a raw Python execution console (`/console/execute`). Users can write snippets to manipulate the global `deck` state directly. This environment is restricted (using safe builtins) to prevent arbitrary OS-level imports.

---

## Summary for Modernization

If migrating to a modern stack (e.g., Next.js frontend + FastAPI/Node backend):
1. **Introspection**: You will need a strong backend worker that reflects the Python hardware API into a JSON Schema.
2. **State Management**: The phased execution (Prep/Main/Cleanup) requires a robust task queue (like Celery or Temporal) rather than in-memory asyncio loops, especially to handle BO campaigns that block and wait for hardware.
3. **Database**: The hierarchical structure (Run -> Phase -> Step) is solid and should be preserved in the new ORM (Prisma/TypeORM/SQLModel).
4. **Real-time UX**: The control panel and log tailing heavily benefit from WebSockets or Server-Sent Events (SSE) to stream hardware status dynamically, rather than relying on Flask template re-renders.
