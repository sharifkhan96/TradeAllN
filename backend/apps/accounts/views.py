from django.conf import settings
from django.contrib.auth import authenticate, get_user_model
from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.tokens import RefreshToken

from .serializers import RegisterSerializer, UserSerializer

COOKIE_PATH = "/api/v1/auth/"


def _session_response(user, status_code=status.HTTP_200_OK):
    refresh = RefreshToken.for_user(user)
    resp = Response(
        {"access": str(refresh.access_token), "user": UserSerializer(user).data}, status=status_code
    )
    _set_refresh_cookie(resp, str(refresh))
    return resp


def _set_refresh_cookie(resp, token):
    resp.set_cookie(
        settings.REFRESH_COOKIE_NAME, token,
        max_age=int(settings.SIMPLE_JWT["REFRESH_TOKEN_LIFETIME"].total_seconds()),
        httponly=True, secure=not settings.DEBUG, samesite="Strict", path=COOKIE_PATH,
    )


class AuthThrottleMixin:
    permission_classes = [permissions.AllowAny]
    authentication_classes = []
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "auth"


class RegisterView(AuthThrottleMixin, APIView):
    def post(self, request):
        ser = RegisterSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        return _session_response(ser.save(), status.HTTP_201_CREATED)


class LoginView(AuthThrottleMixin, APIView):
    def post(self, request):
        email = (request.data.get("email") or "").lower().strip()
        user = authenticate(request, username=email, password=request.data.get("password") or "")
        if not user:
            return Response({"detail": "Invalid email or password."}, status=401)
        return _session_response(user)


class RefreshView(AuthThrottleMixin, APIView):
    throttle_classes = []

    def post(self, request):
        raw = request.COOKIES.get(settings.REFRESH_COOKIE_NAME)
        if not raw:
            return Response({"detail": "No session."}, status=401)
        try:
            user_id = RefreshToken(raw)["user_id"]
            user = get_user_model().objects.get(pk=user_id, is_active=True)
        except (TokenError, get_user_model().DoesNotExist):
            resp = Response({"detail": "Session expired."}, status=401)
            resp.delete_cookie(settings.REFRESH_COOKIE_NAME, path=COOKIE_PATH)
            return resp
        return _session_response(user)


class LogoutView(AuthThrottleMixin, APIView):
    throttle_classes = []

    def post(self, request):
        resp = Response(status=204)
        resp.delete_cookie(settings.REFRESH_COOKIE_NAME, path=COOKIE_PATH)
        return resp


class MeView(APIView):
    def get(self, request):
        return Response(UserSerializer(request.user).data)

    def patch(self, request):
        ser = UserSerializer(request.user, data=request.data, partial=True)
        ser.is_valid(raise_exception=True)
        ser.save()
        return Response(ser.data)
