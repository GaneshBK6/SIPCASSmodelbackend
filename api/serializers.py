from rest_framework import serializers
from .models import AOPTarget

class AOPTargetSerializer(serializers.ModelSerializer):
    class Meta:
        model = AOPTarget
        fields = '__all__'  # Or list fields you want to expose explicitly
        read_only_fields = ('target', 'uploaded_at')  # Calculated and auto fields
