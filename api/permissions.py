"""
Custom permission classes for the Beacon REST API.

These permissions leverage the ``core.User.Role`` choices and the convenience
properties defined on the custom User model (``is_agency_staff``,
``can_manage_grants``, etc.) to enforce role-based access control at the
view level.
"""

from rest_framework.permissions import BasePermission

from core.models import User


class IsAgencyStaff(BasePermission):
    """
    Allow access only to users whose role qualifies as agency staff.

    Agency staff roles include: system_admin, agency_admin, program_officer,
    and fiscal_officer.
    """

    def has_permission(self, request, view):
        return (
            request.user
            and request.user.is_authenticated
            and request.user.is_agency_staff
        )


class IsGrantManager(BasePermission):
    """
    Allow access only to users who can create or manage grant programs.

    Grant manager roles include: system_admin, agency_admin, and
    program_officer.
    """

    def has_permission(self, request, view):
        return (
            request.user
            and request.user.is_authenticated
            and request.user.can_manage_grants
        )


class IsFiscalOfficer(BasePermission):
    """
    Allow access only to fiscal officers and system administrators.
    """

    def has_permission(self, request, view):
        return (
            request.user
            and request.user.is_authenticated
            and request.user.role
            in {User.Role.FISCAL_OFFICER, User.Role.SYSTEM_ADMIN}
        )


class IsAdminUser(BasePermission):
    """
    Allow access only to system administrators.
    """

    def has_permission(self, request, view):
        return (
            request.user
            and request.user.is_authenticated
            and request.user.role == User.Role.SYSTEM_ADMIN
        )
