"""Preflight - the core engine."""

from __future__ import annotations

import inspect
import functools
from typing import Any, Callable, Optional

from .models import ActionCapture, Plan, RiskLevel, Reversibility
from .classifiers import ClassifierChain, ClassifierFn
from .renderer import render, render_plain


class Preflight:
    """Main preflight engine."""

    def __init__(
        self,
        auto_classify: bool = True,
        max_actions: int = 100,
        cost_limit: Optional[float] = None,
    ) -> None:
        self._intercepted: dict[str, Callable] = {}
        self._captures: list[ActionCapture] = []
        self._dry_run_mode: bool = False
        self._classifier_chain = ClassifierChain()
        self._auto_classify = auto_classify
        self._max_actions = max_actions
        self._cost_limit = cost_limit
        self._sequence = 0

    def intercept(self, func: Optional[Callable] = None, **meta: Any) -> Callable:
        """Decorator to intercept a function for preflight capture."""
        if func is None:
            def decorator(f: Callable) -> Callable:
                return self._wrap(f, meta)
            return decorator
        return self._wrap(func, meta)

    def _wrap(self, func: Callable, meta: dict[str, Any]) -> Callable:
        name = func.__name__
        self._intercepted[name] = func

        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            if self._dry_run_mode:
                self._capture(name, func, args, kwargs, meta)
                return None
            return func(*args, **kwargs)

        wrapper._preflight_name = name
        wrapper._preflight_meta = meta
        return wrapper

    def _capture(self, name, func, args, kwargs, meta):
        if len(self._captures) >= self._max_actions:
            return

        sig = inspect.signature(func)
        params = list(sig.parameters.keys())
        named_args = {}
        for i, arg in enumerate(args):
            key = params[i] if i < len(params) else f"arg_{i}"
            named_args[key] = arg

        self._sequence += 1
        action = ActionCapture(
            name=name,
            args=named_args,
            kwargs=kwargs,
            sequence=self._sequence,
        )

        if self._auto_classify:
            action = self._classifier_chain.classify(action)

        # Apply decorator overrides AFTER classification (takes priority)
        if "cost" in meta:
            action.estimated_cost = meta["cost"]
        if "reversible" in meta:
            action.reversibility = (
                Reversibility.REVERSIBLE if meta["reversible"]
                else Reversibility.IRREVERSIBLE
            )
        self._captures.append(action)

    def dry_run(self, run_fn=None, task=""):
        """Execute in dry-run mode, capturing all intercepted calls."""
        self._captures = []
        self._sequence = 0
        self._dry_run_mode = True

        if run_fn is not None:
            try:
                run_fn()
            except Exception:
                pass

        self._dry_run_mode = False

        plan = Plan(
            actions=list(self._captures),
            task_description=task,
            _executors=dict(self._intercepted),
        )
        plan.finalize()

        if self._cost_limit and plan.total_estimated_cost > self._cost_limit:
            plan.warnings.append(
                f"COST LIMIT: ${plan.total_estimated_cost:.2f} > ${self._cost_limit:.2f}"
            )
            plan.overall_risk = RiskLevel.CRITICAL

        return plan

    def capture(self, name, args=None, kwargs=None, executor=None):
        """Directly capture an action (for framework integrations)."""
        action = ActionCapture(
            name=name,
            args=args or {},
            kwargs=kwargs or {},
            sequence=len(self._captures) + 1,
        )
        if self._auto_classify:
            action = self._classifier_chain.classify(action)
        self._captures.append(action)
        if executor:
            self._intercepted[name] = executor
        return action

    def build_plan(self, task=""):
        """Build plan from directly captured actions."""
        plan = Plan(
            actions=list(self._captures),
            task_description=task,
            _executors=dict(self._intercepted),
        )
        plan.finalize()
        return plan

    def add_classifier(self, classifier):
        self._classifier_chain.add(classifier)
        return self

    @staticmethod
    def format(plan, color=True):
        return render(plan, color=color)

    @staticmethod
    def format_plain(plan):
        return render_plain(plan)

    def recording(self, task=""):
        return _RecordingContext(self, task)


class _RecordingContext:
    def __init__(self, pf, task):
        self._pf = pf
        self._task = task
        self.plan = None

    def __enter__(self):
        self._pf._captures = []
        self._pf._sequence = 0
        self._pf._dry_run_mode = True
        return self

    def __exit__(self, *args):
        self._pf._dry_run_mode = False
        self.plan = Plan(
            actions=list(self._pf._captures),
            task_description=self._task,
            _executors=dict(self._pf._intercepted),
        )
        self.plan.finalize()
