"""
Configurable workflow engine for status transitions.

Provides a declarative way to define valid status transitions for any model
with a ``status`` field. Each transition can specify:
- required roles (who can trigger it)
- side-effects (callable hooks after transition)
- validation rules

Usage:
    from core.workflow import WorkflowEngine

    APPLICATION_WORKFLOW = WorkflowEngine(
        transitions=[
            Transition('draft', 'submitted', roles=['applicant'], label='Submit'),
            Transition('submitted', 'under_review', roles=['agency_staff'], label='Begin Review'),
            ...
        ]
    )

    # In a view:
    APPLICATION_WORKFLOW.execute(application, 'submitted', user=request.user)
"""
import logging
from dataclasses import dataclass, field
from typing import Callable, Optional

from django.core.exceptions import PermissionDenied, ValidationError

logger = logging.getLogger(__name__)


@dataclass
class Transition:
    """A single allowed status transition."""

    from_status: str
    to_status: str
    roles: list = field(default_factory=list)
    label: str = ''
    description: str = ''
    require_comment: bool = False
    validators: list = field(default_factory=list)
    on_complete: Optional[Callable] = None

    def __str__(self):
        return f"{self.from_status} -> {self.to_status}"


class WorkflowEngine:
    """Manages valid status transitions for a model.

    Attributes:
        transitions: list of ``Transition`` objects defining the workflow graph.
    """

    def __init__(self, transitions: list[Transition] | None = None):
        self.transitions = transitions or []
        self._index: dict[str, list[Transition]] = {}
        self._rebuild_index()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get_available_transitions(self, current_status: str, user=None):
        """Return transitions available from *current_status* for *user*.

        If *user* is ``None`` all transitions from the status are returned
        regardless of role restrictions.
        """
        candidates = self._index.get(current_status, [])
        if user is None:
            return candidates

        return [
            t for t in candidates
            if self._user_has_role(user, t.roles)
        ]

    def can_transition(self, current_status: str, target_status: str, user=None) -> bool:
        """Return ``True`` if the transition is valid and permitted."""
        for t in self._index.get(current_status, []):
            if t.to_status == target_status:
                if user is None or self._user_has_role(user, t.roles):
                    return True
        return False

    def execute(self, obj, target_status: str, user=None, comment: str = '', save=True):
        """Execute a status transition on *obj*.

        Args:
            obj: Model instance with a ``status`` attribute.
            target_status: Desired new status value.
            user: The user performing the action (used for role checks).
            comment: Optional comment (required for some transitions).
            save: Whether to call ``obj.save()`` after the transition.

        Returns:
            The matched ``Transition`` object.

        Raises:
            ValidationError: If the transition is not valid.
            PermissionDenied: If the user lacks the required role.
        """
        current = obj.status
        transition = self._find_transition(current, target_status)

        if transition is None:
            raise ValidationError(
                f"Transition from '{current}' to '{target_status}' is not allowed."
            )

        # Role check
        if user is not None and not self._user_has_role(user, transition.roles):
            raise PermissionDenied(
                f"User role '{getattr(user, 'role', 'unknown')}' cannot perform "
                f"transition '{transition}'."
            )

        # Comment requirement
        if transition.require_comment and not comment.strip():
            raise ValidationError(
                f"A comment is required for this transition ({transition})."
            )

        # Custom validators
        for validator in transition.validators:
            validator(obj, user, comment)

        # Apply the transition
        old_status = obj.status
        obj.status = target_status

        if save:
            obj.save(update_fields=['status', 'updated_at'])

        logger.info(
            "Workflow transition: %s %s -> %s (user=%s)",
            obj.__class__.__name__,
            old_status,
            target_status,
            user,
        )

        # Post-transition hook
        if transition.on_complete:
            transition.on_complete(obj, user, comment)

        return transition

    def get_status_graph(self) -> dict[str, list[str]]:
        """Return a dict mapping each from_status to a list of reachable statuses."""
        graph = {}
        for t in self.transitions:
            graph.setdefault(t.from_status, []).append(t.to_status)
        return graph

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _rebuild_index(self):
        self._index = {}
        for t in self.transitions:
            self._index.setdefault(t.from_status, []).append(t)

    def _find_transition(self, from_status: str, to_status: str) -> Transition | None:
        for t in self._index.get(from_status, []):
            if t.to_status == to_status:
                return t
        return None

    @staticmethod
    def _user_has_role(user, required_roles: list[str]) -> bool:
        """Check if *user* satisfies any of the *required_roles*.

        Special role keywords:
        - ``'any'``: any authenticated user
        - ``'agency_staff'``: uses ``user.is_agency_staff``
        - ``'grant_manager'``: uses ``user.can_manage_grants``
        - ``'reviewer'``: uses ``user.can_review``
        - anything else: compared to ``user.role``
        """
        if not required_roles or 'any' in required_roles:
            return True

        role = getattr(user, 'role', '')

        for r in required_roles:
            if r == 'agency_staff' and getattr(user, 'is_agency_staff', False):
                return True
            if r == 'grant_manager' and getattr(user, 'can_manage_grants', False):
                return True
            if r == 'reviewer' and getattr(user, 'can_review', False):
                return True
            if r == role:
                return True

        return False


