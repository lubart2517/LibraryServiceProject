from rest_framework.permissions import SAFE_METHODS, BasePermission


class IsAdminOrReadOnly(BasePermission):
    def has_permission(self, request, view):
        return bool(
            request.method in SAFE_METHODS
            or (request.user and request.user.is_staff)
        )


class IsAllowedToCreateOrAdmin(BasePermission):
    def has_permission(self, request, view):
        return bool(request.user.is_authenticated)

    def has_object_permission(self, request, view, obj):
        """
        Return `True` if permission is granted, `False` otherwise.
        """
        if request.method == "POST":
            return bool(request.user)
        else:
            try:
                user = obj.user
            except AttributeError:
                user = obj.borrowing.user
            return bool(
                request.user
                and (user == request.user or request.user.is_staff)
            )


class IsAllowedToViewOwnOrAdmin(BasePermission):
    def has_permission(self, request, view):
        if request.method == "POST":
            return bool(request.user.is_staff)
        return bool(request.user.is_authenticated)

    def has_object_permission(self, request, view, obj):
        """
        Return `True` if permission is granted, `False` otherwise.
        """

        user = obj.borrowing.user
        return bool(
            request.user
            and (user == request.user or request.user.is_staff)
        )
