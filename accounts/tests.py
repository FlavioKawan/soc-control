from django.contrib.auth.models import Group, User
from django.core.cache import cache
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse

from .views import MAX_LOGIN_ATTEMPTS


class LoginThrottleTests(TestCase):
    def setUp(self):
        cache.clear()
        self.user = User.objects.create_user("alice", password="correct-password")

    def _fail_login(self, remote_addr="10.0.0.1"):
        return self.client.post(
            reverse("login"),
            {"username": "alice", "password": "wrong"},
            REMOTE_ADDR=remote_addr,
        )

    def test_correct_credentials_log_in(self):
        response = self.client.post(
            reverse("login"), {"username": "alice", "password": "correct-password"}
        )
        self.assertTrue(response.wsgi_request.user.is_authenticated)

    def test_attempts_below_the_limit_are_not_blocked(self):
        for _ in range(MAX_LOGIN_ATTEMPTS - 1):
            self._fail_login()
        response = self.client.post(
            reverse("login"),
            {"username": "alice", "password": "correct-password"},
            REMOTE_ADDR="10.0.0.1",
        )
        self.assertTrue(response.wsgi_request.user.is_authenticated)

    def test_exceeding_the_limit_blocks_even_the_correct_password(self):
        for _ in range(MAX_LOGIN_ATTEMPTS):
            self._fail_login()
        response = self.client.post(
            reverse("login"),
            {"username": "alice", "password": "correct-password"},
            REMOTE_ADDR="10.0.0.1",
        )
        self.assertFalse(response.wsgi_request.user.is_authenticated)

    def test_throttle_is_scoped_per_ip_not_globally(self):
        for _ in range(MAX_LOGIN_ATTEMPTS):
            self._fail_login(remote_addr="10.0.0.1")
        response = self.client.post(
            reverse("login"),
            {"username": "alice", "password": "correct-password"},
            REMOTE_ADDR="10.0.0.2",
        )
        self.assertTrue(response.wsgi_request.user.is_authenticated)

    def test_successful_login_resets_the_counter(self):
        for _ in range(MAX_LOGIN_ATTEMPTS - 1):
            self._fail_login()
        self.client.post(
            reverse("login"),
            {"username": "alice", "password": "correct-password"},
            REMOTE_ADDR="10.0.0.1",
        )
        for _ in range(MAX_LOGIN_ATTEMPTS - 1):
            self._fail_login()
        response = self.client.post(
            reverse("login"),
            {"username": "alice", "password": "correct-password"},
            REMOTE_ADDR="10.0.0.1",
        )
        self.assertTrue(response.wsgi_request.user.is_authenticated)


class UserManagementPermissionTests(TestCase):
    """auth.* permissions are only handed to ADMIN by setup_roles (see its
    docstring: "no access to ... user/group management" for the other
    groups) - these tests pin that down at the view layer, not just on the
    Permission rows themselves."""

    def setUp(self):
        call_command("setup_roles")
        self.target = User.objects.create_user("bob", password="x")

    def _user_in(self, username, group_name):
        user = User.objects.create_user(username, password="x")
        user.groups.add(Group.objects.get(name=group_name))
        return user

    def test_admin_has_full_user_management_perms(self):
        admin = self._user_in("admin-perm", "ADMIN")
        for perm in ["view_user", "add_user", "change_user", "delete_user"]:
            self.assertTrue(admin.has_perm(f"auth.{perm}"))

    def test_soc_manager_has_no_user_management_perms(self):
        manager = self._user_in("manager-perm", "SOC_MANAGER")
        for perm in ["view_user", "add_user", "change_user", "delete_user"]:
            self.assertFalse(manager.has_perm(f"auth.{perm}"))

    def test_analyst_has_no_user_management_perms(self):
        analyst = self._user_in("analyst-perm", "ANALYST")
        for perm in ["view_user", "add_user", "change_user", "delete_user"]:
            self.assertFalse(analyst.has_perm(f"auth.{perm}"))

    def test_viewer_has_no_user_management_perms(self):
        viewer = self._user_in("viewer-perm", "VIEWER")
        for perm in ["view_user", "add_user", "change_user", "delete_user"]:
            self.assertFalse(viewer.has_perm(f"auth.{perm}"))

    def test_non_admin_gets_403_on_user_list(self):
        manager = self._user_in("manager-403", "SOC_MANAGER")
        self.client.force_login(manager)
        response = self.client.get(reverse("user_list"))
        self.assertEqual(response.status_code, 403)

    def test_non_admin_gets_403_on_user_create(self):
        analyst = self._user_in("analyst-403", "ANALYST")
        self.client.force_login(analyst)
        response = self.client.get(reverse("user_create"))
        self.assertEqual(response.status_code, 403)

    def test_anonymous_is_redirected_to_login(self):
        response = self.client.get(reverse("user_list"))
        self.assertEqual(response.status_code, 302)


