# Testing

## How to run

```bash
PYTHONPATH=. pytest services/api/tests
```

## How to run coverage

```bash
PYTHONPATH=. pytest services/api/tests \
  --cov=services.api.auth \
  --cov=services.api.users_service \
  --cov=services.api.routes.auth_routes
```

## Test Plan

### Register
- Happy path: successful user registration
- Edge case: duplicate email registration
- Failure mode: missing password

### Login
- Happy path: valid credentials return a bearer token
- Edge case: unknown user
- Failure mode: incorrect password

### Current User (/auth/me)
- Happy path: valid JWT returns the authenticated user
- Edge case: malformed token
- Failure mode: expired token

### Password Reset
- Happy path: existing user requests password reset
- Edge case: unknown email returns the same safe response
- Failure mode: invalid or expired reset token

## AI-Assisted Workflow

AI was used to help identify additional edge cases such as:
- duplicate users
- malformed JWTs
- expired tokens
- invalid reset tokens
- unknown email addresses

All generated tests were reviewed and adapted to verify the application's business logic.

## Coverage Results

- 13 tests passing
- Authentication coverage: **79%**