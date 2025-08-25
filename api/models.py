from django.db import models
from django.contrib.auth.hashers import make_password, check_password
from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin, BaseUserManager

class EmployeeData(models.Model):
    excel_file = models.FileField(upload_to='uploads/')
    uploaded_at = models.DateTimeField(auto_now_add=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ['-uploaded_at']

    def __str__(self):
        return f"File uploaded at {self.uploaded_at}"

class AOPTarget(models.Model):
    ship_to = models.CharField(max_length=255)
    py_actuals = models.FloatField()
    growth_percent = models.FloatField()
    emp_id = models.CharField(max_length=50, blank=True, null=True)
    target = models.FloatField(blank=True)
    seller1 = models.CharField(max_length=255, blank=True)
    seller2 = models.CharField(max_length=255, blank=True)
    seller3 = models.CharField(max_length=255, blank=True)
    seller4 = models.CharField(max_length=255, blank=True)
    region = models.CharField(max_length=100, blank=True, null=True)
    comments = models.TextField(blank=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        # Calculate target automatically before saving
        self.target = self.py_actuals * (1 + self.growth_percent / 100)
        super().save(*args, **kwargs)

    class Meta:
        ordering = ['-uploaded_at']

    def __str__(self):
        return f"AOPTarget {self.ship_to} - Target: {self.target}"


class AppUserManager(BaseUserManager):
    def create_user(self, employee_id, password=None, **extra_fields):
        if not employee_id:
            raise ValueError('Employee ID must be set')
        user = self.model(employee_id=employee_id, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, employee_id, password, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        if extra_fields.get('is_staff') is not True or extra_fields.get('is_superuser') is not True:
            raise ValueError('Superuser must have is_staff=True and is_superuser=True')
        return self.create_user(employee_id, password, **extra_fields)

class AppUser(AbstractBaseUser, PermissionsMixin):
    POSITION_CHOICES = (
        ('DM', 'District Manager'),
        ('AM', 'Area Manager'),
	('Seller', 'Seller'),
    )

    employee_id = models.CharField(max_length=50, unique=True)
    name = models.CharField(max_length=100)
    position = models.CharField(max_length=6, choices=POSITION_CHOICES)
    region = models.CharField(max_length=100)

    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)

    objects = AppUserManager()

    USERNAME_FIELD = 'employee_id'
    REQUIRED_FIELDS = ['name', 'position', 'region']

    def __str__(self):
        return f"{self.name} ({self.employee_id})"