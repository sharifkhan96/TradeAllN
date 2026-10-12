from django.conf import settings
from django.shortcuts import get_object_or_404
from rest_framework.decorators import api_view, throttle_classes
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle

from . import llm, service
from .models import AssistantCommand


class AIThrottle(ScopedRateThrottle):
    scope = "ai"


def _cmd(cmd: AssistantCommand) -> dict:
    return {"id": str(cmd.id), "input": cmd.input_text, "intent": cmd.intent,
            "method": cmd.method, "preview": cmd.preview, "status": cmd.status,
            "result": cmd.result, "created_at": cmd.created_at}


@api_view(["POST"])
@throttle_classes([AIThrottle])
def parse(request):
    try:
        cmd = service.handle(request.user, request.data.get("text", ""))
    except (service.AssistantError, llm.LLMUnavailable) as e:
        return Response({"detail": str(e)}, status=400)
    return Response(_cmd(cmd))


@api_view(["POST"])
def confirm(request, pk):
    cmd = get_object_or_404(AssistantCommand, pk=pk, user=request.user)
    try:
        service.confirm(cmd)
    except service.AssistantError as e:
        return Response({"detail": str(e)}, status=400)
    return Response(_cmd(cmd))


@api_view(["POST"])
def reject(request, pk):
    cmd = get_object_or_404(AssistantCommand, pk=pk, user=request.user, status="parsed")
    cmd.status = "rejected"
    cmd.save(update_fields=["status"])
    return Response(_cmd(cmd))


@api_view(["POST"])
@throttle_classes([AIThrottle])
def ask(request):
    q = (request.data.get("question") or "").strip()
    if not q:
        return Response({"detail": "Ask a question."}, status=400)
    return Response(service.ask(request.user, q[:1000]))


@api_view(["GET"])
def status(request):
    return Response({"ai_enabled": llm.enabled(), "user_ai_enabled": request.user.ai_enabled,
                     "model": settings.LLM_MODEL if llm.enabled() else None})


@api_view(["GET"])
def history(request):
    return Response([_cmd(c) for c in service.recent_commands(request.user)])