# =========================================================================
# Pre-defined workflows for each major entity
# =========================================================================

APPLICATION_WORKFLOW = WorkflowEngine(transitions=[
    Transition(
        'draft', 'submitted',
        roles=['applicant', 'agency_staff'],
        label='Submit Application',
    ),
    Transition(
        'submitted', 'under_review',
        roles=['agency_staff'],
        label='Begin Review',
    ),
    Transition(
        'under_review', 'approved',
        roles=['grant_manager'],
        label='Approve',
    ),
    Transition(
        'under_review', 'denied',
        roles=['grant_manager'],
        label='Deny',
        require_comment=True,
    ),
    Transition(
        'under_review', 'revision_requested',
        roles=['agency_staff'],
        label='Request Revision',
        require_comment=True,
    ),
    Transition(
        'revision_requested', 'submitted',
        roles=['applicant'],
        label='Resubmit',
    ),
    Transition(
        'submitted', 'withdrawn',
        roles=['applicant'],
        label='Withdraw',
    ),
    Transition(
        'draft', 'withdrawn',
        roles=['applicant'],
        label='Withdraw',
    ),
])


AWARD_WORKFLOW = WorkflowEngine(transitions=[
    Transition(
        'draft', 'pending_approval',
        roles=['agency_staff'],
        label='Submit for Approval',
    ),
    Transition(
        'pending_approval', 'approved',
        roles=['grant_manager'],
        label='Approve Award',
    ),
    Transition(
        'approved', 'executed',
        roles=['grant_manager'],
        label='Execute Award',
    ),
    Transition(
        'executed', 'active',
        roles=['agency_staff'],
        label='Activate',
    ),
    Transition(
        'active', 'on_hold',
        roles=['grant_manager'],
        label='Place on Hold',
        require_comment=True,
    ),
    Transition(
        'on_hold', 'active',
        roles=['grant_manager'],
        label='Resume',
    ),
    Transition(
        'active', 'completed',
        roles=['grant_manager'],
        label='Complete',
    ),
    Transition(
        'active', 'terminated',
        roles=['grant_manager'],
        label='Terminate',
        require_comment=True,
    ),
    Transition(
        'pending_approval', 'cancelled',
        roles=['grant_manager'],
        label='Cancel',
    ),
    Transition(
        'draft', 'cancelled',
        roles=['agency_staff'],
        label='Cancel',
    ),
])


