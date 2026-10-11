from django.contrib.auth.models import UserManager


class CustomUserManager(UserManager):

    def create_user(
        self,
        phone_number,
        password=None,
        **extra_fields
    ):
        if not phone_number:
            raise ValueError('شماره تلفن الزامی است')

        email = extra_fields.get('email')

        if email:
            extra_fields['email'] = self.normalize_email(email)

        extra_fields.setdefault('is_staff', False)
        extra_fields.setdefault('is_superuser', False)

        user = self.model(
            phone_number=phone_number,
            username=phone_number,
            **extra_fields
        )

        user.set_password(password)
        user.save(using=self._db)

        return user

    def create_superuser(
        self,
        phone_number,
        email=None,
        password=None,
        **extra_fields
    ):
        if not phone_number:
            raise ValueError('شماره تلفن الزامی است')

        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('is_active', True)

        if extra_fields.get('is_staff') is not True:
            raise ValueError('Superuser must have is_staff=True.')

        if extra_fields.get('is_superuser') is not True:
            raise ValueError(
                'Superuser must have is_superuser=True.'
            )

        return self.create_user(
            phone_number=phone_number,
            email=email,
            password=password,
            **extra_fields
        )