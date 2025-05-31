from django.db import models

class EmployeeData(models.Model):
    excel_file = models.FileField(upload_to='uploads/')
    uploaded_at = models.DateTimeField(auto_now_add=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ['-uploaded_at']  # Newest first

    def __str__(self):
        return f"File uploaded at {self.uploaded_at}"