DRAWDOWN_WORKFLOW = WorkflowEngine(transitions=[
    Transition(
        'draft', 'submitted',
        roles=['any'],
        label='Submit Request',
    ),
    Transition(
        'submitted', 'under_review',
        roles=['agency_staff'],
        label='Begin Review',
    ),
    Transition(
        'submitted', 'approved',
        roles=['fiscal_officer', 'agency_admin', 'system_admin'],
        label='Approve',
    ),
    Transition(
        'under_review', 'approved',
        roles=['fiscal_officer', 'agency_admin', 'system_admin'],
        label='Approve',
    ),
    Transition(
        'approved', 'paid',
        roles=['fiscal_officer', 'agency_admin', 'system_admin'],
        label='Mark Paid',
    ),
    Transition(
        'submitted', 'denied',
        roles=['fiscal_officer', 'agency_admin', 'system_admin'],
        label='Deny',
        require_comment=True,
    ),
    Transition(
        'submitted', 'returned',
        roles=['fiscal_officer', 'agency_admin', 'system_admin'],
        label='Return for Revision',
    ),
    Transition(
        'returned', 'submitted',
        roles=['any'],
        label='Resubmit',
    ),
])


REPORT_WORKFLOW = WorkflowEngine(transitions=[
    Transition(
        'draft', 'submitted',
        roles=['any'],
        label='Submit Report',
    ),
    Transition(
        'submitted', 'under_review',
        roles=['agency_staff'],
        label='Begin Review',
    ),
    Transition(
        'submitted', 'approved',
        roles=['agency_staff'],
        label='Approve',
    ),
    Transition(
        'under_review', 'approved',
        roles=['agency_staff'],
        label='Approve',
    ),
    Transition(
        'submitted', 'revision_requested',
        roles=['agency_staff'],
        label='Request Revision',
        require_comment=True,
    ),
    Transition(
        'under_review', 'revision_requested',
        roles=['agency_staff'],
        label='Request Revision',
        require_comment=True,
    ),
    Transition(
        'revision_requested', 'submitted',
        roles=['any'],
        label='Resubmit',
    ),
    Transition(
        'submitted', 'rejected',
        roles=['grant_manager'],
        label='Reject',
        require_comment=True,
    ),
])


CLOSEOUT_WORKFLOW = WorkflowEngine(transitions=[
    Transition(
        'not_started', 'in_progress',
        roles=['agency_staff'],
        label='Begin Closeout',
    ),
    Transition(
        'in_progress', 'pending_review',
        roles=['agency_staff'],
        label='Submit for Review',
    ),
    Transition(
        'pending_review', 'completed',
        roles=['grant_manager'],
        label='Complete Closeout',
    ),
    Transition(
        'pending_review', 'in_progress',
        roles=['grant_manager'],
        label='Return to In Progress',
        require_comment=True,
    ),
    Transition(
        'completed', 'reopened',
        roles=['grant_manager'],
        label='Reopen',
        require_comment=True,
    ),
    Transition(
        'reopened', 'in_progress',
        roles=['agency_staff'],
        label='Resume',
    ),
])


GRANT_PROGRAM_WORKFLOW = WorkflowEngine(transitions=[
    Transition(
        'draft', 'posted',
        roles=['grant_manager'],
        label='Post',
    ),
    Transition(
        'posted', 'accepting_applications',
        roles=['grant_manager'],
        label='Open Applications',
    ),
    Transition(
        'accepting_applications', 'under_review',
        roles=['grant_manager'],
        label='Close Applications & Review',
    ),
    Transition(
        'under_review', 'awards_pending',
        roles=['grant_manager'],
        label='Finalize Reviews',
    ),
    Transition(
        'awards_pending', 'closed',
        roles=['grant_manager'],
        label='Close Program',
    ),
    Transition(
        'posted', 'cancelled',
        roles=['grant_manager'],
        label='Cancel',
    ),
    Transition(
        'posted', 'draft',
        roles=['grant_manager'],
        label='Unpublish',
    ),
])
