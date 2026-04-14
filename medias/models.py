from django.db import models
from glams.models import Glam
from django.utils.translation import gettext_lazy as _


class MediaFile(models.Model):
    page_id = models.CharField(max_length=50, unique=True)
    filename = models.CharField(max_length=300)
    file_path = models.CharField(max_length=1000)
    thumb_path = models.CharField(max_length=1000)
    license = models.CharField(max_length=50, blank=True, null=True)
    upload_date = models.DateTimeField()
    uploader = models.CharField(max_length=250)
    glam = models.ForeignKey(Glam, on_delete=models.CASCADE)
    extension = models.TextField(max_length=10)

    def __str__(self):
        return self.filename


class MediaRequests(models.Model):
    """
    referer is always "all-referers"
    agent is always "users"
    granularity is always "monthly"
    """
    file = models.ForeignKey(MediaFile, on_delete=models.CASCADE)
    timestamp = models.CharField(max_length=10)
    requests = models.PositiveIntegerField(default=0)
    retrieved_at = models.DateTimeField(auto_now_add=True)
    timestamp_new = models.DateField(null=True)

    class Meta:
        unique_together = ("file", "timestamp")

    def formatted_timestamp(self):
        if len(self.timestamp) == 10:
            return f"{self.timestamp[:4]}-{self.timestamp[4:6]}-{self.timestamp[6:8]}"
        else:
            return self.timestamp

    def __str__(self):
        return f"{str(self.file)} ({self.formatted_timestamp()})"


class MediaUsage(models.Model):
    file = models.ForeignKey(MediaFile, on_delete=models.CASCADE)
    title = models.CharField(max_length=5000)
    wiki = models.CharField(max_length=500)
    url = models.URLField(max_length=5000)
    page_id = models.CharField(max_length=50)
    namespace = models.CharField(max_length=5)
    retrieved_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("file", "page_id")

    def __str__(self):
        return f"{str(self.file)} ({self.wiki})"