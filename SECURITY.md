# Security

## Before Deployment

- Generate new values for `API_KEY`, `JOB_SECRET`, and
  `EMBEDDING_API_SECRET`.
- Keep `.env`, OAuth client files, Gmail refresh tokens, database URLs, and
  backup passwords outside Git.
- Treat every `EXPO_PUBLIC_*` value as public. Expo embeds these values in the
  application bundle.
- Use a separate Gmail OAuth client and the read-only Gmail scope.
- Keep the Android APK private unless the API is upgraded to real user
  authentication.

The checked-in environment files contain examples and placeholders only.

## Reporting

Please report a suspected vulnerability privately through GitHub's security
advisory feature instead of opening a public issue.
