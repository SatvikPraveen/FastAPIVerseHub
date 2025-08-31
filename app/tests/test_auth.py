# File: app/tests/test_auth.py

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.core.security import security_manager
from app.tests.conftest import (
    assert_response_success, 
    assert_response_error, 
    assert_valid_token_response,
    UserFactory
)


class TestUserRegistration:
    """Test user registration endpoints."""
    
    async def test_register_user_success(self, async_client: AsyncClient, sample_user_data):
        """Test successful user registration."""
        response = await async_client.post("/api/v1/auth/register", json=sample_user_data)
        
        assert_response_success(response, 201)
        data = response.json()
        
        assert_valid_token_response(data)
        assert "user" in data
        assert data["user"]["email"] == sample_user_data["email"]
        assert data["user"]["full_name"] == sample_user_data["full_name"]
        assert data["user"]["is_active"] is True
    
    async def test_register_user_duplicate_email(
        self, 
        async_client: AsyncClient, 
        sample_user_data, 
        test_user: User
    ):
        """Test registration with duplicate email."""
        sample_user_data["email"] = test_user.email
        
        response = await async_client.post("/api/v1/auth/register", json=sample_user_data)
        
        assert_response_error(response, 400, "BAD_REQUEST")
        data = response.json()
        assert "already registered" in data["message"].lower()
    
    async def test_register_user_password_mismatch(self, async_client: AsyncClient, sample_user_data):
        """Test registration with password mismatch."""
        sample_user_data["confirm_password"] = "DifferentPassword123!"
        
        response = await async_client.post("/api/v1/auth/register", json=sample_user_data)
        
        assert_response_error(response, 422)
    
    async def test_register_user_weak_password(self, async_client: AsyncClient, sample_user_data):
        """Test registration with weak password."""
        weak_password = "123"
        sample_user_data["password"] = weak_password
        sample_user_data["confirm_password"] = weak_password
        
        response = await async_client.post("/api/v1/auth/register", json=sample_user_data)
        
        assert_response_error(response, 422)
    
    async def test_register_user_invalid_email(self, async_client: AsyncClient, sample_user_data):
        """Test registration with invalid email."""
        sample_user_data["email"] = "invalid-email"
        
        response = await async_client.post("/api/v1/auth/register", json=sample_user_data)
        
        assert_response_error(response, 422)
    
    async def test_register_user_missing_fields(self, async_client: AsyncClient):
        """Test registration with missing required fields."""
        incomplete_data = {
            "email": "test@example.com"
            # Missing password and other required fields
        }
        
        response = await async_client.post("/api/v1/auth/register", json=incomplete_data)
        
        assert_response_error(response, 422)


class TestUserLogin:
    """Test user login endpoints."""
    
    async def test_login_success(self, async_client: AsyncClient, test_user: User):
        """Test successful user login."""
        login_data = {
            "email": test_user.email,
            "password": "testpassword123"
        }
        
        response = await async_client.post("/api/v1/auth/login", json=login_data)
        
        assert_response_success(response)
        data = response.json()
        
        assert_valid_token_response(data)
        assert data["user"]["email"] == test_user.email
    
    async def test_login_wrong_password(self, async_client: AsyncClient, test_user: User):
        """Test login with wrong password."""
        login_data = {
            "email": test_user.email,
            "password": "wrongpassword"
        }
        
        response = await async_client.post("/api/v1/auth/login", json=login_data)
        
        assert_response_error(response, 401, "UNAUTHORIZED")
    
    async def test_login_nonexistent_user(self, async_client: AsyncClient):
        """Test login with nonexistent user."""
        login_data = {
            "email": "nonexistent@example.com",
            "password": "somepassword"
        }
        
        response = await async_client.post("/api/v1/auth/login", json=login_data)
        
        assert_response_error(response, 401, "UNAUTHORIZED")
    
    async def test_login_inactive_user(
        self, 
        async_client: AsyncClient, 
        db_session: AsyncSession
    ):
        """Test login with inactive user."""
        # Create inactive user
        inactive_user = await UserFactory.create_user(
            db_session,
            email="inactive@example.com",
            is_active=False
        )
        
        login_data = {
            "email": inactive_user.email,
            "password": "FactoryPassword123!"
        }
        
        response = await async_client.post("/api/v1/auth/login", json=login_data)
        
        assert_response_error(response, 400, "BAD_REQUEST")
    
    async def test_login_invalid_email_format(self, async_client: AsyncClient):
        """Test login with invalid email format."""
        login_data = {
            "email": "invalid-email",
            "password": "somepassword"
        }
        
        response = await async_client.post("/api/v1/auth/login", json=login_data)
        
        assert_response_error(response, 422)