class UserCreateTests(TestCase):
    def setUp(self):
        call_command("setup_roles")
        self.admin = User.objects.create_superuser("root", "root@example.com", "x")
        self.client.force_login(self.admin)

    def test_creating_a_user_hashes_the_password_and_assigns_groups(self):
        group = Group.objects.get(name="ANALYST")
        response = self.client.post(
            reverse("user_create"),
            {
                "username": "newanalyst",
                "first_name": "Nova",
                "last_name": "Analista",
                "email": "nova@example.com",
                "is_active": "on",
                "groups": [group.pk],
                "password1": "S3nhaForte!2026",
                "password2": "S3nhaForte!2026",
            },
        )
        self.assertEqual(response.status_code, 302)
        created = User.objects.get(username="newanalyst")
        self.assertNotEqual(created.password, "S3nhaForte!2026")
        self.assertTrue(created.check_password("S3nhaForte!2026"))
        self.assertEqual(list(created.groups.all()), [group])

    def test_password_confirmation_mismatch_is_rejected(self):
        response = self.client.post(
            reverse("user_create"),
            {
                "username": "mismatch",
                "is_active": "on",
                "password1": "S3nhaForte!2026",
                "password2": "OutraSenha!2026",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(User.objects.filter(username="mismatch").exists())

    def test_duplicate_username_is_rejected(self):
        User.objects.create_user("existing", password="x")
        response = self.client.post(
            reverse("user_create"),
            {
                "username": "existing",
                "is_active": "on",
                "password1": "S3nhaForte!2026",
                "password2": "S3nhaForte!2026",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(User.objects.filter(username="existing").count(), 1)


class UserUpdateTests(TestCase):
    def setUp(self):
        call_command("setup_roles")
        self.admin = User.objects.create_superuser("root2", "root2@example.com", "x")
        self.client.force_login(self.admin)
        self.target = User.objects.create_user("carol", password="x", email="old@example.com")

    def test_update_changes_profile_fields_and_groups(self):
        group = Group.objects.get(name="VIEWER")
        response = self.client.post(
            reverse("user_update", kwargs={"pk": self.target.pk}),
            {
                "username": "carol",
                "first_name": "Carol",
                "last_name": "Danvers",
                "email": "new@example.com",
                "is_active": "on",
                "groups": [group.pk],
            },
        )
        self.assertEqual(response.status_code, 302)
        self.target.refresh_from_db()
        self.assertEqual(self.target.email, "new@example.com")
        self.assertEqual(list(self.target.groups.all()), [group])

    def test_admin_cannot_deactivate_their_own_account(self):
        response = self.client.post(
            reverse("user_update", kwargs={"pk": self.admin.pk}),
            {
                "username": self.admin.username,
                "email": self.admin.email,
                # is_active intentionally omitted: an unchecked checkbox.
            },
        )
        self.assertEqual(response.status_code, 200)
        self.admin.refresh_from_db()
        self.assertTrue(self.admin.is_active)


class UserPasswordResetTests(TestCase):
    def setUp(self):
        call_command("setup_roles")
        self.admin = User.objects.create_superuser("root3", "root3@example.com", "x")
        self.client.force_login(self.admin)
        self.target = User.objects.create_user("dave", password="old-password")

    def test_admin_can_reset_another_users_password(self):
        response = self.client.post(
            reverse("user_password_reset", kwargs={"pk": self.target.pk}),
            {"new_password1": "NovaSenhaForte!2026", "new_password2": "NovaSenhaForte!2026"},
        )
        self.assertEqual(response.status_code, 302)
        self.target.refresh_from_db()
        self.assertTrue(self.target.check_password("NovaSenhaForte!2026"))
        self.assertFalse(self.target.check_password("old-password"))

    def test_mismatched_confirmation_leaves_password_unchanged(self):
        response = self.client.post(
            reverse("user_password_reset", kwargs={"pk": self.target.pk}),
            {"new_password1": "NovaSenhaForte!2026", "new_password2": "Diferente!2026"},
        )
        self.assertEqual(response.status_code, 200)
        self.target.refresh_from_db()
        self.assertTrue(self.target.check_password("old-password"))


class UserDeleteTests(TestCase):
    def setUp(self):
        call_command("setup_roles")
        self.admin = User.objects.create_superuser("root4", "root4@example.com", "x")
        self.client.force_login(self.admin)
        self.target = User.objects.create_user("erin", password="x")

    def test_admin_can_delete_another_user(self):
        response = self.client.post(reverse("user_delete", kwargs={"pk": self.target.pk}))
        self.assertEqual(response.status_code, 302)
        self.assertFalse(User.objects.filter(pk=self.target.pk).exists())

    def test_deleting_your_own_account_is_blocked(self):
        response = self.client.post(reverse("user_delete", kwargs={"pk": self.admin.pk}))
        self.assertEqual(response.status_code, 302)
        self.assertTrue(User.objects.filter(pk=self.admin.pk).exists())
