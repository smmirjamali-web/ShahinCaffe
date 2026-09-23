# users/managers.py
from django.contrib.auth.models import UserManager

class CustomUserManager(UserManager):
    def create_superuser(self, phone_number, email, password, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        
        if not phone_number:
            raise ValueError('شماره تلفن الزامی است')
        
        user = self.model(
            phone_number=phone_number,
            email=email,
            username=phone_number,  # استفاده از phone_number به عنوان username
            **extra_fields
        )
        user.set_password(password)
        user.save(using=self._db)
        return user