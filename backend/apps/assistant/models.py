import uuid

from django.conf import settings
from django.db import models


class AssistantCommand(models.Model):
    STATUSES = [("parsed", "Parsed"), ("confirmed", "Confirmed"), ("rejected", "Rejected"),
                ("failed", "Failed"), ("answered", "Answered")]
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
                             related_name="commands")
    input_text = models.TextField()
    method = models.CharField(max_length=10, default="regex")  # regex | llm
    intent = models.CharField(max_length=20)
    parsed = models.JSONField(default=dict)
    preview = models.JSONField(default=dict)
    status = models.CharField(max_length=10, choices=STATUSES, default="parsed")
    result = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
