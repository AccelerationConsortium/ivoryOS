# Changelog

## 1.5.16 (March 17th, 2026)
- !127 **[Bug]** fix logger removeHandler error on workflow completion
- !126 **[Bug]** fix compile error when if block has no actions (empty if block)
- !125 **[Bug]** fix generated proxy authentication error
- !124 **[QoL]** always display current iteration count out of total iterations during a run
- !122 **[Bug]** fix import class error in generated proxy

## 1.5.15 (March 5th, 2026)
- !119 **[Bug]** use `compile` instead of `exec` to avoid hardware code reloading and device connection issues
- !118 **[New]** downgrade problematic packages to support 32-bit Python installation
- !116 **[Bug]** fix so script will stop execution if error encountered and abort option selected (previously sometimes next step gets executed); save workflow data after each iteration instead of on stop/completion in case of Python/script error
- !115 **[Bug]** fix to improve editing enum arguments and using returned variables as method arguments
- !114 **[Bug]** displaying when login with incorrect combo
- !113 **[Bug]** no reload when checking syntax
- !112 **[QoL]** record step input parameters in workflow steps data CSV file
- !111 **[QoL]** record all app loggers in the downloaded workflow-specific logs CSV file
- !110 **[Bug]** fix syntax error if there is a space in a string configuration parameter

## 1.5.14 (February 8th, 2026)
- !108 **[Bug]** fix nested workflow flow control (if/while) execution bug
- !107 **[New]** save logs from data per run (credit to @Veronica)

## 1.5.13 (February 5th, 2026)
- !106 **[QoL]** workflow library display improvement + scroll bar in config window
- !105 **[QoL]** clean up
- !104 **[Bug]** optional str argument input error in config
- !103 **[Bug]** maximum design size bug, replace session with json
- !102 **[QoL]** add a queue task view, check configs in pop-up window
- !101 **[QoL]** be able to add to name of queued tasks
- !100 **[QoL]** list consolidation in workflow designer
- !99 **[Bug]** code indent wrong when if statement used in nested workflow
- !98 **[Bug]** inner workflow missing context value
- !97 **[New]** Design Agent Feature (re-implementation of "Text-To-Code") (credit to @ChemistryTobias)
- !96 **[QoL]** be able to scroll the code preview
- !95 **[Bug]** workflow with space in name returns immediately instead of being run

## 1.5.12 (January 30th, 2026)
- !94 **[Bug]** fix loaded CSV doesn't auto-update; show reset button when data doesn't match
- !93 **[New]** support `**kwargs` input
- !92 **[QoL]** add search bar on top of the controller and designer

## 1.5.11 (January 29th, 2026)
- !91 **[Bug]** fix database is locked error during workflow execution
- !90 **[New]** add task queue system

## 1.5.10 (January 26th, 2026)
- !89 **[Bug]** syntax error during execution with list of Enum; remove legacy compile in script runner
- !89 **[Bug]** error page when editing steps with list param

## 1.5.9 (January 26th, 2026)
- !88 **[Bug]** cannot scroll progress region after starting a run
- !87 **[Bug]** step retry not working in workflow execution
- !86 **[Bug]** page load error after proxy download + enum import in proxy
- !85 **[QoL]** dropdown menu showing existing variable names in workflow

## 1.5.8 (January 20th, 2026)
Workflow + batch fixes:
- !83 **[Bug]** remove type conversion for str type in `Union[]`
- !82 **[Bug]** arg substitute bug
- !82 **[Bug]** fix "batch_action" shows in step arg
- !81 **[Bug]** serialize all input args and outputs before db commit

New workflow behaviours:
- Register workflow (only registered workflows will show up in the workflow section)
- Once-per-batch action — duplicate results for all per-sample actions
- Auto-complete return values for workflows (inherit workflow returns)

## 1.5.7 (January 19th, 2026)
- !79 **[Bug]** once-per-batch action execution bug
- !78 **[Bug]** custom type / dropdown menu import

## 1.5.6 (January 16th, 2026)
- !77 **[QoL]** central/cloud db, auth tweak to support PostgreSQL, config from `.env`
- !76 **[QoL]** per-batch / per-sample option for workflow steps
- Minor UI text change for clarity

## 1.5.5 (January 13th, 2026)
- !75 **[Bug]** workflow steps not in sequential execution
- !74 **[Bug]** BO config UI — Choice input not reloaded

