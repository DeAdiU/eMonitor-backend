from rest_framework import serializers
from .models import User, PlatformProfile, MentorStudentMapping

class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'password', 'role', 'enrollment_year', 'graduation_year', 'date_of_birth', 'phone_number', 'is_verified']
        extra_kwargs = {
            'password': {'write_only': True},  # Password is not returned in responses
            'id': {'read_only': True},         # ID is auto-generated and read-only
            'is_verified': {'read_only': True} # Prevent users from modifying is_verified directly
        }

    def create(self, validated_data):
        # Create a new user with hashed password
        user = User.objects.create_user(
            username=validated_data['username'],
            email=validated_data['email'],
            password=validated_data['password'],
            role=validated_data['role'],
            enrollment_year=validated_data.get('enrollment_year'),
            graduation_year=validated_data.get('graduation_year'),
            date_of_birth=validated_data.get('date_of_birth'),
            phone_number=validated_data.get('phone_number'),
        )
        return user

    def update(self, instance, validated_data):
        # Update existing user instance
        instance.username = validated_data.get('username', instance.username)
        instance.email = validated_data.get('email', instance.email)

        # Handle password update (hash it if provided)
        if 'password' in validated_data:
            instance.set_password(validated_data['password'])  # Hash the new password

        # Update optional fields
        instance.enrollment_year = validated_data.get('enrollment_year', instance.enrollment_year)
        instance.graduation_year = validated_data.get('graduation_year', instance.graduation_year)
        instance.date_of_birth = validated_data.get('date_of_birth', instance.date_of_birth)
        instance.phone_number = validated_data.get('phone_number', instance.phone_number)

        # Note: 'role' and 'is_verified' are not updated here to restrict changes.
        # If you want to allow role updates under certain conditions, add logic below:
        # instance.role = validated_data.get('role', instance.role)

        instance.save()
        return instance

class PlatformProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = PlatformProfile
        fields = ['id', 'user', 'platform', 'profile_id', 'is_verified']
        read_only_fields = ['id', 'user', 'is_verified']

class MentorStudentMappingSerializer(serializers.ModelSerializer):
    class Meta:
        model = MentorStudentMapping
        fields = ['id', 'mentor', 'student']