class TestTokenOperations:
    """Test token-related operations."""
    
    async def test_refresh_token_success(self, async_client: AsyncClient, test_user: User):
        """Test successful token refresh."""
        # First login to get tokens
        login_data = {
            "email": test_user.email,
            "password": "testpassword123"
        }
        
        login_response = await async_client.post("/api/v1/auth/login", json=login_data)
        login_data = login_response.json()
        
        # Refresh token
        refresh_data = {
            "refresh_token": login_data["refresh_token"]
        }
        
        response = await async_client.post("/api/v1/auth/refresh", json=refresh_data)
        
        assert_response_success(response)
        data = response.json()
        
        assert_valid_token_response(data)
        assert data["access_token"] != login_data["access_token"]  # Should be different
    
    async def test_refresh_token_invalid(self, async_client: AsyncClient):
        """Test refresh with invalid token."""
        refresh_data = {
            "refresh_token": "invalid_refresh_token"
        }
        
        response = await async_client.post("/api/v1/auth/refresh", json=refresh_data)
        
        assert_response_error(response, 401, "UNAUTHORIZED")
    
    async def test_verify_token_valid(self, async_client: AsyncClient, auth_headers):
        """Test token verification with valid token."""
        response = await async_client.post(
            "/api/v1/auth/verify-token", 
            headers=auth_headers
        )
        
        assert_response_success(response)
        data = response.json()
        
        assert data["valid"] is True
        assert "user_id" in data
        assert "token_type" in data
    
    async def test_verify_token_invalid(self, async_client: AsyncClient):
        """Test token verification with invalid token."""
        invalid_headers = {"Authorization": "Bearer invalid_token"}
        
        response = await async_client.post(
            "/api/v1/auth/verify-token", 
            headers=invalid_headers
        )
        
        assert_response_success(response)
        data = response.json()
        
        assert data["valid"] is False
    
    async def test_get_current_user(self, async_client: AsyncClient, test_user: User, auth_headers):
        """Test getting current user info."""
        response = await async_client.get("/api/v1/auth/me", headers=auth_headers)
        
        assert_response_success(response)
        data = response.json()
        
        assert data["email"] == test_user.email
        assert data["full_name"] == test_user.full_name
        assert data["is_active"] == test_user.is_active
    
    async def test_get_current_user_unauthorized(self, async_client: AsyncClient):
        """Test getting current user without authentication."""
        response = await async_client.get("/api/v1/auth/me")
        
        assert_response_error(response, 401, "UNAUTHORIZED")


class TestPasswordOperations:
    """Test password-related operations."""
    
    async def test_change_password_success(
        self, 
        async_client: AsyncClient, 
        test_user: User, 
        auth_headers
    ):
        """Test successful password change."""
        response = await async_client.post(
            "/api/v1/auth/change-password",
            json={
                "current_password": "testpassword123",
                "new_password": "NewPassword456!"
            },
            headers=auth_headers
        )
        
        assert_response_success(response)
        data = response.json()
        
        assert "successfully" in data["message"].lower()
    
    async def test_change_password_wrong_current(
        self, 
        async_client: AsyncClient, 
        auth_headers
    ):
        """Test password change with wrong current password."""
        response = await async_client.post(
            "/api/v1/auth/change-password",
            json={
                "current_password": "wrongpassword",
                "new_password": "NewPassword456!"
            },
            headers=auth_headers
        )
        
        assert_response_error(response, 400, "BAD_REQUEST")
    
    async def test_forgot_password(self, async_client: AsyncClient, test_user: User):
        """Test forgot password request."""
        response = await async_client.post(
            "/api/v1/auth/forgot-password",
            json={"email": test_user.email}
        )
        
        assert_response_success(response)
        data = response.json()
        
        assert "reset link" in data["message"].lower()
    
    async def test_forgot_password_nonexistent_email(self, async_client: AsyncClient):
        """Test forgot password with nonexistent email."""
        response = await async_client.post(
            "/api/v1/auth/forgot-password",
            json={"email": "nonexistent@example.com"}
        )
        
        # Should still return success for security (don't reveal if email exists)
        assert_response_success(response)
    
    async def test_reset_password_success(self, async_client: AsyncClient, test_user: User):
        """Test successful password reset."""
        # Create a reset token
        reset_token = security_manager.create_access_token(
            data={"sub": str(test_user.id), "type": "password_reset"}
        )
        
        response = await async_client.post(
            "/api/v1/auth/reset-password",
            json={
                "token": reset_token,
                "new_password": "ResetPassword123!"
            }
        )
        
        assert_response_success(response)
        data = response.json()
        
        assert "successfully" in data["message"].lower()
    
    async def test_reset_password_invalid_token(self, async_client: AsyncClient):
        """Test password reset with invalid token."""
        response = await async_client.post(
            "/api/v1/auth/reset-password",
            json={
                "token": "invalid_token",
                "new_password": "ResetPassword123!"
            }
        )
        
        assert_response_error(response, 400, "BAD_REQUEST")


class TestLogout:
    """Test logout functionality."""
    
    async def test_logout_success(self, async_client: AsyncClient, auth_headers):
        """Test successful logout."""
        response = await async_client.post("/api/v1/auth/logout", headers=auth_headers)
        
        assert_response_success(response)
        data = response.json()
        
        assert "logged out" in data["message"].lower()
    
    async def test_logout_unauthorized(self, async_client: AsyncClient):
        """Test logout without authentication."""
        response = await async_client.post("/api/v1/auth/logout")
        
        assert_response_error(response, 401, "UNAUTHORIZED")