## 1.5.4 (January 8th, 2026)
Happy New Year from the IvoryOS team! 🎉
- !73 **[New]** import Python functions as workflow (Finn)
- !72 **[QoL]** UI/UX optimization
- !71 **[Bug]** autofill not working in workflow method
- !70 **[Bug]** BO history CSV upload not working
- !69 **[Bug]** use dynamic param within comment text
- !68 **[Bug]** fix can't add a math variable
- !67 **[QoL]** always save CSV regardless of output

## 1.5.3 (December 20th, 2025)
- !66 **[New]** human-in-the-loop user input (@Yusuke)
- !65 **[New]** additional user log (@Veronica)
- !64 **[New]** setter/getter support
- !63 **[Bug]** deduplicate in Ax custom strategy
- !62 **[QoL]** always-on progress bar

## 1.5.2 (December 15th, 2025)
- **[Bug]** fix Ax step range input conversion bug (@Yusuke)

## 1.5.1 (December 14th, 2025)
- **[Bug]** fix progress HTML

## 1.5.0 (December 14th, 2025)
- **[New]** finalize the design as workflow step (beta)

## 1.4.16 (December 12th, 2025)
- **[Bug]** config list input conversion fix (@Leo)

## 1.4.15 (December 12th, 2025)
- **[Bug]** list input type conversion fix (@Ryan, @Leo)
- **[New]** introduce math variable (credit: @Veronica)

## 1.4.14 (December 12th, 2025)
- **[New]** add NIMO 2.0.5 append historical data
- **[New]** additional parameters for NIMO

## 1.4.13 (December 11th, 2025)
- **[Bug]** remove action return value save when `None` return type hinted (@Veronica)
- **[New]** support `Optional[Enum]` type hinting (@Veronica)

## 1.4.12 (December 5th, 2025)
- **[Bug]** temp fix for property in form loading (@Ryan, @Yusuke)
- **[Bug]** JSON-safe data check (@Yusuke)
- **[Bug]** fix temp connection method call in script

## 1.4.11 (December 3rd, 2025)
- **[New]** add get optimizer schema route

## 1.4.10 (December 3rd, 2025)
- **[Bug]** row addition when switching config tabs
- **[New]** add upload historical data
- **[Bug]** fix Ax `num_trials=0` error

## 1.4.9 (November 27th, 2025)
- **[Bug]** step order sorting bug (@everyone)

## 1.4.8 (November 25th, 2025)
- **[New]** stop-pending no longer prompts to continue cleanup (@Veronica)
- **[New]** description field in script — add a description when saving (@Veronica)

## 1.4.7 (November 23rd, 2025)
- **[QoL]** reorder parameter sweep entries (@Irene, @Maria, @Ekaterina)
- **[New]** gracefully stop pending iterations, move to cleanup steps (@Veronica)
- **[Bug]** Ax optimizer: fix bug when using reserved words (e.g. "test", "yield", "product") as objective name
- **[New]** Ax optimizer: allow failed trials — marked as Failed when missing objective(s) (@SDL2)
- **[Bug]** fix handling of `None` values; empty string is now treated as `None` (@Veronica)
- **[Bug]** fix type hint extraction when using `from __future__ import annotations` (@SDL2)

## 1.4.6 (November 19th, 2025)
- **[Bug]** fix error when leading number in str input (@Irene, @Maria, @Ekaterina)

## 1.4.5 (November 19th, 2025)
- **[Bug]** proxy authentication failing message fix (@Maria Politi)
- **[Bug]** proxy class won't initialize if username/password combination is wrong
- **[Bug]** faulty display of single/batch code

## 1.4.4 (November 16th, 2025)
- **[Bug]** variable and function return bug (@Veronica Lai)
- **[Bug]** handle Ax not accepting "test" as objective name
- **[QoL]** move optimizer init to thread
- Minor bug fixes

## 1.4.3 (November 14th, 2025)
Minor user interface changes:
- **[New]** create default admin user; allow password change by clicking on username
- **[New]** add option to change logo (replace or prepend the IvoryOS logo)
- **[QoL]** auto-create module list from imported modules; further imports will override existing modules
- **[QoL]** remove unused API endpoint
- **[Bug]** fix stop button not working

## 1.4.2 (November 12th, 2025)
- **[New]** add floating help icon (credit to @Veronica Lai)
- **[Bug]** fix type conversion for args with no type hint (credit to @Maria Politi)

## 1.4.1 (November 5th, 2025)
- **[New]** update optimizer API call
- **[New]** PoC plot for NIMO optimizer
- **[Bug]** minor bugs — device tab display error (credit to @Finn Bork)

## 1.4.0 (November 2nd, 2025)
- **[New]** introduce batch execution, step-wise repeat per batch
- **[New]** introduce batch action (light purple) — repeat only once per batch
- **[New]** redesign script runner with granular action control in if/for/while
- **[Bug]** fix Ax/Bayes errors for compatibility with the newest version
- **[QoL]** BO tab and input will restore on reload

## 1.3.6 – 1.3.8 (October 9th, 2025)
- **[Bug]** handle editing error on deleted steps (can occur when multiple browsers are open and inactive tabs are not refreshed)
- **[Bug]** fix Ax platform import path (`No module named 'ax.modelbridge'`)
- **[New]** add NIMO as an optimizer option
- **[Bug]** fix Flask async install
- **[Bug]** forgot to include `nimo_optimizer.py` in 1.3.6 release

## 1.3.5 (October 2nd, 2025)
- **[Bug]** fix output list
- **[New]** allow async
- **[Bug]** variable not found in execution (credit: @Jenny Zhou)
- **[New]** missing variable alert (credit: @Jenny Zhou)
- **[Bug]** minor fix in `__init__` and add optional installs

## 1.3.4 (September 18th, 2025)
- **[New]** allow customized notification handler for workflow pause (human intervention)
- **[Bug]** fix redundant db backup when there are no workflow records
- **[Bug]** fix function call "Unknown API Error" with "busy"
- **[QoL]** optimize db addition with `flush()`
- **[QoL]** docs (README) update

## 1.3.3 (September 11th, 2025)
- **[Bug]** fix Python-to-JSON conversion; support more deck and blocks

## 1.3.2 (September 10th, 2025)
- **[Bug]** fix old workflow db schema handling; update status too
- **[Bug]** fix `time.sleep()` Python-to-JSON conversion
- **[New]** allow building block execution in MCP
- **[QoL]** fix docs and Sphinx auto-doc

## 1.3.1
- **[Bug]** fix socketio in demos
- **[Bug]** `time.sleep()` execution error in Python 3.7 (credit: @Maria Politi)

## 1.3.0
- **[New]** refactor the workflow record db to support visualization (old workflow db backed up and dropped)
- **[Bug]** fix Enum dynamic input and input in Devices
- **[Bug]** fix snapshot converted to str issue

## 1.2.8
- **[New]** add human intervention (pause) to flow control
- **[New]** add `@block` decorator for Python functions
- **[QoL]** move `run()` from `__init__.py` to `server.py`
- **[QoL]** optimize drag/drop — no drag when selecting text
- **[Bug]** fix type conversion error for "any" type

## 1.2.7
- **[Security]** remove API function call backdoor
- **[New]** modify RPC script generation to support auth
- **[QoL]** clean up function call error handling
- **[Bug]** fix workflow save flash

## 0.1.23
- **[New]** show line numbers
- **[New]** add dropdown menu option for Enum type
- **[New]** add retry option when erroring out
- **[New]** new wait implementation — can stop during waiting
- **[New]** add direct blueprint plugin config

## 0.1.22
- **[New]** add data page
- **[Bug]** fix phase order in run page
- **[New]** add client feature to device (direct control) page

## 0.1.21
- **[New]** add drag and drop to design
- **[New]** add bool option for variables
- **[QoL]** remove About from top tab
- **[QoL]** move logic (if, while, etc.) to "flow control"

## 0.1.20
- **[New]** add task progress tracking

## 0.1.19
- **[New]** add pause/resume and stop to execution page
- **[Bug]** fix Python script display

## 0.1.18
- **[Bug]** fix prep/cleanup repeat issue
- **[Bug]** remove duplicate return values
- **[QoL]** add plugin docs

## 0.1.17
- **[QoL]** move video feed as plugins

## 0.1.16
- **[Bug]** fix pip setup

## 0.1.15
- **[New]** add modular tabs
- **[New]** add video feed

## 0.1.14
- **[Bug]** fix statement display for logic functions
- **[QoL]** display docstrings in functions

## 0.1.13
- **[Bug]** fix edit action input type bugs
- **[Bug]** fix variable calling in function
- **[New]** add warning for undefined variable

## 0.1.12
- **[New]** add checking for duplicate entry in config file
- **[New]** add return value output in backend control
- **[New]** add repeat in workflow design
